# Changelog

All notable changes to `finana-ai-advisor` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-24

### Added
- Centralized validated `Settings` configuration (`src/config.py`), `.env.example`, and structured single-line JSON logging (`configure_logging`).
- Pure deterministic personal finance calculators (`src/calculators.py`): 50/30/20 budgeting, 3-12 month emergency fund sizing, and mortgage affordability/DSR evaluation.
- Strict Pydantic v2 API contracts (`src/schemas.py`) for health, budget, emergency fund, mortgage, and chat endpoints.
- Production FastAPI microservice gateway (`src/api.py`) featuring `GET /health`, `POST /api/v1/budget`, `POST /api/v1/emergency-fund`, `POST /api/v1/mortgage`, and rate-limited `POST /api/v1/chat`, plus CORS allowlists, security response headers, and centralized 500 error boundary.
- Thread-safe `CircuitBreaker` and `SlidingWindowRateLimiter` protecting upstream Groq calls.
- Five offline Pytest suites (`tests/`) covering calculators, config, schemas, mocked chatbot resilience, and FastAPI integration tests.
- Multi-stage non-root `Dockerfile`, `docker-compose.yml`, `Makefile`, `pyproject.toml`, `.flake8`, `.pre-commit-config.yaml`, GitHub Actions CI pipeline (Ruff, Flake8, Pytest, Semgrep, Docker, Trivy, tag release), Dependabot, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and `docs/RUNBOOK.md`.

### Changed
- Eliminated import-time `ValueError` crash and eager `Groq()` instantiation in `src/chatbot.py` in favor of lazy dependency injection (`get_groq_client`) with explicit network timeout (`REQUEST_TIMEOUT_SECONDS`).
- Replaced raw `print()` calls in `src/chatbot.py` with PII-safe metadata logging (`message_chars`, `reply_chars`, `model`) and sanitized external fallback messages.
- Refactored `src/main.py` Streamlit UI into modular functions under 50 lines with sidebar 50/30/20 quick calculator integration while keeping `streamlit run src/main.py` compatibility.
- Pinned exact PyPI versions in `requirements.txt`, `requirements-lock.txt`, and `uv.lock`.
