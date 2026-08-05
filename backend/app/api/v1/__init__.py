"""
API v1 router aggregator.

Mounts all versioned sub-routers under the ``/api`` prefix. Shared
pre-flight dependencies (rate limiting, API key) are applied once here
so individual routers stay dependency-free.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import career, chat, resume
from app.core.rate_limit import rate_limit_dependency
from app.core.security import require_api_key

# Router for everything under /api — applied before sub-routers so
# rate limiting + optional API-key auth guard every endpoint.
api_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(require_api_key)],
)

api_router.include_router(
    chat.router,
    dependencies=[Depends(rate_limit_dependency)],
)
api_router.include_router(
    career.router,
    dependencies=[Depends(rate_limit_dependency)],
)
api_router.include_router(
    resume.router,
    dependencies=[Depends(rate_limit_dependency)],
)
