"""FastAPI microservice gateway for Finana AI Advisor and deterministic calculators."""

from __future__ import annotations

from collections import deque
from collections.abc import Awaitable, Callable
import logging
import math
import threading
import time
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.calculators import (
    assess_mortgage_affordability,
    calculate_budget_50_30_20,
    calculate_emergency_fund,
)
from src.chatbot import ChatClientProtocol, CircuitBreaker, generate_advice
from src.config import Settings, configure_logging, get_settings
from src.schemas import (
    BudgetBreakdownResponse,
    BudgetRequest,
    ChatRequest,
    ChatResponse,
    EmergencyFundRequest,
    EmergencyFundResponse,
    ErrorResponse,
    HealthResponse,
    MortgageAssessmentResponse,
    MortgageRequest,
)

APP_NAME = "finana-ai-advisor"
APP_VERSION = "1.0.0"
RATE_LIMIT_WINDOW_SECONDS = 60.0

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter keyed by client IP."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: float = RATE_LIMIT_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize sliding-window limits and monotonic clock."""
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero.")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero.")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = {}

    def check_and_record(self, client_key: str) -> tuple[bool, int]:
        """Verify quota for `client_key` and record the request if allowed.

        Returns:
            Tuple of `(allowed, retry_after_seconds)`.
        """
        key = client_key.strip() or "unknown"
        now = self._clock()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                oldest = bucket[0]
                retry_after = max(1, math.ceil(self._window_seconds - (now - oldest)))
                return False, retry_after

            bucket.append(now)
            return True, 0


def get_app_settings(request: Request) -> Settings:
    """FastAPI dependency returning active application settings."""
    return request.app.state.settings


def get_llm_client(request: Request) -> ChatClientProtocol | None:
    """FastAPI dependency returning an optional injected LLM client."""
    return request.app.state.llm_client


def get_circuit_breaker(request: Request) -> CircuitBreaker:
    """FastAPI dependency returning the app's upstream circuit breaker."""
    return request.app.state.circuit_breaker


def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing sliding-window rate limits per client IP."""
    limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
    client_host = request.client.host if request.client and request.client.host else "unknown"
    allowed, retry_after = limiter.check_and_record(client_host)
    if not allowed:
        logger.warning("Rate limit exceeded path=%s retry_after=%d", request.url.path, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(retry_after)},
        )


def _register_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure CORS allowlist and defensive HTTP security headers."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(
    active_settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    """Liveness and configuration readiness probe."""
    return HealthResponse(
        status="healthy",
        service=APP_NAME,
        version=APP_VERSION,
        llm_configured=active_settings.is_llm_configured(),
        model=active_settings.groq_model,
    )


@router.post("/api/v1/budget", response_model=BudgetBreakdownResponse, tags=["Calculators"])
def calculate_budget(payload: BudgetRequest) -> BudgetBreakdownResponse:
    """Compute deterministic 50/30/20 monthly budget allocation."""
    allocation = calculate_budget_50_30_20(payload.monthly_income)
    return BudgetBreakdownResponse(
        monthly_income=allocation.monthly_income,
        needs=allocation.needs,
        wants=allocation.wants,
        savings=allocation.savings,
        needs_pct=allocation.needs_pct,
        wants_pct=allocation.wants_pct,
        savings_pct=allocation.savings_pct,
    )


@router.post(
    "/api/v1/emergency-fund",
    response_model=EmergencyFundResponse,
    tags=["Calculators"],
)
def calculate_emergency_reserve(payload: EmergencyFundRequest) -> EmergencyFundResponse:
    """Calculate target emergency reserve coverage between 3 and 12 months."""
    recommendation = calculate_emergency_fund(
        monthly_expenses=payload.monthly_expenses,
        dependents=payload.dependents,
        income_stability=payload.income_stability,
    )
    return EmergencyFundResponse(
        monthly_expenses=recommendation.monthly_expenses,
        dependents=recommendation.dependents,
        income_stability=recommendation.income_stability,
        recommended_months=recommendation.recommended_months,
        minimum_target=recommendation.minimum_target,
        recommended_target=recommendation.recommended_target,
        rationale=recommendation.rationale,
    )


@router.post("/api/v1/mortgage", response_model=MortgageAssessmentResponse, tags=["Calculators"])
def assess_mortgage(payload: MortgageRequest) -> MortgageAssessmentResponse:
    """Assess mortgage installment and combined Debt Service Ratio (DSR)."""
    assessment = assess_mortgage_affordability(
        monthly_income=payload.monthly_income,
        existing_monthly_debt=payload.existing_monthly_debt,
        principal=payload.principal,
        annual_rate_pct=payload.annual_rate_pct,
        tenure_years=payload.tenure_years,
    )
    return MortgageAssessmentResponse(
        monthly_installment=assessment.monthly_installment,
        existing_monthly_debt=assessment.existing_monthly_debt,
        total_monthly_debt=assessment.total_monthly_debt,
        dsr_pct=assessment.dsr_pct,
        max_recommended_installment=assessment.max_recommended_installment,
        verdict=assessment.verdict,
        rationale=assessment.rationale,
    )


@router.post(
    "/api/v1/chat",
    response_model=ChatResponse,
    tags=["Advisor"],
    dependencies=[Depends(enforce_rate_limit)],
)
def chat_advisor(
    payload: ChatRequest,
    active_settings: Annotated[Settings, Depends(get_app_settings)],
    injected_client: Annotated[ChatClientProtocol | None, Depends(get_llm_client)],
    breaker: Annotated[CircuitBreaker, Depends(get_circuit_breaker)],
) -> ChatResponse:
    """Generate personalized financial guidance through the rate-limited AI advisor."""
    history_dicts = [{"role": item.role, "content": item.content} for item in payload.history]
    result = generate_advice(
        user_message=payload.message,
        history=history_dicts,
        client=injected_client,
        settings=active_settings,
        circuit_breaker=breaker,
    )
    if result.status != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.reply,
        )
    return ChatResponse(reply=result.reply, model=result.model, status=result.status)


def create_app(
    settings: Settings | None = None,
    llm_client: ChatClientProtocol | None = None,
    rate_limiter: SlidingWindowRateLimiter | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> FastAPI:
    """Create and configure the Finana FastAPI application instance."""
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    application = FastAPI(
        title="Finana AI Financial Advisor API",
        version=APP_VERSION,
        description=(
            "Personal finance calculators (50/30/20, emergency fund, KPR/DSR) and "
            "rate-limited Groq Llama 3.3 conversational advisory service."
        ),
    )
    application.state.settings = active_settings
    application.state.llm_client = llm_client
    application.state.rate_limiter = rate_limiter or SlidingWindowRateLimiter(
        max_requests=active_settings.rate_limit_per_minute,
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
    )
    application.state.circuit_breaker = circuit_breaker or CircuitBreaker(
        failure_threshold=active_settings.circuit_breaker_threshold,
        cooldown_seconds=active_settings.circuit_breaker_cooldown_seconds,
    )

    _register_middleware(application, active_settings)

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled API exception path=%s error_type=%s",
            request.url.path,
            type(exc).__name__,
        )
        payload = ErrorResponse(
            detail="An unexpected internal error occurred.",
            error_code="INTERNAL_SERVER_ERROR",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(),
        )

    application.include_router(router)
    return application


app = create_app()
