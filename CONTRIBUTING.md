# Contributing to Finana AI Advisor

Thank you for contributing to `finana-ai-advisor`. Please follow these engineering guidelines so pull requests pass CI cleanly on the first attempt.

## Local Development Setup

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .\.venv\Scripts\activate
pip install -r requirements.txt
pip install ruff flake8
cp .env.example .env
```

## Engineering Standards

1. **Pure Domain Logic & DI**: Keep deterministic math in `src/calculators.py` free of framework/network side effects, and inject external clients via `get_groq_client()` or FastAPI `Depends(...)`.
2. **No PII in Logs**: Never log raw user financial narratives, API keys, or complete assistant replies. Log only safe metadata (character counts, model identifier, status).
3. **Code Hygiene**:
   - Functions under 50 lines, shallow nesting (`< 3`), explicit type annotations, and Google-style docstrings.
   - Never swallow exceptions (`except: pass`). Catch explicit exception classes and return sanitized errors externally.
4. **Verification Gate Before Commit**:
   ```bash
   make lint
   make test
   ```
   All Ruff checks, Ruff formatting checks, Flake8 checks, and offline Pytest assertions (including >= 75% coverage) must pass without requiring a live `GROQ_API_KEY`.

## Commit & Pull Request Convention

- Use Conventional Commits (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `ci:`).
- Ensure `.env` and local credentials are never staged (`git status`).
- Document breaking API or configuration changes in `CHANGELOG.md`.
