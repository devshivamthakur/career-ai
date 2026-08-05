"""
Centralised exception handlers.

Maps framework exceptions (validation, HTTP) and application exceptions
(:class:`app.core.exceptions.AppError`) to consistent JSON payloads that
always include the request ID for correlation.
"""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map application exceptions to HTTP responses."""
    logger.warning(
        "Request %s: app error %s (%s): %s",
        _request_id(request),
        exc.code,
        exc.status_code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            "request_id": _request_id(request),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = _request_id(request)
    logger.warning("Request %s: HTTP %d: %s", request_id, exc.status_code, exc.detail)

    content = {"detail": exc.detail, "request_id": request_id}
    if exc.headers:
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    request_id = _request_id(request)
    logger.warning("Request %s: request validation failed: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "request_id": request_id,
        },
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = _request_id(request)
    logger.exception("Request %s: unhandled exception: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": request_id},
    )
