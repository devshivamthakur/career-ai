"""
Telemetry and observability utilities.

Provides callback builders for LangFuse (LLM observability platform)
so that all LLM calls across the application can be traced consistently.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def build_langfuse_callbacks(source_name: str = "agent") -> list[Any]:
    """Build LangFuse callback handlers if credentials are configured.

    Args:
        source_name: Label used in log messages to identify the caller.

    Returns:
        A list of callback handlers (empty list if LangFuse is not configured).
    """
    callbacks: list[Any] = []

    # Late import to avoid circular dependency at module level
    from app.core.config import settings

    if not (settings.LANGFUSE_PUBLIC_KEY or settings.LANGFUSE_SECRET_KEY):
        return callbacks

    if settings.LANGFUSE_BASE_URL:
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_BASE_URL)
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
    if settings.LANGFUSE_SECRET_KEY:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)

    try:
        from langfuse.langchain import CallbackHandler

        callbacks.append(CallbackHandler())
        logger.info("LangFuse callback handler enabled for %s", source_name)
    except Exception as exc:
        logger.warning(
            "LangFuse callback handler unavailable for %s: %s",
            source_name,
            exc,
        )

    return callbacks
