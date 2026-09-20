"""
Shared configuration and utilities.

Re-exports settings and provides a shared async Redis client.
"""

from app.core.config import settings

__all__ = ["settings"]