"""
Server-Sent Events (SSE) formatting utilities.

Provides helpers to format event streams for real-time
communication with the frontend.
"""

import json
from typing import Any


def sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a Server-Sent Event (SSE) string.

    Args:
        event: The event type name (e.g. ``"token"``, ``"done"``, ``"error"``).
        data: A JSON-serialisable dictionary of event data.

    Returns:
        A well-formatted SSE string ready for stream transmission.
    """
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data)}\n\n"
    )
