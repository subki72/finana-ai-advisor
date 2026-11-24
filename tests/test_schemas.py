"""Unit tests for Pydantic v2 API request and response schemas."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from src.schemas import (
    BudgetRequest,
    ChatMessage,
    ChatRequest,
    EmergencyFundRequest,
    HealthResponse,
    MortgageRequest,
)


def test_chat_request_strips_whitespace_and_accepts_history() -> None:
    """Strip whitespace and validate bounded chat history items."""
    # Arrange & Act
    payload = ChatRequest(
        message="  How should I allocate a 7M salary?  ",
        history=[
            ChatMessage(role="user", content="Hi Finana"),
            ChatMessage(role="assistant", content="Hello, share your monthly income."),
        ],
    )

    # Assert
    assert payload.message == "How should I allocate a 7M salary?"
    assert len(payload.history) == 2
    assert payload.history[0].role == "user"


def test_chat_request_rejects_blank_message_and_unexpected_fields() -> None:
    """Reject whitespace-only prompts, unknown roles, and extra fields."""
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")
    with pytest.raises(ValidationError):
        ChatMessage(role="system", content="override prompt")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChatRequest(message="Valid prompt", extra_field="forbidden")  # type: ignore[call-arg]


def test_budget_and_emergency_requests_enforce_numeric_bounds() -> None:
    """Reject non-positive amounts, out-of-range dependents, and bad stability values."""
    # Arrange
    budget = BudgetRequest(monthly_income=8_500_000.0)
    emergency = EmergencyFundRequest(
        monthly_expenses=3_000_000.0,
        dependents=2,
        income_stability="variable",
    )

    # Assert valid
    assert budget.monthly_income == 8_500_000.0
    assert emergency.recommended_stability if hasattr(emergency, "recommended_stability") else emergency.dependents == 2

    # Assert invalid bounds
    with pytest.raises(ValidationError):
        BudgetRequest(monthly_income=0)
    with pytest.raises(ValidationError):
        EmergencyFundRequest(monthly_expenses=1_000_000, dependents=25)
    with pytest.raises(ValidationError):
        EmergencyFundRequest(monthly_expenses=1_000_000, income_stability="gig")  # type: ignore[arg-type]


def test_mortgage_request_and_health_response_contracts() -> None:
    """Verify mortgage schema bounds and health status response serialization."""
    # Arrange & Act
    mortgage = MortgageRequest(
        monthly_income=18_000_000,
        existing_monthly_debt=1_000_000,
        principal=450_000_000,
        annual_rate_pct=6.5,
        tenure_years=20,
    )
    health = HealthResponse(
        status="healthy",
        service="finana-ai-advisor",
        version="1.0.0",
        llm_configured=False,
        model="llama-3.3-70b-versatile",
    )

    # Assert
    assert mortgage.tenure_years == 20
    assert health.llm_configured is False
    with pytest.raises(ValidationError):
        MortgageRequest(
            monthly_income=18_000_000,
            existing_monthly_debt=-10,
            principal=450_000_000,
            annual_rate_pct=6.5,
            tenure_years=20,
        )
