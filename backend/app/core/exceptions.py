"""
Application-specific exception types.

Central hierarchy for business errors so that the API error handlers
can map them to HTTP responses consistently (see ``app.api.errors``).
"""

from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    """Base class for all application errors.

    Attributes:
        status_code: HTTP status code to return.
        code: Machine-readable error code (e.g. ``"pdf_page_limit"``).
        message: Human-readable detail message.
        detail: Optional extra structured payload (headers, context).
    """

    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        if code:
            self.code = code
        self.detail = detail or {}


class ServiceUnavailableError(AppError):
    """Downstream service (LLM, agent, Redis…) is unavailable."""

    status_code = 503
    code = "service_unavailable"
    message = "Service temporarily unavailable"


class RateLimitExceededError(AppError):
    """Client exceeded the configured request rate."""

    status_code = 429
    code = "rate_limit_exceeded"
    message = "Too many requests, please slow down"


class ResourceNotFoundError(AppError):
    """Requested resource (session, file…) does not exist."""

    status_code = 404
    code = "not_found"
    message = "Resource not found"


class InvalidInputError(AppError):
    """Input validation failed at the business-logic layer."""

    status_code = 422
    code = "invalid_input"
    message = "Invalid input"


class PDFProcessingError(InvalidInputError):
    """PDF could not be read/parsed."""

    code = "pdf_processing_failed"


class PDFPageLimitError(InvalidInputError):
    """PDF exceeds the allowed page count."""

    code = "pdf_page_limit_exceeded"
