"""
Miscellaneous helper utilities used across the application.

Includes request-ID generation and temp-file cleanup helpers.
"""

import os
import time
import logging
from contextlib import suppress

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate a unique request ID for tracing and correlation."""
    return f"req_{int(time.time() * 1000)}"


async def cleanup_temp_file(file_path: str, delay: int = 0) -> None:
    """Asynchronously remove a temporary file, with an optional delay.

    Args:
        file_path: Absolute path to the file to remove.
        delay: Seconds to wait before removing (default 0).
    """
    if delay:
        import asyncio
        await asyncio.sleep(delay)

    with suppress(Exception):
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug("Cleaned up temp file: %s", file_path)
