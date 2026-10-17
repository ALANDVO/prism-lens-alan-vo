# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

docker-compose-ci

## Roadmap

### plugin-validation-engine — Plugin validation engine

Status: done

Acceptance:
- Upload a plugin zip archive and run all validation checks
- Checks cover manifest, skills, agents, hooks, mcp, path existence, symlinks, and OAuth config
- Report has severity-filterable results grouped by category
- Deterministic: no LLM key required for offline validation

Implementation: `backend/app/services/checks.py`, `backend/app/services/validator.py`, `backend/app/services/archiver.py`

Tests: `backend/tests/test_checks.py`, `backend/tests/test_validator.py`

### plugin-api — Plugin validation REST API

Status: done

Acceptance:
- POST /api/v1/plugins/validate accepts an archive and returns a report ID
- GET /api/v1/reports lists reports with pagination and filtering
- GET /api/v1/reports/{id} returns a full report
- GET /api/v1/reports/{id}/export returns report as JSON or text

Implementation: `backend/app/api/plugins.py`, `backend/app/api/reports.py`

Tests: `backend/tests/test_api.py`

### report-persistence — SQLite persistence and audit log

Status: done

Acceptance:
- Reports and checks stored in SQLite with UTC timestamps
- Audit log records all validation actions
- Pagination and filtering on report listing

Implementation: `backend/app/db/database.py`, `backend/app/models/orm.py`

Tests: `backend/tests/test_api.py`

### llm-advisory — Opt-in LLM advisory explanations

Status: done

Acceptance:
- POST /api/v1/reports/{id}/advisory generates natural-language explanation
- Supports OpenAI-compatible, Anthropic, Gemini, Ollama providers
- Errors are clear and redacted when no key or provider failure
- Advisory is labeled as advisory, grounded in actual report records

Implementation: `backend/app/services/llm.py`, `backend/app/api/reports.py`

Tests: `backend/tests/test_llm.py`

### frontend-dashboard — React dashboard with validate/detail/export workflows

Status: done

Acceptance:
- Upload a plugin archive and view validation results
- Search and filter reports
- View detailed check results with severity filtering
- Export reports as JSON or text

Implementation: `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/ValidatePage.tsx`, `frontend/src/pages/ReportDetail.tsx`, `frontend/src/components/`

Tests: `frontend/src/tests/Dashboard.test.tsx`, `frontend/src/tests/UploadForm.test.tsx`, `frontend/src/tests/ReportDetail.test.tsx`

### auth-keycloak — Keycloak OIDC authentication

Status: in_progress

Acceptance:
- OIDC authorization code with state + nonce + PKCE
- HttpOnly SameSite cookies with CSRF protection
- Roles: viewer, analyst, admin
- Realm import for SAML identity brokering

Implementation: `backend/app/core/security.py`, `keycloak/realm-export.json`

Tests: `backend/tests/test_api.py`

### docker-compose-ci — Docker, compose, CI workflow

Status: done

Acceptance:
- Dockerfiles with nonroot users
- compose.yaml with Keycloak and persistent volumes
- CI workflow testing backend and frontend

Implementation: `backend/Dockerfile`, `frontend/Dockerfile`, `compose.yaml`, `.github/workflows/ci.yml`

