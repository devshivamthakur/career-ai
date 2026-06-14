"""
Resume Tailor Service — main orchestrator for the resume tailoring workflow.

Coordinates validation, file handling, PDF extraction, and streaming
into a single ``validate_and_prepare`` → ``stream_resume_generation`` pipeline.
"""

import os
import logging
from contextlib import suppress
from typing import Tuple

from fastapi import UploadFile

from app.services.validation_service import ValidationService, RequestValidationService
from app.services.file_handling_service import FileHandlingService
from app.services.streaming_service import StreamingService
from app.services.pdf_service import PDFParsingService
from app.core.infrastructure import concurrency_mgr, ServiceConfig

logger = logging.getLogger(__name__)


class ResumeTailorService:
    """Main service orchestrator for resume tailoring.

    Coordinates validation, file handling, PDF extraction, and streaming.
    """

    def __init__(self, agent) -> None:
        self.agent = agent
        self.validation_service = ValidationService(agent)
        self.request_validation_service = RequestValidationService()
        self.file_service = FileHandlingService()
        self.streaming_service = StreamingService(agent)

    async def validate_and_prepare(
        self,
        job_description: str,
        resume_pdf: UploadFile,
    ) -> Tuple[str, str]:
        """Validate inputs and prepare for streaming.

        Returns:
            A ``(cleaned_jd, cv_text)`` tuple.
        """
        # Validate job description input
        cleaned_jd = self.request_validation_service.validate_job_description_input(
            job_description
        )

        # Validate PDF content type
        self.request_validation_service.validate_pdf_content_type(
            resume_pdf.content_type
        )

        # Save uploaded file
        tmp_path = await self.file_service.save_uploaded_file(resume_pdf)

        try:
            # Validate PDF file integrity
            self.file_service.validate_pdf_file(tmp_path)

            # Extract resume text with concurrency limiting
            async with concurrency_mgr.pdf_limit():
                import asyncio

                cv_text = await asyncio.wait_for(
                    asyncio.to_thread(
                        PDFParsingService.extract_text_from_pdf, tmp_path
                    ),
                    timeout=ServiceConfig.PDF_PARSING_TIMEOUT,
                )

            if not cv_text or len(cv_text.strip()) < 50:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient text extracted from PDF (minimum 50 characters)",
                )

            logger.info("Resume extracted — %d chars", len(cv_text))

            # Validate job description
            is_valid_jd, reason = await self.validation_service.validate_job_description(
                cleaned_jd
            )

            if not is_valid_jd:
                from fastapi import HTTPException, status
                logger.warning("Invalid JD — %s", reason)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid job description: {reason}",
                )

            return cleaned_jd, cv_text

        finally:
            # Cleanup temp file
            with suppress(Exception):
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
