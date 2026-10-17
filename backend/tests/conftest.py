"""Shared pytest fixtures for Prism Lens backend tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Set test env BEFORE any app imports so the settings singleton picks them up.
os.environ.setdefault("DEV_MODE", "true")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_prism.db")
os.environ.setdefault("LLM_API_KEY", "")


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Create a bare plugin directory for test fixtures."""
    d = tmp_path / "my-plugin"
    d.mkdir()
    return d


@pytest.fixture
def engine():
    """ValidationEngine instance."""
    from backend.app.services.validator import ValidationEngine

    return ValidationEngine()


@pytest.fixture
def client():
    """FastAPI TestClient with DEV_MODE auth and test DB.

    The lifespan creates tables on enter.  Tests are expected to use
    unique plugin names or clean up their own data.
    """
    from fastapi.testclient import TestClient

    from backend.app.core.security import UserContext, get_current_user
    from backend.app.main import app

    app.dependency_overrides[get_current_user] = lambda: UserContext(
        sub="test-user", role="admin", name="Test User"
    )

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def clean_reports(client):
    """Delete all existing reports and checks for a clean slate."""
    import asyncio
    from backend.app.db.database import AsyncSessionLocal
    from backend.app.models.orm import CheckRecord, Report

    async def _clear():
        async with AsyncSessionLocal() as session:
            await session.execute(CheckRecord.__table__.delete())
            await session.execute(Report.__table__.delete())
            await session.commit()

    try:
        asyncio.run(_clear())
    except Exception:
        pass
    yield