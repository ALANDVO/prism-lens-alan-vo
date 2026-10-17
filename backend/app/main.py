"""Prism Lens — FastAPI application factory.

Run with:
    uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

Docker entrypoint uses the same app object.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.app.api import plugins as plugins_router
from backend.app.api import reports as reports_router
from backend.app.core.config import get_settings
from backend.app.db.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("prism_lens")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Prism Lens starting (version %s, env=%s)", settings.app_version, settings.environment)
    await init_db()
    yield
    logger.info("Prism Lens shutting down")


app = FastAPI(
    title="Prism Lens",
    description="Diagnostic tool for Cursor plugins — validates plugin "
    "structure against the Agent Skills specification and explains "
    "loading failures through deterministic static-analysis checks.",
    version=settings.app_version,
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.dev_mode else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(plugins_router.router)
app.include_router(reports_router.router)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/")
async def root():
    return RedirectResponse(url="/docs")


def create_app() -> FastAPI:
    """Application factory (documented, alternative entry point)."""
    return app