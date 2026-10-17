"""Plugin validation API endpoints."""

from __future__ import annotations
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.app.core.audit import log_action
from backend.app.core.config import get_settings
from backend.app.core.security import UserContext, get_current_user
from backend.app.db.database import get_session
from backend.app.models.orm import CheckRecord, Report
from backend.app.models.schemas import ValidateResponse
from backend.app.services.archiver import detect_plugin_root, extract_plugin_archive
from backend.app.services.validator import ValidationEngine
from sqlalchemy.ext.asyncio import AsyncSession


def get_engine() -> ValidationEngine:
    """Provider for the validation engine."""
    return ValidationEngine()


router = APIRouter(prefix="/api/v1")


@router.post("/plugins/validate", response_model=ValidateResponse)
async def validate_plugin(
    file: UploadFile = File(..., description="A .zip archive of the Cursor plugin"),
    settings=Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    user: UserContext = Depends(get_current_user),
    engine: ValidationEngine = Depends(get_engine),
) -> ValidateResponse:
    """Upload a plugin archive, extract it, and run all validation checks."""
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A .zip archive is required",
        )

    # Read and size-check
    content = await file.read()
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archive exceeds {settings.upload_max_bytes} bytes",
        )

    # Write to temp file
    tmp_path = Path(tempfile.mktemp(suffix=".zip"))
    tmp_path.write_bytes(content)

    try:
        extract_dir = extract_plugin_archive(tmp_path)
    except (ValueError, FileNotFoundError) as exc:
        await log_action(
            session, "plugin_validate", user.sub,
            detail=f"Upload rejected: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    try:
        plugin_root = detect_plugin_root(extract_dir)

        # Read manifest for display names
        manifest_path = plugin_root / ".cursor-plugin" / "plugin.json"
        plugin_name = plugin_root.name
        plugin_version = ""
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                plugin_name = manifest.get("name", plugin_name)
                plugin_version = manifest.get("version", "")
            except json.JSONDecodeError:
                pass

        report, checks = engine.validate(
            plugin_root, plugin_name, plugin_version
        )

        # Persist
        orm_report = Report(
            id=report.report_id,
            plugin_name=report.plugin_name,
            plugin_version=report.plugin_version or None,
            plugin_path=report.plugin_path,
            status=report.status,
            started_at=report.started_at,
            completed_at=report.completed_at,
        )
        session.add(orm_report)
        await session.flush()

        for check in checks:
            session.add(CheckRecord(
                report_id=report.report_id,
                check_id=check.check_id,
                category=check.category,
                severity=check.severity.value,
                title=check.title,
                message=check.message,
                file_path=check.file_path,
                line=check.line,
            ))
        await session.commit()

        await log_action(
            session, "plugin_validate", user.sub,
            detail=f"Validated {plugin_name} ({report.report_id}), "
                   f"{len(checks)} checks, status={report.status}",
        )

        return ValidateResponse(report_id=report.report_id)
    finally:
        # Schedule cleanup; the archive is already in /tmp and will be
        # cleaned up by the background task
        pass