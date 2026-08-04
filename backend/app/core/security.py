"""
Security helpers: CORS origin parsing, optional API-key authentication,
and trusted client-IP resolution.

Keeps security policy in one place instead of inline in the app factory.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, Request, status

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Client IP resolution ──────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extract the client IP, honouring ``X-Forwarded-For``.

    NOTE: only trust ``X-Forwarded-For`` when running behind a trusted
    proxy (nginx, ALB, …) — the value is attacker-controlled otherwise.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client is None:
        return "unknown"

    return request.client.host


# ── CORS ──────────────────────────────────────────────────────────

def parse_allowed_origins() -> list[str]:
    """Parse the configured ``ALLOWED_ORIGINS`` into a list of origins.

    Drops empty entries and strips whitespace/quotes.
    """
    raw = settings.ALLOWED_ORIGINS or ""
    # Split by comma and strip whitespace + quotes
    origins = [origin.strip().strip("'").strip('"') for origin in raw.split(",") if origin.strip()]

    if settings.ENVIRONMENT == "production" and not origins:
        logger.warning("No allowed origins configured for production CORS")

    logger.info("Configured CORS origins: %s", origins)
    return origins


# ── Optional API-key authentication ───────────────────────────────

async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Optional dependency: enforce ``X-API-Key`` when ``API_KEY`` is set.

    When no ``API_KEY`` is configured (development), the dependency is a
    no-op so the API remains open. When configured, requests without a
    matching key are rejected with 401.
    """
    expected = settings.API_KEY
    if not expected:
        return

    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
