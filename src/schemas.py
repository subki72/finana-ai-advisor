"""Pydantic v2 request and response contracts for Finana AI Advisor API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CHAT_CHARS = 4000
MAX_HISTORY_ITEMS = 20


class ChatMessage(BaseModel):
    """Single conversational turn in chat history."""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CHAT_CHARS)

    @field_validator("content")
    @classmethod
    def validate_non_blank_content(cls, value: str) -> str:
        """Strip whitespace and reject blank-only chat turns."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be blank.")
        return cleaned


class ChatRequest(BaseModel):
    """Inbound payload for the AI financial advisor endpoint."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=MAX_CHAT_CHARS)
    history: list[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_ITEMS)

    @field_validator("message")
    @classmethod
    def validate_non_blank_message(cls, value: str) -> str:
        """Strip whitespace and reject empty or whitespace-only prompts."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be blank.")
        return cleaned


class ChatResponse(BaseModel):
    """Outbound response from the AI financial advisor endpoint."""

    reply: str
    model: str
    status: Literal["ok", "degraded", "unavailable"] = "ok"


class BudgetRequest(BaseModel):
    """Inbound payload for 50/30/20 personal budget calculation."""

    model_config = ConfigDict(extra="forbid")

    monthly_income: float = Field(gt=0, le=1e12)


class BudgetBreakdownResponse(BaseModel):
    """Outbound 50/30/20 monthly budget breakdown."""

    monthly_income: float
    needs: float
    wants: float
    savings: float
    needs_pct: float = 50.0
    wants_pct: float = 30.0
    savings_pct: float = 20.0


class EmergencyFundRequest(BaseModel):
    """Inbound payload for emergency fund target calculation."""

    model_config = ConfigDict(extra="forbid")

    monthly_expenses: float = Field(gt=0, le=1e12)
    dependents: int = Field(default=0, ge=0, le=20)
    income_stability: Literal["stable", "variable", "freelance"] = "stable"


class EmergencyFundResponse(BaseModel):
    """Outbound emergency fund target and rationale."""

    monthly_expenses: float
    dependents: int
    income_stability: str
    recommended_months: int
    minimum_target: float
    recommended_target: float
    rationale: str


class MortgageRequest(BaseModel):
    """Inbound payload for mortgage installment and DSR evaluation."""

    model_config = ConfigDict(extra="forbid")

    monthly_income: float = Field(gt=0, le=1e12)
    existing_monthly_debt: float = Field(default=0.0, ge=0, le=1e12)
    principal: float = Field(gt=0, le=1e13)
    annual_rate_pct: float = Field(ge=0.0, le=100.0)
    tenure_years: int = Field(ge=1, le=40)


class MortgageAssessmentResponse(BaseModel):
    """Outbound mortgage installment and affordability evaluation."""

    monthly_installment: float
    existing_monthly_debt: float
    total_monthly_debt: float
    dsr_pct: float
    max_recommended_installment: float
    verdict: Literal["affordable", "stretched", "unaffordable"]
    rationale: str


class HealthResponse(BaseModel):
    """Liveness and configuration readiness payload."""

    status: Literal["healthy", "degraded"]
    service: str
    version: str
    llm_configured: bool
    model: str


class ErrorResponse(BaseModel):
    """Structured error response that never exposes internal stack traces."""

    detail: str
    error_code: str
