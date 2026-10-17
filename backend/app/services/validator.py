"""Validation engine orchestrator.

Coordinates all check modules and produces a ValidationReport.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path

from backend.app.models.schemas import (
    CheckResult,
    ReportStatus,
    Severity,
    ValidationReport,
)
from backend.app.services.checks import ALL_CHECKS


class ValidationEngine:
    """Runs all registered checks against a plugin directory."""

    def __init__(self, checks: list | None = None):
        self._checks = checks or ALL_CHECKS

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def validate(
        self,
        plugin_dir: Path,
        plugin_name: str = "",
        plugin_version: str = "",
    ) -> tuple[ValidationReport, list[CheckResult]]:
        """Run all checks and return (report, all_checks).

        The report carries summary counts; the second return value is the
        full ordered list of CheckResult objects for persistence and API.
        """
        started = self._now()
        all_checks: list[CheckResult] = []

        # If we can't find the manifest, try to infer the name from the
        # directory itself so the report is still meaningful.
        if not plugin_name:
            plugin_name = plugin_dir.name

        for check_fn in self._checks:
            try:
                results = check_fn(plugin_dir)
                if results:
                    all_checks.extend(results)
            except Exception as exc:
                all_checks.append(
                    CheckResult(
                        check_id=f"{check_fn.__name__}_error",
                        category=check_fn.__name__.replace("check_", ""),
                        severity=Severity.error,
                        title=f"Check encountered an error",
                        message=f"{check_fn.__name__} raised: {type(exc).__name__}: {exc}",
                    )
                )

        completed = self._now()
        summary = {"error": 0, "warning": 0, "info": 0}
        for c in all_checks:
            summary[c.severity.value] += 1

        if summary["error"] > 0:
            status = ReportStatus.failed
        elif summary["warning"] > 0:
            status = ReportStatus.warnings
        else:
            status = ReportStatus.passed

        report_id = f"r_{secrets.token_urlsafe(10)}"
        report = ValidationReport(
            report_id=report_id,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            plugin_path=str(plugin_dir),
            status=status,
            started_at=started,
            completed_at=completed,
            checks=all_checks,
            summary=summary,
        )

        return report, all_checks


def build_text_report(report: ValidationReport) -> str:
    """Render a human-readable text report from a ValidationReport."""
    lines: list[str] = []
    lines.append(f"Prism Lens — Validation Report")
    lines.append(f"  Report ID : {report.report_id}")
    lines.append(f"  Plugin    : {report.plugin_name}"
                 + (f" v{report.plugin_version}" if report.plugin_version else ""))
    lines.append(f"  Status    : {report.status.value.upper()}")
    lines.append(f"  Started   : {report.started_at.isoformat()}")
    lines.append(f"  Completed : {report.completed_at.isoformat() if report.completed_at else '—'}")
    lines.append(f"  Summary   : {summary_bar(report.summary)}")
    lines.append("")

    # Group by category
    by_category: dict[str, list[CheckResult]] = {}
    for c in report.checks:
        by_category.setdefault(c.category, []).append(c)

    for category in sorted(by_category):
        checks = by_category[category]
        lines.append(f"── {category.upper()} ──")
        for c in checks:
            icon = _severity_icon(c.severity)
            loc = f" ({c.file_path}"
            if c.line:
                loc += f":{c.line}"
            loc += ")" if c.file_path else ")"
            lines.append(f"  [{icon}] {c.title}{loc}")
            for wrapped in _wrap(c.message, indent=6):
                lines.append(f"    {wrapped}")
        lines.append("")

    if report.llm_advisory:
        lines.append("── LLM ADVISORY (advisory — not authoritative) ──")
        for wrapped in _wrap(report.llm_advisory, indent=4):
            lines.append(f"  {wrapped}")
        lines.append("")

    return "\n".join(lines)


def summary_bar(summary: dict[str, int]) -> str:
    return f"errors={summary.get('error', 0)}  " \
           f"warnings={summary.get('warning', 0)}  " \
           f"info={summary.get('info', 0)}"


def _severity_icon(sev: Severity) -> str:
    return {"error": "✗", "warning": "⚠", "info": "i"}[sev]


def _wrap(text: str, indent: int = 0) -> list[str]:
    """Naive word-wrap for text reports."""
    import textwrap

    return textwrap.wrap(text, width=90, subsequent_indent=" " * indent)