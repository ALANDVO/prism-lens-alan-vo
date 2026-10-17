"""Audit logging for security-sensitive actions."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from backend.app.models.orm import AuditEntry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("prism_lens.audit")


async def log_action(
    session: "AsyncSession",
    action: str,
    actor: Optional[str] = None,
    detail: Optional[str] = None,
) -> AuditEntry:
    """Insert an audit entry and commit it."""
    entry = AuditEntry(
        action=action,
        actor=actor or "system",
        detail=detail,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    logger.info("AUDIT %s actor=%s", action, actor or "system")
    return entry