"""
Application lifespan events.

Runs once at startup (cache warm-up, connection checks) and once at
shutdown (graceful cleanup). Kept separate from the app factory so the
factory stays declarative.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.caching import initialize_semantic_cache

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup → serve → shutdown."""
    logger.info("Starting %s v%s (%s)", app.title, app.version, "app")
    initialize_semantic_cache()
    try:
        yield
    finally:
        logger.info("Shutting down %s", app.title)
