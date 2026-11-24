"""Centralized, validated configuration and structured logging for Finana AI Advisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
import os
import sys

from dotenv import load_dotenv

DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
MAX_REQUEST_TIMEOUT_SECONDS = 300.0
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 3
DEFAULT_CIRCUIT_BREAKER_COOLDOWN_SECONDS = 30.0
DEFAULT_ALLOWED_ORIGINS: tuple[str, ...] = (
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
)
VALID_LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
PLACEHOLDER_API_KEYS: frozenset[str] = frozenset(
    {
        "",
        "your_groq_api_key_here",
        "your_groq_api_key_placeholder",
    }
)


class JsonLogFormatter(logging.Formatter):
    """Formats application log records as single-line structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record into JSON without exposing raw PII payloads."""
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=True)


def _parse_positive_float(raw_value: str | None, default: float, env_name: str) -> float:
    """Parse an environment string as a positive finite float."""
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = float(raw_value.strip())
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a valid number, got {raw_value!r}.") from exc
    if parsed <= 0:
        raise ValueError(f"{env_name} must be greater than zero.")
    return parsed


def _parse_positive_int(raw_value: str | None, default: int, env_name: str) -> int:
    """Parse an environment string as a positive integer."""
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise ValueError(f"{env_name} must be a valid integer, got {raw_value!r}.") from exc
    if parsed <= 0:
        raise ValueError(f"{env_name} must be greater than zero.")
    return parsed


def _parse_allowed_origins(raw_value: str | None) -> tuple[str, ...]:
    """Parse comma-separated CORS origins from the environment."""
    if raw_value is None or not raw_value.strip():
        return DEFAULT_ALLOWED_ORIGINS
    origins = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    if not origins:
        raise ValueError("ALLOWED_ORIGINS must specify at least one valid origin.")
    return origins


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings for Finana UI, FastAPI gateway, and Groq advisor."""

    groq_api_key: str = ""
    groq_model: str = DEFAULT_GROQ_MODEL
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE
    circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD
    circuit_breaker_cooldown_seconds: float = DEFAULT_CIRCUIT_BREAKER_COOLDOWN_SECONDS
    log_level: str = "INFO"

    def is_llm_configured(self) -> bool:
        """Return True when a non-placeholder Groq API key is present."""
        cleaned = self.groq_api_key.strip()
        if cleaned in PLACEHOLDER_API_KEYS:
            return False
        return not cleaned.lower().startswith("your_")

    def validate(self, require_api_key: bool = False) -> None:
        """Validate configuration invariants upfront.

        Args:
            require_api_key: When True, requires a real non-placeholder GROQ_API_KEY.

        Raises:
            ValueError: If any setting violates bounds or required invariants.
        """
        if require_api_key and not self.is_llm_configured():
            raise ValueError("GROQ_API_KEY must be set to a valid API key.")
        if not self.groq_model.strip():
            raise ValueError("GROQ_MODEL must not be empty.")
        if not (0 < self.request_timeout_seconds <= MAX_REQUEST_TIMEOUT_SECONDS):
            raise ValueError(f"REQUEST_TIMEOUT_SECONDS must be in (0, {MAX_REQUEST_TIMEOUT_SECONDS}].")
        if self.rate_limit_per_minute <= 0:
            raise ValueError("RATE_LIMIT_PER_MINUTE must be greater than zero.")
        if self.circuit_breaker_threshold <= 0:
            raise ValueError("CIRCUIT_BREAKER_THRESHOLD must be greater than zero.")
        if self.circuit_breaker_cooldown_seconds <= 0:
            raise ValueError("CIRCUIT_BREAKER_COOLDOWN_SECONDS must be greater than zero.")
        if self.log_level.upper() not in VALID_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}.")
        if not self.allowed_origins:
            raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")

    @classmethod
    def from_env(cls, load_env_file: bool = True) -> Settings:
        """Construct and validate Settings from environment variables.

        Args:
            load_env_file: Whether to load variables from a local `.env` file first.

        Returns:
            A validated `Settings` instance.
        """
        if load_env_file:
            load_dotenv(override=False)

        settings = cls(
            groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
            groq_model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip(),
            request_timeout_seconds=_parse_positive_float(
                os.getenv("REQUEST_TIMEOUT_SECONDS"),
                DEFAULT_REQUEST_TIMEOUT_SECONDS,
                "REQUEST_TIMEOUT_SECONDS",
            ),
            allowed_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS")),
            rate_limit_per_minute=_parse_positive_int(
                os.getenv("RATE_LIMIT_PER_MINUTE"),
                DEFAULT_RATE_LIMIT_PER_MINUTE,
                "RATE_LIMIT_PER_MINUTE",
            ),
            circuit_breaker_threshold=_parse_positive_int(
                os.getenv("CIRCUIT_BREAKER_THRESHOLD"),
                DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
                "CIRCUIT_BREAKER_THRESHOLD",
            ),
            circuit_breaker_cooldown_seconds=_parse_positive_float(
                os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS"),
                DEFAULT_CIRCUIT_BREAKER_COOLDOWN_SECONDS,
                "CIRCUIT_BREAKER_COOLDOWN_SECONDS",
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
        settings.validate(require_api_key=False)
        return settings


def get_settings(load_env_file: bool = True) -> Settings:
    """Factory returning validated application settings."""
    return Settings.from_env(load_env_file=load_env_file)


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure structured JSON logging idempotently and return the app logger.

    Args:
        level: Optional log level override (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured `finana` package logger.
    """
    resolved_level = (level or os.getenv("LOG_LEVEL", "INFO")).strip().upper() or "INFO"
    if resolved_level not in VALID_LOG_LEVELS:
        raise ValueError(f"Invalid LOG_LEVEL {resolved_level!r}; expected {sorted(VALID_LOG_LEVELS)}.")

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, resolved_level))

    # Avoid duplicating handlers or stripping pytest caplog handlers on repeated calls.
    has_json_handler = any(isinstance(handler.formatter, JsonLogFormatter) for handler in root_logger.handlers)
    if not has_json_handler:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(JsonLogFormatter())
        root_logger.addHandler(stream_handler)

    return logging.getLogger("finana")
