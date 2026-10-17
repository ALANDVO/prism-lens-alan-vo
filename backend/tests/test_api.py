"""Integration tests for the REST API.

Tests cross the real HTTP boundary via TestClient + TestApp. Covers:
validate endpoint, report listing/retrieval, export (JSON + text), and
advisory (disabled without LLM key).
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.app.models.schemas import Severity
from backend.app.models.orm import Report, CheckRecord


def _make_plugin_zip(plugin_dir: Path, zip_path: Path) -> Path:
    """Create a zip archive of a plugin directory."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os_walk(plugin_dir):
            for name in files:
                filepath = Path(root) / name
                arcname = filepath.relative_to(plugin_dir.parent)
                zf.write(filepath, arcname)
    return zip_path


def os_walk(path: Path):
    import os

    return os.walk(path)


def _make_valid_plugin(tmp_path: Path) -> Path:
    """Create a valid plugin directory and return its path."""
    plugin = tmp_path / "valid-plugin"
    plugin.mkdir()
    (plugin / ".cursor-plugin").mkdir(parents=True, exist_ok=True)

    (plugin / ".cursor-plugin" / "plugin.json").write_text(json.dumps({
        "name": "valid-plugin",
        "version": "1.0.0",
        "description": "A valid test plugin",
    }))
    (plugin / ".cursor-plugin" / "marketplace.json").write_text(
        json.dumps({"name": "valid-plugin"})
    )

    skill_dir = plugin / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: A test skill\n---\n\nBody\n"
    )
    (skill_dir / "README.md").write_text("# My Skill")
    return plugin


def _make_broken_plugin(tmp_path: Path) -> Path:
    """Create a plugin with validation errors."""
    plugin = tmp_path / "broken"
    plugin.mkdir()
    (plugin / ".cursor-plugin").mkdir(parents=True, exist_ok=True)
    # Invalid name (capital letters, space)
    (plugin / ".cursor-plugin" / "plugin.json").write_text(json.dumps({
        "name": "Broken Plugin",
        "version": "1.0.0",
        "description": "Broken",
    }))
    # Skill with name mismatch
    skill_dir = plugin / "skills" / "poteto-mode"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Poteto Mode\ndescription: Broken skill\n---\n\nBody\n"
    )
    return plugin


class TestValidateEndpoint:
    def test_validate_valid_plugin(self, client, clean_reports, tmp_path):
        """Upload a valid plugin and get back a report_id."""
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")

        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)

        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
        assert data["report_id"].startswith("r_")

    def test_validate_broken_plugin(self, client, clean_reports, tmp_path):
        """Upload a broken plugin and verify errors are in the report."""
        plugin = _make_broken_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "broken.zip")

        with open(zip_path, "rb") as f:
            files = {"file": ("broken.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)

        assert resp.status_code == 200
        report_id = resp.json()["report_id"]

        # Fetch the report
        resp = client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 200
        report = resp.json()
        assert report["status"] == "failed"
        severities = [c["severity"] for c in report["checks"]]
        assert "error" in severities

    def test_validate_invalid_file_type(self, client, clean_reports, tmp_path):
        """Non-zip uploads should be rejected."""
        files = {"file": ("plugin.txt", io.BytesIO(b"hello"), "text/plain")}
        resp = client.post("/api/v1/plugins/validate", files=files)
        assert resp.status_code == 400

    def test_validate_invalid_zip(self, client, clean_reports, tmp_path):
        """A file claiming to be zip but not actually zip."""
        files = {"file": ("bad.zip", io.BytesIO(b"not a zip"), "application/zip")}
        resp = client.post("/api/v1/plugins/validate", files=files)
        assert resp.status_code == 400


class TestReportListing:
    def test_list_reports_empty(self, client, clean_reports):
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_reports_after_validate(self, client, clean_reports, tmp_path):
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")

        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            client.post("/api/v1/plugins/validate", files=files)

        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        reports = resp.json()
        assert len(reports) >= 1
        assert reports[0]["plugin_name"] == "valid-plugin"

    def test_list_reports_filtered_by_status(self, client, clean_reports, tmp_path):
        """Filter reports by status."""
        broken = _make_broken_plugin(tmp_path)
        zip_path = _make_plugin_zip(broken, tmp_path / "broken.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("broken.zip", f, "application/zip")}
            client.post("/api/v1/plugins/validate", files=files)

        resp = client.get("/api/v1/reports?status=failed")
        assert resp.status_code == 200
        reports = resp.json()
        assert all(r["status"] == "failed" for r in reports)

    def test_list_reports_search(self, client, clean_reports, tmp_path):
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            client.post("/api/v1/plugins/validate", files=files)

        resp = client.get("/api/v1/reports?search=valid")
        assert resp.status_code == 200
        reports = resp.json()
        assert all("valid" in r["plugin_name"] for r in reports)


class TestReportDetail:
    def test_get_report(self, client, clean_reports, tmp_path):
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)

        report_id = resp.json()["report_id"]
        resp = client.get(f"/api/v1/reports/{report_id}")
        assert resp.status_code == 200
        report = resp.json()
        assert report["report_id"] == report_id
        assert report["plugin_name"] == "valid-plugin"
        assert "checks" in report
        assert "summary" in report

    def test_get_report_not_found(self, client, clean_reports):
        resp = client.get("/api/v1/reports/r_nonexistent")
        assert resp.status_code == 404


class TestExport:
    def _create_report(self, client, tmp_path, clean_reports):
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)
        return resp.json()["report_id"]

    def test_export_json(self, client, clean_reports, tmp_path):
        report_id = self._create_report(client, tmp_path, clean_reports)
        resp = client.get(f"/api/v1/reports/{report_id}/export?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_id"] == report_id
        assert "checks" in data

    def test_export_text(self, client, clean_reports, tmp_path):
        report_id = self._create_report(client, tmp_path, clean_reports)
        resp = client.get(f"/api/v1/reports/{report_id}/export?format=text")
        assert resp.status_code == 200
        assert "Prism Lens" in resp.text
        assert "Validation Report" in resp.text
        assert "Summary" in resp.text

    def test_export_invalid_format(self, client, clean_reports, tmp_path):
        report_id = self._create_report(client, tmp_path, clean_reports)
        resp = client.get(f"/api/v1/reports/{report_id}/export?format=xml")
        assert resp.status_code == 422


class TestAdvisory:
    def test_advisory_without_key_returns_503(self, client, clean_reports, tmp_path):
        """LLM advisory should return 503 when LLM_API_KEY is not set."""
        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)

        report_id = resp.json()["report_id"]
        resp = client.post(f"/api/v1/reports/{report_id}/advisory")
        assert resp.status_code == 503
        assert "LLM" in resp.json()["detail"] or "not configured" in resp.json()["detail"].lower()

    def test_advisory_persists(self, client, clean_reports, tmp_path):
        """After advisory is generated, it should be stored."""
        import unittest.mock as mock
        from backend.app.services.llm import generate_advisory

        plugin = _make_valid_plugin(tmp_path)
        zip_path = _make_plugin_zip(plugin, tmp_path / "plugin.zip")
        with open(zip_path, "rb") as f:
            files = {"file": ("plugin.zip", f, "application/zip")}
            resp = client.post("/api/v1/plugins/validate", files=files)

        report_id = resp.json()["report_id"]

        # Set a fake key and mock the LLM call
        import backend.app.core.config as config_module

        original = config_module.settings.llm_api_key
        config_module.settings.__dict__["llm_api_key"] = "test-key"

        try:
            with mock.patch(
                "backend.app.api.reports.generate_advisory",
                return_value="The plugin passed all deterministic checks.",
            ):
                resp = client.post(f"/api/v1/reports/{report_id}/advisory")
            assert resp.status_code == 200
            assert resp.json()["llm_advisory"] is not None
            assert "passed" in resp.json()["llm_advisory"].lower()
        finally:
            config_module.settings.__dict__["llm_api_key"] = original

        # Reload and verify it was persisted
        resp = client.get(f"/api/v1/reports/{report_id}")
        assert resp.json()["llm_advisory"] is not None


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_root_redirect(self, client):
        resp = client.get("/")
        assert resp.status_code in (200, 307)