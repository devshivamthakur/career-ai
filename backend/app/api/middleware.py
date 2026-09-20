"""
HTTP middleware: request-ID correlation, security headers, request logging,
and body-size limits.

Kept separate from the app factory so ``main.py`` stays declarative.
"""

from __future__ import annotations

import logging
import time

from fastapi import Request,Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.security import get_client_ip, parse_allowed_origins
from app.services.ip_ban_service import ip_ban_service
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
            # In production, connect-src should allow self and the configured origins
            origins_str = " ".join(parse_allowed_origins())
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self' data:; "
                f"connect-src 'self' {origins_str}; "
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


class IPBanMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks banned IPs and counts *unauthenticated* suspicious
    scanner traffic toward an auto-ban threshold.

    Key behaviour:
      1. If the IP is banned (or auto-banned) -> 403.
      2. If the IP is on the static or dynamic whitelist -> always allowed.
      3. Suspicious-path violation counting is skipped when the request is
         either authenticated with a JWT or carrying the admin API key.
         That prevents legitimate admin dashboard traffic from triggering
         an auto-ban just because the URL contains the segment "admin".
      4. Only requests that look like real scanner/probe traffic (.env,
         .git, wp-*, xmlrpc.php, *.php, etc.) count as violations.
    """

    # Paths that don't count as security violations (legitimate access).
    EXEMPT_PATHS = [
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    ]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> JSONResponse:
        client_ip = request.client.host if request.client else "unknown"

        # 1) Banned -> blocked (whitelisted IPs short-circuit this).
        if await ip_ban_service.is_banned(client_ip):
            logger.warning(
                "Blocked banned IP access attempt: %s -> %s",
                client_ip,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Your IP has been blocked due to suspicious activity.",
                    "detail": "If you believe this is an error, please contact support.",
                },
            )

        # 2) Suspicious-path detection - only for unauthenticated requests.
        #    The path itself is also re-checked against the safe-prefix
        #    allow-list inside is_suspicious_path().
        path = request.url.path
        if path not in self.EXEMPT_PATHS and ip_ban_service.is_suspicious_path(path):
            if not self._looks_authenticated(request):
                await ip_ban_service.record_security_violation(client_ip, path)

        response = await call_next(request)

        # 3) Rate-limited -> record violation for potential auto-ban
        #    (again, only for unauthenticated callers).
        if response.status_code == 429 and not self._looks_authenticated(request):
            await ip_ban_service.record_rate_limit_violation(client_ip)

        return response

    @staticmethod
    def _looks_authenticated(request: Request) -> bool:
        """
        Return True if the request carries either:
          * a Bearer JWT in the Authorization header, or
          * the admin API key in the X-API-Key header.

        Note: this is purely a *presence* check used to exempt clearly
        legitimate traffic from scanner-style counters. It does NOT
        validate the token/key here - the route's own dependency does
        that and will return 401/403 if the credential is bad.
        """
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer ") and auth[7:].strip():
            return True
        if request.headers.get("x-api-key"):
            return True
        return False
