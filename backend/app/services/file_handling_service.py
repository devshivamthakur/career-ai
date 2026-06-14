"""
File upload handling and PDF validation service.

Manages temporary file storage, size validation, and content-type checks
for uploaded resume PDFs.
"""

import os
import tempfile
import logging
from contextlib import suppress
from typing import Optional

from fastapi import HTTPException, UploadFile, status

from app.core.infrastructure import ServiceConfig
from app.services.pdf_service import PDFParsingService
from app.utils.constants import MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)


class FileHandlingService:
    """Handles file upload validation, temporary storage, and cleanup."""

    @staticmethod
    async def save_uploaded_file(cv_file: UploadFile) -> str:
        """Save an uploaded file to a temporary location.

        Returns:
            The absolute path to the temporary file.

        Raises:
            HTTPException: If the file is empty, too large, or cannot be saved.
        """
        try:
            file_content = await cv_file.read()

            if not file_content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty",
                )

            # Validate file size
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds {MAX_FILE_SIZE_MB} MB limit",
                )

            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
                prefix=ServiceConfig.TEMP_FILE_PREFIX,
            ) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name

            logger.debug("Temp file created: %s", tmp_path)
            return tmp_path

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("File save error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing file upload",
            )

    @staticmethod
    def validate_pdf_file(file_path: str) -> None:
        """Validate that a file is a readable, non-empty PDF."""
        if not PDFParsingService.validate_pdf_file(file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted PDF file",
            )

    @staticmethod
    async def cleanup_temp_file(file_path: str, delay: int = 0) -> None:
        """Asynchronously remove a temporary file, with an optional delay."""
        if delay:
            import asyncio
            await asyncio.sleep(delay)

        with suppress(Exception):
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug("Cleaned up temp file: %s", file_path)
