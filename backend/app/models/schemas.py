"""Pydantic schemas for API request and response bodies."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ReportStatus(str, Enum):
    passed = "passed"
    warnings = "warnings"
    failed = "failed"


class CheckResult(BaseModel):
    check_id: str = Field(..., description="Stable identifier for the check")
    category: str = Field(..., description="Check category (manifest, skills, …)")
    severity: Severity = Field(..., description="error | warning | info")
    title: str = Field(..., description="Short human-readable title")
    message: str = Field(..., description="Detailed explanation")
    file_path: Optional[str] = Field(default=None, description="Relative path")
    line: Optional[int] = Field(default=None, description="Line number if applicable")


class ValidationReport(BaseModel):
    report_id: str = Field(..., description="Unique report identifier")
    plugin_name: str = Field(..., description="Plugin name from manifest")
    plugin_version: Optional[str] = Field(default=None)
    plugin_path: Optional[str] = Field(default=None)
    status: ReportStatus = Field(..., description="passed | warnings | failed")
    started_at: datetime = Field(...)
    completed_at: Optional[datetime] = Field(default=None)
    checks: list[CheckResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    llm_advisory: Optional[str] = Field(default=None)


class ValidateResponse(BaseModel):
    report_id: str


class ReportSummary(BaseModel):
    report_id: str
    plugin_name: str
    plugin_version: Optional[str] = None
    status: ReportStatus
    started_at: datetime
    error_count: int
    warning_count: int
    info_count: int