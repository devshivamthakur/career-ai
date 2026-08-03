"""
Gunicorn configuration for production deployments.

Run with:
    gunicorn -c gunicorn_conf.py app.main:app

Every value can be overridden via environment variables.
"""

from __future__ import annotations

import multiprocessing
import os

# ── Server socket ─────────────────────────────────────────────────
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# ── Workers ───────────────────────────────────────────────────────
# Async workers (UvicornWorker) handle concurrent connections per worker.
# Default: 2 × CPU cores + 1 (classic gunicorn recommendation).
workers = int(
    os.getenv("GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1))
)
worker_class = "uvicorn.workers.UvicornWorker"

# ── Timeouts (SSE streams can be long-lived) ──────────────────────
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "60"))
keepalive = 5

# ── Process recycling (prevents slow memory leaks) ────────────────
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 50

# ── Logging ───────────────────────────────────────────────────────
# Access logging is handled by app.api.middleware.RequestLoggingMiddleware,
# so the gunicorn access log defaults to off unless explicitly enabled.
accesslog = os.getenv("GUNICORN_ACCESS_LOG") or None
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
