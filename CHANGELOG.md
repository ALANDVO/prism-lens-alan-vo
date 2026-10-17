# Changelog

## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.0.0 — 2025-01-01

### Added
- **Validation engine** (`backend/app/services/checks.py`): 8 deterministic
  check modules covering manifest, skills, agents, hooks, MCP servers, path
  existence, symlinks, and OAuth configuration. Checks are derived from
  Cursor plugin issue analysis (#237, #35, #251, #278, #385, #472, #531).
- **Validation engine orchestrator** (`backend/app/services/validator.py`):
  runs all checks, produces a `ValidationReport` with severity summary, and
  generates a human-readable text report.
- **Archive extraction** (`backend/app/services/archiver.py`): extracts `.zip`
  plugin archives with zip-slip protection.
- **Opt-in LLM advisory** (`backend/app/services/llm.py`): supports OpenAI
  compatible, Anthropic, Gemini, and Ollama providers via httpx. Bounded
  timeouts, redacted errors, grounded in actual check results.
- **REST API** (`backend/app/api/`): validate, list, detail, export, and
  advisory endpoints with pagination, filtering, and search.
- **SQLite persistence** (`backend/app/db/`, `backend/app/models/orm.py`):
  stores reports, individual check records, and an audit log with UTC
  timestamps.
- **Authentication scaffolding** (`backend/app/core/security.py`): dev-mode
  demo auth (localhost only) and Keycloak OIDC architecture.
- **Frontend dashboard** (`frontend/src/`): React + TypeScript + Vite with
  upload form, report dashboard, detailed report view, severity/category
  filtering, text/JSON export, and LLM advisory request.
- **Docker support**: backend and frontend Dockerfiles with nonroot users,
  `compose.yaml` with Keycloak and PostgreSQL, `.env.example`.
- **CI workflow**: backend tests, frontend typecheck/build/test, Docker
  image builds via `setup-buildx-action`.
- **Documentation**: README with architecture diagram, API reference, AI/ML
  evaluation section, provider configuration table, and SSO/SAML setup.

### Tests
- 72 backend tests (checks, engine, API integration, LLM mocking)
- 9 frontend tests (Dashboard, UploadForm, ReportDetail)