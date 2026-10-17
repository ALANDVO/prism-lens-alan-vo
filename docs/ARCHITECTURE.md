# Prism Lens Architecture

## Overview

Prism Lens is a full-stack application (FastAPI backend + React frontend) that
validates Cursor plugin archives against the Agent Skills specification and
produces diagnostic reports explaining why plugins fail to load.

## Backend (FastAPI)

### Request flow
1. Client uploads a `.zip` archive via `POST /api/v1/plugins/validate`.
2. `archiver.py` extracts the zip (zip-slip protection, size limits).
3. `validator.py` runs all check functions from `checks.py`.
4. Results are persisted to SQLite via SQLAlchemy ORM.
5. Client retrieves reports via `GET /api/v1/reports/{id}`.
6. LLM advisory is an opt-in `POST /api/v1/reports/{id}/advisory` that calls
   `llm.py` with mocked-friendly interface.

### Check engine
Each check function in `checks.py` is a pure function: `(plugin_dir: Path) →
list[CheckResult]`. The `ValidationEngine` orchestrates them, catching
exceptions so a single check failure doesn't abort the entire run.

### Data model
- `Report` — one row per validation run (status, timestamps, counts, LLM advisory).
- `CheckRecord` — one row per individual finding (category, severity, title,
  message, file path, line number).
- `AuditEntry` — audit log of all API actions (actor, action, detail).

### Authentication
- **Dev mode** (`DEV_MODE=true`): demo admin user, localhost only.
- **Production**: Keycloak OIDC authorization code with state + nonce + PKCE.
  Token validation, cookie management, and role enforcement are scaffolded in
  `security.py` but not yet connected end-to-end (see STATUS.md).

## Frontend (React + Vite)

### Architecture
- `api/client.ts` — typed client wrapping `fetch`, mirrors backend API shapes.
- `types/index.ts` — TypeScript interfaces derived from Pydantic schemas.
- `pages/` — route-level components (Dashboard, Validate, ReportDetail).
- `components/` — reusable UI primitives (CheckList, SeverityBadge, etc.).

### State management
No external state manager — React component state + props. The backend is the
single source of truth; reports are fetched on demand.

## Docker & Deployment

`compose.yaml` orchestrates:
- `backend` — FastAPI, exposed on `127.0.0.1:8000`
- `frontend` — nginx, exposed on `127.0.0.1:5173`
- `keycloak` — OIDC provider, exposed on `127.0.0.1:8080`
- `db` — PostgreSQL for Keycloak

## Security considerations
- No API keys, credentials, or secrets committed.
- LLM keys only on server; never sent to the frontend.
- Dev mode binds to 127.0.0.1 only.
- Archive extraction includes zip-slip protection.
- Audit log records all validation and advisory actions.