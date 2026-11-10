# Changelog

## 1.3.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

### Added
- **Enhanced MCP validation** (`backend/app/services/checks.py`): Transport-specific
  validation for `stdio`, `sse`, and `http` transports with required field checks
  (command for stdio, URL for sse/http). Environment variable placeholder
  validation across all transport fields. OAuth configuration validation
  including auth type and scopes format. Server-type heuristics: Gmail servers
  validated for `gmail.settings.basic` scope, GitHub servers warned if missing
  authentication. Command availability warning for non-builtin stdio commands.

### Changed
- **Improved Gmail scope check** (`backend/app/services/checks.py`): The
  `check_mcp` function now searches for Gmail settings references specifically
  in MCP server configurations (command, args, url, env) and verifies the
  required `gmail.settings.basic` OAuth scope in the server's `auth` or `oauth`
  configuration section. This reduces false positives from the previous raw-JSON
  string search (issue #385).
## 1.1.0 — work-in-progress checkpoint
 
Partial code published for continued development. Known issues: STATUS.md.
 
### Changed
- **Improved Gmail scope check** (`backend/app/services/checks.py`): The
  `check_mcp` function now searches for Gmail settings references specifically
  in MCP server configurations (command, args, url, env) and verifies the
  required `gmail.settings.basic` OAuth scope in the server's `auth` or `oauth`
  configuration section. This reduces false positives from the previous raw-JSON
  string search (issue #385).
 
## 1.0.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

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

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
