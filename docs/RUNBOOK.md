# Finana AI Advisor — Operations Runbook

## 1. Service Overview

- **Service Name**: `finana-ai-advisor`
- **Components**:
  - **FastAPI Gateway** (`src/api.py`): Port `8000` — provides `/health` liveness/readiness probe, deterministic calculators (`/api/v1/budget`, `/api/v1/emergency-fund`, `/api/v1/mortgage`), and rate-limited LLM chat (`/api/v1/chat`).
  - **Streamlit Web UI** (`src/main.py`): Port `8501` — interactive conversational interface and sidebar 50/30/20 calculator.

## 2. Health Verification

```bash
curl -fsS http://127.0.0.1:8000/health
```

Expected response (`200 OK`):

```json
{
  "status": "healthy",
  "service": "finana-ai-advisor",
  "version": "1.0.0",
  "llm_configured": true,
  "model": "llama-3.3-70b-versatile"
}
```

Note: `llm_configured: false` indicates the service is live for deterministic calculators (`/api/v1/budget`, `/api/v1/emergency-fund`, `/api/v1/mortgage`), while `/api/v1/chat` will return `503 Service Unavailable` until a valid `GROQ_API_KEY` is supplied.

## 3. Common Incidents & Triage

| Symptom | Likely Cause | Diagnostic Action | Mitigation |
|---|---|---|---|
| `/api/v1/chat` returns `503` with unconfigured message | Missing or placeholder `GROQ_API_KEY` | Check `GET /health` -> `llm_configured` | Set valid `GROQ_API_KEY` in `.env` or secret manager and restart container |
| `/api/v1/chat` returns `503` temporarily paused | Upstream Groq timeout/error tripped `CircuitBreaker` | Search JSON logs for `Circuit breaker open` or `Chat completion failed` | Wait `CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default 30s) or verify Groq API status |
| `/api/v1/chat` returns `429` | Client exceeded `RATE_LIMIT_PER_MINUTE` | Inspect `Retry-After` response header | Respect `Retry-After` backoff or adjust `RATE_LIMIT_PER_MINUTE` |
| `/api/v1/budget` or `/mortgage` returns `500` | Unexpected unhandled runtime error | Inspect structured JSON logs (`error_type` & `path`) | Roll back recent deployment (`docker compose down && git checkout <prev_tag>`) |
| Container fails `HEALTHCHECK` | Uvicorn process failed startup or wrong config | Run `docker logs <container>` for `Settings.validate` `ValueError` | Fix invalid env vars (`REQUEST_TIMEOUT_SECONDS`, `LOG_LEVEL`, `ALLOWED_ORIGINS`) |

## 4. Rollback & Recovery Procedure

1. Verify current release tag: `git describe --tags --abbrev=0`.
2. Stop unhealthy containers: `docker compose down`.
3. Check out previous verified release tag and rebuild:
   ```bash
   git checkout v1.0.0
   docker compose up -d --build
   ```
4. Confirm `/health` returns `200 OK` and execute smoke test against `/api/v1/budget`.
