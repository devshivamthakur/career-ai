"""
Structured logging configuration.

Configures the root logger once with a consistent, parseable format and
tames noisy third-party loggers (httpx, uvicorn access logs, …).
"""

from __future__ import annotations

import logging
import sys

# ISO-8601-ish timestamp, level, logger name, message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# Loggers that add noise in production
_QUIET_LOGGERS = ("uvicorn.access", "httpx", "httpcore", "pdfminer", "PIL")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger exactly once (idempotent)."""
    root = logging.getLogger()

    # Already configured (e.g. by a test harness) — don't double-register.
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
