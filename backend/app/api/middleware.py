"""
HTTP middleware: request-ID correlation, security headers, request logging,
and body-size limits.

Kept separate from the app factory so ``main.py`` stays declarative.
"""

from __future__ import annotations

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings
from app.core.security import get_client_ip
from app.utils.helpers import generate_request_id

logger = logging.getLogger(__name__)

# Endpoints excluded from access logging (noisy / non-business)
_SKIP_LOG_PATHS = {"/health", "/api/resume/health"}

# SSE streaming prefixes must NOT be gzip-compressed — gzip buffers the entire
# stream, which defeats token-by-token streaming and can stall proxies.
_STREAM_PREFIXES = ("/api/chat", "/api/career", "/api/resume/tailor")


class SelectiveGZipMiddleware:
    """Compress JSON/text responses but skip SSE streaming endpoints.

    Pure-ASGI wrapper around Starlette's GZipMiddleware so streaming
    responses pass through untouched (no buffering, no added latency).
    """

    def __init__(self, app, minimum_size: int = 500):
        from starlette.middleware.gzip import GZipMiddleware

        self._streaming_app = app
        self._gzip_app = GZipMiddleware(app, minimum_size=minimum_size)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if any(path.startswith(p) for p in _STREAM_PREFIXES):
                return await self._streaming_app(scope, receive, send)
        return await self._gzip_app(scope, receive, send)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and timestamp to every request/response."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = request_id
        request.state.start_time = time.perf_counter()

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emit one structured access-log line per request (opt-in)."""

    async def dispatch(self, request: Request, call_next):
        if not settings.ENABLE_REQUEST_LOGGING or request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        request_id = getattr(request.state, "request_id", "-")

        logger.info(
            "%s %s %d %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response (config-gated)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if not settings.ENABLE_SECURITY_HEADERS:
            return response

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Prevent referrer leakage of sensitive paths (session IDs, etc.)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Disable browser features we don't use (camera, mic, geolocation)
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        # Deny cross-domain resource embedding (Flash/PDF) — legacy but free
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content-Security-Policy — relaxed in dev (Swagger/JSdelivr), strict in prod
        if settings.ENVIRONMENT == "production":
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self' http://localhost:* ws://localhost:*; "
            )
        response.headers["Content-Security-Policy"] = csp

        response.headers["X-Powered-By"] = ""
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds the configured limit."""

    async def dispatch(self, request: Request, call_next):
        limit = settings.MAX_BODY_SIZE_MB * 1024 * 1024
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > limit:
            return Response(
                status_code=413,
                content='{"detail": "Request body too large"}',
                media_type="application/json",
            )

        # Defensive: stream the body only when content-length is missing
        if not content_length and request.method in {"POST", "PUT", "PATCH"}:
            body = await request.body()
            if len(body) > limit:
                return Response(
                    status_code=413,
                    content='{"detail": "Request body too large"}',
                    media_type="application/json",
                )

        return await call_next(request)
