"""
Health & liveness endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health_check():
    """Basic health check for uptime monitors and Kubernetes probes."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
    }
