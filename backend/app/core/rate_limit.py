"""
Rate limiting for FastAPI.

Production path uses Redis (distributed counter, shared across workers).
When Redis is unreachable, the limiter transparently degrades to a
per-process in-memory sliding window so the API never 503s solely
because the rate-limiter backend is down.

Limits are configured via ``ServiceConfig.MAX_REQUESTS_PER_CLIENT`` and
``ServiceConfig.RATE_LIMIT_WINDOW``.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Optional

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings
from app.core.infrastructure import ServiceConfig
from app.core.security import get_client_ip

logger = logging.getLogger(__name__)

_REDIS: Optional[Redis] = None
_REDIS_FAILED = False

# In-memory fallback: client_id -> recent request timestamps
_MEMORY_LIMITS: dict[str, Deque[float]] = defaultdict(deque)


def _get_redis() -> Optional[Redis]:
    """Lazily create the Redis client once. Returns None if Redis is down."""
    global _REDIS, _REDIS_FAILED
    if _REDIS is None and not _REDIS_FAILED:
        try:
            _REDIS = Redis.from_url(
                settings.resolved_redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Rate limiter: Redis client init failed: %s", exc)
            _REDIS_FAILED = True
    return _REDIS


def _format_key(client_id: str) -> str:
    return f"rate_limit:{client_id}"


# ── Redis backend ─────────────────────────────────────────────────

async def _allow_redis(client_id: str) -> tuple[bool, int]:
    """Increment-and-expire counter. Returns (allowed, retry_after_seconds)."""
    redis = _get_redis()
    if redis is None:
        return True, 0  # caller falls through to the in-memory window

    key = _format_key(client_id)
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, ServiceConfig.RATE_LIMIT_WINDOW)

        allowed = current <= ServiceConfig.MAX_REQUESTS_PER_CLIENT
        retry_after = 0
        if not allowed:
            ttl = await redis.ttl(key)
            retry_after = int(ttl) if ttl and ttl > 0 else ServiceConfig.RATE_LIMIT_WINDOW
        return allowed, retry_after
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Rate limiter: Redis error, using in-memory fallback: %s", exc)
        return True, 0


# ── In-memory fallback (sliding window) ───────────────────────────

async def _allow_memory(client_id: str) -> tuple[bool, int]:
    """Sliding-window counter. Returns (allowed, retry_after_seconds)."""
    now = time.monotonic()
    window_start = now - ServiceConfig.RATE_LIMIT_WINDOW

    queue = _MEMORY_LIMITS[client_id]
    while queue and queue[0] < window_start:
        queue.popleft()

    if len(queue) >= ServiceConfig.MAX_REQUESTS_PER_CLIENT:
        retry_after = max(1, int(ServiceConfig.RATE_LIMIT_WINDOW - (now - queue[0])))
        return False, retry_after

    queue.append(now)
    return True, 0


# ── Public dependency ─────────────────────────────────────────────

async def rate_limit_dependency(request: Request) -> None:
    """FastAPI dependency enforcing per-client rate limits (Redis → memory fallback)."""
    client_id = get_client_ip(request)

    allowed, retry_after = await _allow_redis(client_id)
    if not allowed:
        logger.warning("Rate limit exceeded for client %s", client_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Redis healthy → done. If Redis is unavailable, _allow_redis returned
    # (True, 0) and we enforce via the in-memory window instead.
    if _get_redis() is not None:
        return

    allowed, retry_after = await _allow_memory(client_id)
    if not allowed:
        logger.warning("Rate limit exceeded (memory fallback) for client %s", client_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down and try again later.",
            headers={"Retry-After": str(retry_after)},
        )
