"""Groq-backed conversational financial advisor with lazy DI and resilience controls."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import logging
import threading
import time
from typing import Any, Literal, Protocol

from groq import Groq, GroqError

try:
    from src.config import Settings, get_settings
except ModuleNotFoundError:  # pragma: no cover - supports `streamlit run src/main.py` from src/
    from config import Settings, get_settings

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 20
AdviceStatus = Literal["ok", "degraded", "unavailable"]

SYSTEM_INSTRUCTION = (
    "You are Finana, a casual and practical Financial Advisor. Your tasks: "
    "1. Analyze the user's financial story clearly. "
    "2. If income numbers are provided, calculate a 50/30/20 budget breakdown. "
    "3. Give practical, actionable personal finance advice. "
    "Tone: Casual, friendly, and concise. Do not use emojis in responses."
)

MISSING_KEY_FALLBACK_MESSAGE = (
    "Finana AI chat is currently unavailable because GROQ_API_KEY is not configured. "
    "You can still use the deterministic budget, emergency fund, and mortgage calculators."
)
CIRCUIT_OPEN_FALLBACK_MESSAGE = (
    "Finana AI chat is temporarily paused due to upstream service instability. "
    "Please try again shortly or use the deterministic financial calculators."
)
UPSTREAM_ERROR_FALLBACK_MESSAGE = (
    "Finana could not complete your request due to a temporary AI service error. Please try again in a moment."
)


class MissingApiKeyError(ValueError):
    """Raised when an LLM request is attempted without a configured Groq API key."""


class ChatCompletionChoiceProtocol(Protocol):
    """Structural protocol for Groq chat completion choice message container."""

    message: Any


class ChatClientProtocol(Protocol):
    """Structural protocol allowing clean dependency injection of Groq-compatible clients."""

    chat: Any


@dataclass(frozen=True)
class AdviceResult:
    """Structured result returned by the conversational financial advisor."""

    reply: str
    model: str
    status: AdviceStatus


class CircuitBreaker:
    """Thread-safe circuit breaker guarding upstream Groq API calls."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize circuit breaker thresholds and monotonic clock."""
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be greater than zero.")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be greater than zero.")
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._failure_count = 0
        self._state: Literal["closed", "open", "half_open"] = "closed"
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        """Return current circuit breaker state after evaluating cooldown expiration."""
        with self._lock:
            self._refresh_state_locked()
            return self._state

    def _refresh_state_locked(self) -> None:
        """Transition from open to half-open when cooldown expires (caller holds lock)."""
        if self._state == "open" and (self._clock() - self._opened_at) >= self._cooldown_seconds:
            self._state = "half_open"

    def allow_request(self) -> bool:
        """Return True if an upstream request is permitted right now."""
        with self._lock:
            self._refresh_state_locked()
            return self._state != "open"

    def record_success(self) -> None:
        """Reset failure tracking and close the circuit after a successful call."""
        with self._lock:
            self._failure_count = 0
            self._state = "closed"

    def record_failure(self) -> None:
        """Record an upstream failure and open the circuit once threshold is reached."""
        with self._lock:
            self._failure_count += 1
            if self._state == "half_open" or self._failure_count >= self._failure_threshold:
                self._state = "open"
                self._opened_at = self._clock()


_DEFAULT_CIRCUIT_BREAKER = CircuitBreaker()


def reset_default_circuit_breaker() -> None:
    """Reset the module-level circuit breaker used by direct Streamlit helper calls."""
    _DEFAULT_CIRCUIT_BREAKER.record_success()


def get_groq_client(settings: Settings | None = None) -> Groq:
    """Lazily construct a timeout-protected Groq SDK client from validated settings.

    Args:
        settings: Optional pre-loaded `Settings` instance.

    Returns:
        Configured `Groq` client with explicit network timeout.

    Raises:
        MissingApiKeyError: If `GROQ_API_KEY` is missing or a placeholder value.
    """
    active_settings = settings or get_settings()
    if not active_settings.is_llm_configured():
        raise MissingApiKeyError("GROQ_API_KEY is not configured.")
    return Groq(
        api_key=active_settings.groq_api_key,
        timeout=active_settings.request_timeout_seconds,
    )


def _build_messages(
    user_message: str,
    history: Sequence[Mapping[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build sanitized chat messages with bounded conversation history."""
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("user_message must be a non-empty string.")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
    if history:
        for turn in history[-MAX_HISTORY_TURNS:]:
            role = str(turn.get("role", "")).strip()
            content = str(turn.get("content", "")).strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _extract_reply_text(response: Any) -> str:
    """Extract and validate non-empty assistant content from Groq completion payload."""
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("Empty choices returned by chat completion response.")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty content returned by chat completion response.")
    return content.strip()


def _invoke_completion(
    active_client: ChatClientProtocol,
    model_name: str,
    messages: list[dict[str, str]],
    breaker: CircuitBreaker,
) -> AdviceResult:
    """Execute Groq completion request under circuit-breaker error handling."""
    logger.info(
        "Dispatching chat request model=%s message_chars=%d history_turns=%d",
        model_name,
        len(messages[-1]["content"]),
        len(messages) - 2,
    )
    try:
        response = active_client.chat.completions.create(model=model_name, messages=messages)
        reply = _extract_reply_text(response)
    except (GroqError, OSError, TimeoutError, ValueError, RuntimeError, AttributeError, IndexError) as exc:
        breaker.record_failure()
        logger.error("Chat completion failed model=%s error_type=%s", model_name, type(exc).__name__)
        return AdviceResult(reply=UPSTREAM_ERROR_FALLBACK_MESSAGE, model=model_name, status="degraded")

    breaker.record_success()
    logger.info("Chat completion succeeded model=%s reply_chars=%d", model_name, len(reply))
    return AdviceResult(reply=reply, model=model_name, status="ok")


def generate_advice(
    user_message: str,
    history: Sequence[Mapping[str, str]] | None = None,
    client: ChatClientProtocol | None = None,
    settings: Settings | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> AdviceResult:
    """Generate financial advice via Groq with PII-safe logging and safe fallbacks.

    Args:
        user_message: User financial prompt or question.
        history: Optional prior conversation turns (`role`, `content`).
        client: Optional injected Groq-compatible client for offline testing.
        settings: Optional pre-loaded `Settings`.
        circuit_breaker: Optional `CircuitBreaker` guarding upstream calls.

    Returns:
        `AdviceResult` containing reply text, model name, and status.

    Raises:
        ValueError: If `user_message` is blank or not a string.
    """
    messages = _build_messages(user_message, history)
    active_settings = settings or get_settings()
    breaker = circuit_breaker or _DEFAULT_CIRCUIT_BREAKER

    if not breaker.allow_request():
        logger.warning("Circuit breaker open; skipping Groq call model=%s", active_settings.groq_model)
        return AdviceResult(
            reply=CIRCUIT_OPEN_FALLBACK_MESSAGE,
            model=active_settings.groq_model,
            status="unavailable",
        )

    try:
        active_client = client if client is not None else get_groq_client(active_settings)
    except MissingApiKeyError:
        logger.warning("Groq API key not configured; returning advisory fallback")
        return AdviceResult(
            reply=MISSING_KEY_FALLBACK_MESSAGE,
            model=active_settings.groq_model,
            status="unavailable",
        )

    return _invoke_completion(active_client, active_settings.groq_model, messages, breaker)


def chatbot(
    user_message: str,
    history: Sequence[Mapping[str, str]] | None = None,
    client: ChatClientProtocol | None = None,
    settings: Settings | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> str:
    """Backward-compatible wrapper returning advisor reply text for UI callers.

    Args:
        user_message: User financial prompt or question.
        history: Optional prior conversation turns.
        client: Optional injected Groq client.
        settings: Optional `Settings` instance.
        circuit_breaker: Optional `CircuitBreaker`.

    Returns:
        Advisor reply string or safe fallback message.
    """
    return generate_advice(
        user_message=user_message,
        history=history,
        client=client,
        settings=settings,
        circuit_breaker=circuit_breaker,
    ).reply
