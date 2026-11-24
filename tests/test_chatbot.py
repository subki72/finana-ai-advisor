"""Offline unit tests for Groq advisor DI, circuit breaker, and PII-safe logging."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from src.chatbot import (
    CIRCUIT_OPEN_FALLBACK_MESSAGE,
    MISSING_KEY_FALLBACK_MESSAGE,
    UPSTREAM_ERROR_FALLBACK_MESSAGE,
    CircuitBreaker,
    MissingApiKeyError,
    chatbot,
    generate_advice,
    get_groq_client,
)
from src.config import Settings


class _MockCompletions:
    """In-memory mock replacement for Groq chat.completions."""

    def __init__(self, reply_text: str | None = None, error: Exception | None = None) -> None:
        self._reply_text = reply_text
        self._error = error
        self.recorded_calls: list[dict[str, object]] = []

    def create(self, *, model: str, messages: list[dict[str, str]]) -> object:
        self.recorded_calls.append({"model": model, "messages": messages})
        if self._error is not None:
            raise self._error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._reply_text))])


class _MockGroqClient:
    """In-memory mock replacement for Groq client."""

    def __init__(self, reply_text: str | None = None, error: Exception | None = None) -> None:
        self.completions = _MockCompletions(reply_text=reply_text, error=error)
        self.chat = SimpleNamespace(completions=self.completions)


def test_chatbot_happy_path_and_zero_pii_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Verify mocked reply succeeds while logging only character counts, never PII text."""
    # Arrange
    secret_income_story = "My salary is 12345678 IDR and my secret debt is 987654 IDR"
    expected_reply = "Needs 50%, Wants 30%, Savings 20%."
    mock_client = _MockGroqClient(reply_text=expected_reply)
    settings = Settings(groq_api_key="dummy-mock-test-key", groq_model="llama-3.3-70b-versatile")
    breaker = CircuitBreaker()

    # Act
    with caplog.at_level(logging.INFO, logger="src.chatbot"):
        reply = chatbot(
            secret_income_story,
            history=[{"role": "user", "content": "Halo"}, {"role": "assistant", "content": "Hi"}],
            client=mock_client,
            settings=settings,
            circuit_breaker=breaker,
        )

    # Assert
    assert reply == expected_reply
    assert len(mock_client.completions.recorded_calls) == 1
    sent_messages = mock_client.completions.recorded_calls[0]["messages"]
    assert isinstance(sent_messages, list)
    assert sent_messages[0]["role"] == "system"
    assert sent_messages[-1]["content"] == secret_income_story

    full_log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "12345678" not in full_log_text
    assert "987654" not in full_log_text
    assert "Needs 50%" not in full_log_text
    assert "message_chars=" in full_log_text
    assert "reply_chars=" in full_log_text


def test_chatbot_handles_missing_api_key_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return safe fallback without crashing when GROQ_API_KEY is absent."""
    # Arrange
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = Settings(groq_api_key="")

    # Act & Assert
    with pytest.raises(MissingApiKeyError):
        get_groq_client(settings)

    result = generate_advice(
        "How much emergency fund should I save?",
        settings=settings,
        circuit_breaker=CircuitBreaker(),
    )
    assert result.status == "unavailable"
    assert result.reply == MISSING_KEY_FALLBACK_MESSAGE


def test_get_groq_client_passes_explicit_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure lazy Groq factory forwards configured timeout to the SDK constructor."""
    # Arrange
    captured: dict[str, object] = {}

    def _fake_groq(*, api_key: str, timeout: float) -> object:
        captured["api_key"] = api_key
        captured["timeout"] = timeout
        return _MockGroqClient(reply_text="ok")

    import src.chatbot as chatbot_module

    monkeypatch.setattr(chatbot_module, "Groq", _fake_groq)
    settings = Settings(groq_api_key="dummy-configured-key", request_timeout_seconds=12.5)

    # Act
    client = get_groq_client(settings)

    # Assert
    assert client is not None
    assert captured["api_key"] == "dummy-configured-key"
    assert captured["timeout"] == 12.5


def test_chatbot_upstream_error_returns_safe_fallback_without_leaking_details() -> None:
    """Never return raw exception messages on timeout or upstream API failure."""
    # Arrange
    failing_client = _MockGroqClient(error=TimeoutError("internal-upstream-host:443 timed out"))
    settings = Settings(groq_api_key="dummy-mock-test-key")
    breaker = CircuitBreaker(failure_threshold=3)

    # Act
    result = generate_advice(
        "Should I refinance my mortgage?",
        client=failing_client,
        settings=settings,
        circuit_breaker=breaker,
    )

    # Assert
    assert result.status == "degraded"
    assert result.reply == UPSTREAM_ERROR_FALLBACK_MESSAGE
    assert "internal-upstream-host" not in result.reply


def test_circuit_breaker_opens_and_recovers_after_cooldown() -> None:
    """Open circuit after consecutive failures and allow half-open recovery after cooldown."""
    # Arrange
    current_time = [100.0]
    breaker = CircuitBreaker(
        failure_threshold=2,
        cooldown_seconds=30.0,
        clock=lambda: current_time[0],
    )
    failing_client = _MockGroqClient(error=RuntimeError("boom"))
    healthy_client = _MockGroqClient(reply_text="Recovered advice.")
    settings = Settings(groq_api_key="dummy-mock-test-key")

    # Act: trigger 2 consecutive failures -> opens circuit
    generate_advice("q1", client=failing_client, settings=settings, circuit_breaker=breaker)
    generate_advice("q2", client=failing_client, settings=settings, circuit_breaker=breaker)
    open_result = generate_advice("q3", client=healthy_client, settings=settings, circuit_breaker=breaker)

    # Assert open short-circuit
    assert breaker.state == "open"
    assert open_result.status == "unavailable"
    assert open_result.reply == CIRCUIT_OPEN_FALLBACK_MESSAGE
    assert len(healthy_client.completions.recorded_calls) == 0

    # Act: advance clock past cooldown -> recovers
    current_time[0] += 31.0
    recovered_result = generate_advice("q4", client=healthy_client, settings=settings, circuit_breaker=breaker)

    # Assert closed recovery
    assert recovered_result.status == "ok"
    assert recovered_result.reply == "Recovered advice."
    assert breaker.state == "closed"


def test_chatbot_rejects_empty_user_message() -> None:
    """Raise ValueError upfront when user_message is empty or blank."""
    with pytest.raises(ValueError, match="user_message"):
        chatbot("   ", [])
