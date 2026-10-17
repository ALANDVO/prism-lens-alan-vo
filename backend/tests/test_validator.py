"""Tests for the ValidationEngine orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.models.schemas import (
    CheckResult,
    ReportStatus,
    Severity,
    ValidationReport,
)
from backend.app.services.validator import (
    ValidationEngine,
    build_text_report,
    summary_bar,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_valid_manifest(plugin_dir: Path, name: str = "test-plugin") -> None:
    (plugin_dir / ".cursor-plugin").mkdir(parents=True, exist_ok=True)
    _write(
        plugin_dir / ".cursor-plugin" / "plugin.json",
        json.dumps({"name": name, "version": "1.0.0", "description": "Test"}),
    )


def _make_valid_skill(plugin_dir: Path, skill_name: str = "my-skill") -> None:
    skill_dir = plugin_dir / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _write(
        skill_dir / "SKILL.md",
        f"---\nname: {skill_name}\ndescription: A skill\n---\n\nBody\n",
    )
    _write(skill_dir / "README.md", "# Readme")


class TestValidationEngine:
    def test_empty_plugin_dir(self, tmp_path: Path, engine: ValidationEngine):
        """A directory with nothing should report missing manifest."""
        plugin = tmp_path / "empty"
        plugin.mkdir()
        report, checks = engine.validate(plugin)
        assert report.status == ReportStatus.failed
        check_ids = [c.check_id for c in checks]
        assert "manifest_missing" in check_ids
        assert report.summary["error"] > 0

    def test_valid_plugin_passes(self, tmp_path: Path, engine: ValidationEngine):
        """A well-formed plugin should pass with no errors."""
        plugin = tmp_path / "valid-plugin"
        plugin.mkdir()
        _make_valid_manifest(plugin, name="valid-plugin")
        _make_valid_skill(plugin, skill_name="my-skill")

        report, checks = engine.validate(plugin, "valid-plugin", "1.0.0")
        assert report.status == ReportStatus.warnings  # marketplace.json missing
        errors = [c for c in checks if c.severity.value == "error"]
        assert len(errors) == 0
        assert report.plugin_name == "valid-plugin"
        assert report.plugin_version == "1.0.0"

    def test_broken_plugin_fails(self, tmp_path: Path, engine: ValidationEngine):
        """A plugin with multiple issues should report errors."""
        plugin = tmp_path / "broken"
        plugin.mkdir()
        _make_valid_manifest(plugin, name="Broken Plugin")  # invalid name
        _make_valid_skill(plugin, skill_name="poteto-mode")
        # Tamper skill name
        skill_md = plugin / "skills" / "poteto-mode" / "SKILL.md"
        content = skill_md.read_text()
        content = content.replace("name: poteto-mode", "name: Poteto Mode")
        skill_md.write_text(content)
        # Add an undeclared MCP variable
        _write(
            plugin / "mcp.json",
            json.dumps({
                "mcpServers": {"srv": {"command": "echo", "env": {"X": "${MISSING}"}}},
                "variables": {},
            }),
        )

        report, checks = engine.validate(plugin, "Broken Plugin", "1.0.0")
        assert report.status == ReportStatus.failed
        check_ids = [c.check_id for c in checks]
        assert "manifest_name_invalid" in check_ids
        assert "skill_name_mismatch" in check_ids
        assert "mcp_undeclared_variable" in check_ids
        assert report.summary["error"] >= 3

    def test_report_id_is_unique(self, tmp_path: Path, engine: ValidationEngine):
        plugin = tmp_path / "p"
        plugin.mkdir()
        _make_valid_manifest(plugin)
        report1, _ = engine.validate(plugin)
        report2, _ = engine.validate(plugin)
        assert report1.report_id != report2.report_id

    def test_status_warnings(self, tmp_path: Path, engine: ValidationEngine):
        """Plugin with only warnings should have warnings status."""
        plugin = tmp_path / "warnings"
        plugin.mkdir()
        _make_valid_manifest(plugin)
        # No skills directory — generates a warning, not an error
        report, checks = engine.validate(plugin)
        assert report.status == ReportStatus.warnings

    def test_status_passed(self, tmp_path: Path, engine: ValidationEngine):
        """Plugin with no issues at all."""
        plugin = tmp_path / "perfect"
        plugin.mkdir()
        _make_valid_manifest(plugin, name="perfect")
        # Add marketplace.json to avoid the warning
        (plugin / ".cursor-plugin").mkdir(parents=True, exist_ok=True)
        _write(plugin / ".cursor-plugin" / "marketplace.json", json.dumps({"name": "perfect"}))
        # Add a valid skill to avoid the skills_dir_missing warning
        _make_valid_skill(plugin, "my-skill")
        report, checks = engine.validate(plugin, "perfect", "1.0.0")
        assert report.status == ReportStatus.passed
        assert report.summary["error"] == 0
        assert report.summary["warning"] == 0

    def test_custom_checks(self, tmp_path: Path):
        """Engine accepts a custom check list."""
        plugin = tmp_path / "custom"
        plugin.mkdir()

        def custom_check(d: Path):
            return [
                CheckResult(
                    check_id="custom",
                    category="test",
                    severity=Severity.info,
                    title="Custom check ran",
                    message="OK",
                )
            ]

        engine = ValidationEngine(checks=[custom_check])
        report, checks = engine.validate(plugin)
        assert any(c.check_id == "custom" for c in checks)

    def test_check_raises_is_caught(self, tmp_path: Path):
        """A check that raises should produce an error result, not crash."""

        def bad_check(d: Path):
            raise RuntimeError("boom")

        engine = ValidationEngine(checks=[bad_check])
        plugin = tmp_path / "p"
        plugin.mkdir()
        report, checks = engine.validate(plugin)
        assert any(c.severity == Severity.error for c in checks)
        assert report.status == ReportStatus.failed



class TestTextReport:
    def test_text_report_contains_sections(self, tmp_path: Path, engine: ValidationEngine):
        plugin = tmp_path / "p"
        plugin.mkdir()
        report, _ = engine.validate(plugin, "p", "1.0.0")
        text = build_text_report(report)
        assert "Prism Lens" in text
        assert "Validation Report" in text
        assert "p" in text
        assert "Summary" in text
        assert "MANIFEST" in text

    def test_summary_bar(self):
        bar = summary_bar({"error": 2, "warning": 3, "info": 1})
        assert "errors=2" in bar
        assert "warnings=3" in bar
        assert "info=1" in bar

    def test_text_report_with_advisory(self):
        check = CheckResult(
            check_id="test",
            category="manifest",
            severity=Severity.error,
            title="Test error",
            message="This is a test error message",
        )
        report = ValidationReport(
            report_id="r_test",
            plugin_name="test",
            status=ReportStatus.failed,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            checks=[check],
            summary={"error": 1, "warning": 0, "info": 0},
            llm_advisory="This plugin has issues.",
        )
        text = build_text_report(report)
        assert "LLM ADVISORY" in text
        assert "This plugin has issues." in text