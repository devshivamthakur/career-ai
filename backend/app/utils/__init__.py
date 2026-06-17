"""
Utility package for the CareerAI backend.

Provides shared constants, SSE formatting helpers, telemetry utilities,
and miscellaneous helper functions used across the application layers.
"""

from app.utils.constants import (
    MAX_FILE_SIZE_MB,
    MIN_JOB_DESCRIPTION_LENGTH,
    MAX_JOB_DESCRIPTION_LENGTH,
    STREAM_DELAY,
    RESUME_SECTION_KEYWORDS,
    RESUME_TRIGGER_KEYWORDS,
)

from app.utils.sse import sse_event

from app.utils.telemetry import build_langfuse_callbacks

from app.utils.helpers import generate_request_id, cleanup_temp_file

__all__ = [
    "MAX_FILE_SIZE_MB",
    "MIN_JOB_DESCRIPTION_LENGTH",
    "MAX_JOB_DESCRIPTION_LENGTH",
    "STREAM_DELAY",
    "RESUME_SECTION_KEYWORDS",
    "RESUME_TRIGGER_KEYWORDS",
    "sse_event",
    "build_langfuse_callbacks",
    "generate_request_id",
    "cleanup_temp_file",
]
