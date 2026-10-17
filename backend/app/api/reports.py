"""Report retrieval, export, and LLM advisory API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.app.core.audit import log_action
from backend.app.core.config import get_settings
from backend.app.core.security import UserContext, get_current_user
from backend.app.db.database import get_session
from backend.app.models.orm import CheckRecord, Report
from backend.app.models.schemas import (
    ReportSummary,
    Severity,
    ValidationReport,
    CheckResult,
)
from backend.app.services.llm import LLMConfig, LLMNotConfiguredError, LLMProviderError, generate_advisory
from backend.app.services.validator import build_text_report
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1")


def _orm_to_report(orm_report: Report) -> ValidationReport:
    """Convert an ORM report to the response schema."""
    checks = [
        CheckResult(
            check_id=c.check_id,
            category=c.category,
            severity=c.severity,
            title=c.title,
            message=c.message,
            file_path=c.file_path,
            line=c.line,
        )
        for c in orm_report.checks
    ]
    summary = orm_report.summary
    return ValidationReport(
        report_id=orm_report.id,
        plugin_name=orm_report.plugin_name,
        plugin_version=orm_report.plugin_version,
        plugin_path=orm_report.plugin_path,
        status=orm_report.status,
        started_at=orm_report.started_at,
        completed_at=orm_report.completed_at,
        checks=checks,
        summary=summary,
        llm_advisory=orm_report.llm_advisory,
    )


@router.get("/reports", response_model=list[ReportSummary])
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user: UserContext = Depends(get_current_user),
):
    """List validation reports with pagination, filtering, and search."""
    stmt = select(Report).order_by(Report.started_at.desc())

    if status_filter:
        stmt = stmt.where(Report.status == status_filter)

    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            func.lower(Report.plugin_name).like(func.lower(pattern))
            | (Report.id.like(pattern))
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    reports = result.scalars().all()

    summaries = []
    for r in reports:
        summaries.append(
            ReportSummary(
                report_id=r.id,
                plugin_name=r.plugin_name,
                plugin_version=r.plugin_version,
                status=r.status.value,
                started_at=r.started_at,
                error_count=r.summary.get("error", 0),
                warning_count=r.summary.get("warning", 0),
                info_count=r.summary.get("info", 0),
            )
        )
    return summaries


@router.get("/reports/{report_id}", response_model=ValidationReport)
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    user: UserContext = Depends(get_current_user),
):
    """Retrieve a full validation report."""
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )
    return _orm_to_report(report)


@router.get("/reports/{report_id}/export", response_class=PlainTextResponse)
async def export_report(
    report_id: str,
    format: str = Query(default="text", pattern="^(json|text)$"),
    session: AsyncSession = Depends(get_session),
    user: UserContext = Depends(get_current_user),
):
    """Export a report as JSON or plain text."""
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )

    schema_report = _orm_to_report(report)

    if format == "json":
        from fastapi.encoders import jsonable_encoder
        return JSONResponse(
            content=jsonable_encoder(schema_report),
            media_type="application/json",
        )
    else:
        text = build_text_report(schema_report)
        return PlainTextResponse(text, media_type="text/plain")


@router.post("/reports/{report_id}/advisory", response_model=ValidationReport)
async def request_advisory(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    user: UserContext = Depends(get_current_user),
    settings=Depends(get_settings),
):
    """Request an opt-in LLM advisory for a validation report.

    Requires LLM_API_KEY to be configured. Raises 503 if not configured.
    """
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report not found: {report_id}",
        )

    schema_report = _orm_to_report(report)

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM advisory is not configured. Set LLM_API_KEY to enable.",
        )

    config = LLMConfig(
        api_key=settings.llm_api_key,
        provider=settings.llm_provider or "openai-compatible",
        model=settings.llm_model or "gpt-4o-mini",
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )

    try:
        advisory = generate_advisory(config, schema_report)
    except LLMNotConfiguredError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured",
        )
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc}",
        )

    report.llm_advisory = advisory
    await session.commit()
    await session.refresh(report)

    await log_action(
        session, "llm_advisory", user.sub,
        detail=f"Generated advisory for report {report_id}",
    )

    return _orm_to_report(report)