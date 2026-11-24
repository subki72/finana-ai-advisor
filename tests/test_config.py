"""Unit tests for runtime Settings validation and structured JSON logging."""

from __future__ import annotations

import json
import logging

import pytest

from src.config import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    JsonLogFormatter,
    Settings,
    configure_logging,
)


def test_settings_from_env_uses_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Load Settings cleanly without GROQ_API_KEY using production defaults."""
    # Arrange
    for env_key in (
        "GROQ_API_KEY",
        "GROQ_MODEL",
        "REQUEST_TIMEOUT_SECONDS",
        "ALLOWED_ORIGINS",
        "RATE_LIMIT_PER_MINUTE",
        "CIRCUIT_BREAKER_THRESHOLD",
        "CIRCUIT_BREAKER_COOLDOWN_SECONDS",
        "LOG_LEVEL",
    ):
        monkeypatch.delenv(env_key, raising=False)

    # Act
    settings = Settings.from_env(load_env_file=False)

    # Assert
    assert settings.groq_api_key == ""
    assert settings.groq_model == DEFAULT_GROQ_MODEL
    assert settings.request_timeout_seconds == DEFAULT_REQUEST_TIMEOUT_SECONDS
    assert settings.rate_limit_per_minute == DEFAULT_RATE_LIMIT_PER_MINUTE
    assert settings.is_llm_configured() is False


def test_settings_from_env_parses_custom_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse explicit environment configuration overrides accurately."""
    # Arrange
    monkeypatch.setenv("GROQ_API_KEY", "dummy-configured-test-token")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.1-8b-instant")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "15.5")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com, http://localhost:8501 ")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "45")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    # Act
    settings = Settings.from_env(load_env_file=False)

    # Assert
    assert settings.is_llm_configured() is True
    assert settings.groq_model == "llama-3.1-8b-instant"
    assert settings.request_timeout_seconds == 15.5
    assert settings.allowed_origins == ("https://app.example.com", "http://localhost:8501")
    assert settings.rate_limit_per_minute == 45
    assert settings.log_level == "DEBUG"


def test_settings_validate_enforces_api_key_only_when_required() -> None:
    """Allow unconfigured API key on startup, but reject when require_api_key=True."""
    # Arrange
    settings = Settings(groq_api_key="your_groq_api_key_placeholder")

    # Act & Assert
    settings.validate(require_api_key=False)
    assert settings.is_llm_configured() is False
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        settings.validate(require_api_key=True)


@pytest.mark.parametrize(
    ("env_name", "env_value"),
    [
        ("REQUEST_TIMEOUT_SECONDS", "-5"),
        ("REQUEST_TIMEOUT_SECONDS", "not-a-number"),
        ("REQUEST_TIMEOUT_SECONDS", "999"),
        ("RATE_LIMIT_PER_MINUTE", "0"),
        ("RATE_LIMIT_PER_MINUTE", "abc"),
        ("LOG_LEVEL", "TRACE"),
    ],
)
def test_settings_from_env_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    env_name: str,
    env_value: str,
) -> None:
    """Reject invalid numeric or enum configuration values at startup."""
    monkeypatch.setenv(env_name, env_value)
    with pytest.raises(ValueError):
        Settings.from_env(load_env_file=False)


def test_configure_logging_formats_structured_json_idempotently() -> None:
    """Configure JSON formatter once and serialize log records cleanly."""
    # Arrange
    root_logger = logging.getLogger()
    before_json_handlers = sum(isinstance(handler.formatter, JsonLogFormatter) for handler in root_logger.handlers)

    # Act
    app_logger = configure_logging("INFO")
    app_logger_second = configure_logging("WARNING")
    after_json_handlers = sum(isinstance(handler.formatter, JsonLogFormatter) for handler in root_logger.handlers)
    record = logging.LogRecord(
        name="finana.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Structured event count=%d",
        args=(3,),
        exc_info=None,
    )
    formatted = JsonLogFormatter().format(record)
    parsed = json.loads(formatted)

    # Assert
    assert app_logger.name == "finana"
    assert app_logger_second is app_logger
    assert after_json_handlers == max(1, before_json_handlers)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "finana.test"
    assert parsed["message"] == "Structured event count=3"


def test_configure_logging_rejects_invalid_level() -> None:
    """Raise ValueError when configured with an unsupported log level."""
    with pytest.raises(ValueError, match="LOG_LEVEL"):
        configure_logging("VERBOSE")
