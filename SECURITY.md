# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in `finana-ai-advisor`:

1. **Do NOT open a public GitHub issue** for undisclosed vulnerabilities.
2. Submit a private report via GitHub Security Advisories (`Security -> Advisories -> Report a vulnerability`).
3. Include affected file paths, line numbers, reproduction steps, and estimated impact.
4. Initial acknowledgement will be provided within **48 hours**.

## Security Controls

- **Secret Hygiene**: `.env`, `.env.*`, and private key files are excluded via `.gitignore`. `GROQ_API_KEY` is loaded lazily at request time and never committed to source control.
- **PII Protection**: User financial messages and AI responses are never logged to stdout or server logs; only non-sensitive metadata (character counts, model name, status) is logged.
- **Input Validation & Headers**: FastAPI endpoints enforce strict Pydantic v2 schema bounds, explicit CORS allowlists (`ALLOWED_ORIGINS`), security response headers, and sliding-window rate limiting on `/api/v1/chat`.
- **Automated Vulnerability Management**: Weekly Dependabot alerts (`semver-major` updates ignored for stability), Semgrep SAST, and Trivy container image scanning in CI.
- **Container Hardening**: Multi-stage non-root Docker builds (`USER appuser`, UID `10001`).
