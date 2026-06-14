"""
Service layer for the CareerAI backend.

Contains business-logic orchestration, PDF processing, session management,
validation, file handling, and SSE streaming services.
"""

from app.services.chat_session import (
    create_session,
    get_session,
    save_message,
    get_context_messages,
    delete_session,
    ensure_session,
)
from app.services.pdf_service import PDFParsingService
from app.services.pdf_export import PDFExportService
from app.services.validation_service import ValidationService, RequestValidationService
from app.services.file_handling_service import FileHandlingService
from app.services.streaming_service import StreamingService
from app.services.resume_tailor_service import ResumeTailorService
from app.services.career_assistant_service import CareerAssistantService

__all__ = [
    "create_session",
    "get_session",
    "save_message",
    "get_context_messages",
    "delete_session",
    "ensure_session",
    "PDFParsingService",
    "PDFExportService",
    "ValidationService",
    "RequestValidationService",
    "FileHandlingService",
    "StreamingService",
    "ResumeTailorService",
    "CareerAssistantService",
]
