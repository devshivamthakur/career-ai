"""
Rate limiting middleware for FastAPI.

Uses Redis as a distributed counter to enforce per-client rate limits.
Defaults are pulled from ``ServiceConfig`` in the infrastructure module.
"""

import logging

from fastapi import Request, HTTPException, status
from redis.asyncio import Redis

from app.core.infrastructure import ServiceConfig
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_client_ip(request: Request) -> str:
    """Extract the client IP from request headers or direct connection."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client is None:
        return "unknown"

    return request.client.host


redis_client = Redis.from_url(settings.resolved_redis_url, encoding="utf-8", decode_responses=True)


def _format_key(client_id: str) -> str:
    return f"rate_limit:{client_id}"


async def allow_request(client_id: str) -> bool:
    """Check whether *client_id* has remaining capacity within the current window."""
    key = _format_key(client_id)
    try:
        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, ServiceConfig.RATE_LIMIT_WINDOW)

        return current <= ServiceConfig.MAX_REQUESTS_PER_CLIENT
    except Exception as exc:
        logger.error("Redis rate limiter error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting service unavailable",
        )


async def retry_after(client_id: str) -> int:
    """Return the remaining TTL (seconds) of the rate-limit key for *client_id*."""
    key = _format_key(client_id)
    ttl = await redis_client.ttl(key)
    if ttl is None or ttl < 0:
        return 0
    return ttl


async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency that enforces rate limits per client IP."""
    client_id = _get_client_ip(request)
    allowed = await allow_request(client_id)
    if not allowed:
        retry = await retry_after(client_id)
        logger.warning("Rate limit exceeded for client %s", client_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again later.",
            headers={"Retry-After": str(retry)},
        )
