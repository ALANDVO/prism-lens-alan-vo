# Prism Lens API Reference

## Base URL
`http://localhost:8000`

## Health
```
GET /health
```
Returns `{"status": "healthy", "version": "1.0.0"}`.

## Plugin Validation
```
POST /api/v1/plugins/validate
Content-Type: multipart/form-data
```
Accepts a `.zip` file upload under the form field `file`. Extracts and
validates the plugin, stores the report, and returns:
```json
{"report_id": "r_xxxxxxxxxx"}
```

## Report Listing
```
GET /api/v1/reports
```
Query parameters:
- `limit` (1–100, default 20)
- `offset` (default 0)
- `status` — filter by `passed`, `warnings`, or `failed`
- `search` — substring match on plugin name or report ID

Returns a list of `ReportSummary` objects.

## Report Detail
```
GET /api/v1/reports/{report_id}
```
Returns a full `ValidationReport` including all checks.

## Export
```
GET /api/v1/reports/{report_id}/export?format=json|text
```
Returns the report as JSON or plain text.

## LLM Advisory
```
POST /api/v1/reports/{report_id}/advisory
```
Requires `LLM_API_KEY` to be configured. Returns the updated report
with `llm_advisory` populated. Returns 503 if no key is configured.

## Response Schemas

### CheckResult
```json
{
  "check_id": "manifest_name_invalid",
  "category": "manifest",
  "severity": "error",
  "title": "Plugin name does not conform to identifier rules",
  "message": "...",
  "file_path": ".cursor-plugin/plugin.json",
  "line": null
}
```

### ValidationReport
```json
{
  "report_id": "r_xxxxxxxxxx",
  "plugin_name": "my-plugin",
  "plugin_version": "1.0.0",
  "status": "failed",
  "started_at": "2025-01-01T00:00:00+00:00",
  "completed_at": "2025-01-01T00:00:01+00:00",
  "checks": [...],
  "summary": {"error": 2, "warning": 1, "info": 0},
  "llm_advisory": null
}
```