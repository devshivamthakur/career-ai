"""Shared Redis client for request-time infrastructure services."""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from app.core.config import settings

_redis: Optional[Redis] = None


def get_redis() -> Redis:
    """Return the process-wide bounded Redis client."""
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.resolved_redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
        )
    return _redis


async def close_redis() -> None:
    """Close the shared pool during application shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None