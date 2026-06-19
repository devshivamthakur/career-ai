"""
Miscellaneous helper utilities used across the application.

Includes request-ID generation, temp-file cleanup helpers,
and prompt injection sanitisation utilities.
"""

import os
import re
import time
import logging
from contextlib import suppress

logger = logging.getLogger(__name__)


# ── Prompt Injection Sanitisation ───────────────────────────────
# Known prompt injection / jailbreak patterns to strip from user input
# before it reaches the LLM prompt context.
#
# NOTE: Delimiter-based separation (the ════════ markers in chat_routes.py)
# is the PRIMARY defence. This secondary sanitisation catches common
# injection payloads that might leak through.

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directions|commands|prompts)", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all\s+previous)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)", re.IGNORECASE),
    re.compile(r"you\s+(are\s+)?(now|free|allowed)\s+to", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|though\s+you\s+are|a\s+new)", re.IGNORECASE),
    re.compile(r"new\s+(instructions|directions|commands|prompts?)\s*:?", re.IGNORECASE),
    re.compile(r"system\s*(prompt|message|instruction)", re.IGNORECASE),
    re.compile(r"output\s+(your\s+)?(system\s+)?(prompt|instructions)", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+)?(prompt|instructions|tools?)", re.IGNORECASE),
    re.compile(r"leak\s+(your\s+)?(system\s+)?(prompt|instructions|data)", re.IGNORECASE),
    re.compile(r"DAN|do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"you\s+don'?t\s+have\s+(to\s+)?(follow|obey)", re.IGNORECASE),
    re.compile(r"override\s+(mode|protocol|restrictions|constraints)", re.IGNORECASE),
]


def sanitise_user_input(text: str) -> str:
    """Strip or neutralise known prompt injection patterns from user input.

    This is a SECONDARY defence — the primary protection is the
    delimiter-based separation of system instructions from user content.

    Args:
        text: The raw user input string.

    Returns:
        Sanitised text with injection patterns replaced by neutral markers.
    """
    original = text
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[redacted]", text)

    if text != original:
        logger.info("Prompt injection patterns stripped from user input (%d chars → %d chars)",
                     len(original), len(text))
    return text


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
