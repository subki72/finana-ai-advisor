"""Integration tests for Finana FastAPI microservice endpoints and middleware."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from src.api import SlidingWindowRateLimiter, create_app
from src.config import Settings


class _MockGroqApiClient:
    """Mock Groq client injected into FastAPI app state for offline API tests."""

    def __init__(self, reply_text: str = "Allocate 50% needs, 30% wants, 20% savings.") -> None:
        self._reply_text = reply_text
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model: str, messages: list[dict[str, str]]) -> object:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._reply_text))])


def test_health_endpoint_reports_liveness_and_security_headers() -> None:
    """Verify GET /health succeeds without API key and attaches defensive headers."""
    # Arrange
    settings = Settings(groq_api_key="", allowed_origins=("http://localhost:8501",))
    app = create_app(settings=settings)
    client = TestClient(app)

    # Act
    response = client.get("/health", headers={"Origin": "http://localhost:8501"})

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "finana-ai-advisor"
    assert body["llm_configured"] is False
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["access-control-allow-origin"] == "http://localhost:8501"


def test_budget_and_emergency_endpoints_return_deterministic_calculations() -> None:
    """Verify POST /api/v1/budget and POST /api/v1/emergency-fund payloads."""
    # Arrange
    app = create_app(settings=Settings())
    client = TestClient(app)

    # Act
    budget_res = client.post("/api/v1/budget", json={"monthly_income": 10_000_000})
    fund_res = client.post(
        "/api/v1/emergency-fund",
        json={"monthly_expenses": 4_000_000, "dependents": 1, "income_stability": "variable"},
    )

    # Assert
    assert budget_res.status_code == 200
    assert budget_res.json()["needs"] == 5_000_000.0
    assert budget_res.json()["wants"] == 3_000_000.0
    assert budget_res.json()["savings"] == 2_000_000.0

    assert fund_res.status_code == 200
    assert fund_res.json()["recommended_months"] == 8
    assert fund_res.json()["recommended_target"] == 32_000_000.0


def test_mortgage_endpoint_and_validation_422_handling() -> None:
    """Verify mortgage calculation output and 422 responses on malformed input."""
    # Arrange
    app = create_app(settings=Settings())
    client = TestClient(app)

    # Act
    valid_res = client.post(
        "/api/v1/mortgage",
        json={
            "monthly_income": 20_000_000,
            "existing_monthly_debt": 500_000,
            "principal": 400_000_000,
            "annual_rate_pct": 6.0,
            "tenure_years": 15,
        },
    )
    invalid_res = client.post(
        "/api/v1/mortgage",
        json={
            "monthly_income": -100,
            "existing_monthly_debt": 0,
            "principal": 400_000_000,
            "annual_rate_pct": 6.0,
            "tenure_years": 0,
        },
    )

    # Assert
    assert valid_res.status_code == 200
    assert valid_res.json()["verdict"] == "affordable"
    assert valid_res.json()["dsr_pct"] <= 30.0
    assert invalid_res.status_code == 422


def test_chat_endpoint_with_mocked_client_and_unconfigured_503() -> None:
    """Verify mocked /api/v1/chat succeeds and unconfigured server returns safe 503."""
    # Arrange
    configured_app = create_app(
        settings=Settings(groq_api_key="dummy-mock-test-key"),
        llm_client=_MockGroqApiClient(),
    )
    unconfigured_app = create_app(settings=Settings(groq_api_key=""))

    # Act
    ok_res = TestClient(configured_app).post(
        "/api/v1/chat",
        json={"message": "My income is 8M, how should I budget?"},
    )
    blank_res = TestClient(configured_app).post("/api/v1/chat", json={"message": "   "})
    unavailable_res = TestClient(unconfigured_app).post(
        "/api/v1/chat",
        json={"message": "Help me budget"},
    )

    # Assert
    assert ok_res.status_code == 200
    assert ok_res.json()["status"] == "ok"
    assert "50%" in ok_res.json()["reply"]
    assert blank_res.status_code == 422
    assert unavailable_res.status_code == 503


def test_chat_endpoint_enforces_sliding_window_rate_limit_429() -> None:
    """Reject requests exceeding per-minute limit with HTTP 429 and Retry-After."""
    # Arrange
    current_time = [500.0]
    limiter = SlidingWindowRateLimiter(
        max_requests=2,
        window_seconds=60.0,
        clock=lambda: current_time[0],
    )
    app = create_app(
        settings=Settings(groq_api_key="dummy-mock-test-key", rate_limit_per_minute=2),
        llm_client=_MockGroqApiClient(),
        rate_limiter=limiter,
    )
    client = TestClient(app)
    payload = {"message": "Give me a quick savings tip"}

    # Act
    res_1 = client.post("/api/v1/chat", json=payload)
    res_2 = client.post("/api/v1/chat", json=payload)
    res_3 = client.post("/api/v1/chat", json=payload)

    # Assert rate limit enforced
    assert res_1.status_code == 200
    assert res_2.status_code == 200
    assert res_3.status_code == 429
    assert int(res_3.headers["retry-after"]) >= 1

    # Act: advance clock past sliding window -> quota resets
    current_time[0] += 61.0
    res_4 = client.post("/api/v1/chat", json=payload)
    assert res_4.status_code == 200


def test_global_exception_handler_returns_safe_500_without_leaking_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify unhandled exceptions return structured 500 JSON with zero internal leaks."""

    # Arrange
    def _boom(_income: float) -> object:
        raise RuntimeError("sensitive internal trace token-xyz")

    monkeypatch.setattr("src.api.calculate_budget_50_30_20", _boom)
    app = create_app(settings=Settings())
    client = TestClient(app, raise_server_exceptions=False)

    # Act
    response = client.post("/api/v1/budget", json={"monthly_income": 5_000_000})

    # Assert
    assert response.status_code == 500
    body = response.json()
    assert body["error_code"] == "INTERNAL_SERVER_ERROR"
    assert "sensitive internal trace" not in response.text
