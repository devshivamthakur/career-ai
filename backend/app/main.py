"""
CareerAI API — application entry point.

Kept deliberately thin: middleware, error handlers, and routers are
configured in dedicated modules (``app.api.middleware``, ``app.api.errors``,
``app.api.v1``). Only wiring lives here.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.errors import (
    app_error_handler,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
from app.api.middleware import (
    MaxBodySizeMiddleware,
    RequestContextMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    SelectiveGZipMiddleware,
)
from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.events import lifespan
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.core.security import parse_allowed_origins

logger = logging.getLogger(__name__)

configure_logging()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    show_docs = not settings.HIDE_DOCS_IN_PRODUCTION

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="API for CareerAI - AI-Powered Job Application & Interview Prep Assistant",
        docs_url="/docs" if show_docs else None,
        redoc_url="/redoc" if show_docs else None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=lifespan,
    )

    # ── Middleware (first added = outermost) ─────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_allowed_origins(),
        allow_credentials=settings.ALLOW_CREDENTIALS,
        allow_methods=settings.ALLOW_METHODS,
        allow_headers=settings.ALLOW_HEADERS,
        max_age=600,  # cache preflight for 10 minutes
    )
    # Guard against Host-header poisoning
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(MaxBodySizeMiddleware)
    # Compression must be outermost-ish so it can wrap everything below it
    # while still skipping SSE streaming endpoints.
    app.add_middleware(SelectiveGZipMiddleware)

    # ── Exception handlers ───────────────────────────────────────
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unexpected_exception_handler)

    # ── Routers ──────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(api_router)

    # ── Static file serving (uploaded resume PDFs) ───────────────
    storage_path = os.path.join(os.path.dirname(__file__), "storage")
    os.makedirs(storage_path, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=storage_path), name="storage")

    return app


app = create_app()
