"""
Resume Tailoring Service Layer
Encapsulates business logic and orchestration for resume tailoring.
"""

import os
import json
import time
import hashlib
import logging
import tempfile
from typing import AsyncGenerator, Optional, Tuple
from contextlib import suppress
from datetime import datetime

from fastapi import HTTPException, status, UploadFile

from app.api.config import (
    ServiceConfig, circuit_breaker, request_cache, concurrency_mgr
)
from app.agents.resume_tailor import ResumeTailorAgent
from app.services.pdf_service import PDFParsingService
from app.utils import MIN_JOB_DESCRIPTION_LENGTH, STREAM_DELAY

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def compute_hash(data: str) -> str:
    """Compute SHA256 hash for caching"""
    return hashlib.sha256(data.encode()).hexdigest()


def generate_request_id() -> str:
    """Generate unique request ID for tracking"""
    return f"req_{int(time.time() * 1000)}"


async def cleanup_temp_file(file_path: str, delay: int = 0) -> None:
    """Async cleanup of temporary files with optional delay"""
    if delay:
        await asyncio.sleep(delay)
    
    with suppress(Exception):
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Cleaned up temp file: {file_path}")


def sse_event(event: str, data: dict) -> str:
    """Format SSE (Server-Sent Event) response"""
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data)}\n\n"
    )


# ═══════════════════════════════════════════════════════════════════════
# VALIDATION SERVICE
# ═══════════════════════════════════════════════════════════════════════

class ValidationService:
    """Handles validation of job descriptions with caching"""
    
    def __init__(self, agent: ResumeTailorAgent):
        self.agent = agent
    
    async def validate_job_description(self, jd: str) -> Tuple[bool, str]:
        """
        Validate job description with caching.
        Avoids redundant validation for duplicate JDs.
        """
        jd_hash = compute_hash(jd)
        
        # Check cache
        cached_result = await request_cache.get(jd_hash)
        if cached_result is not None:
            logger.debug("JD validation cache hit")
            return cached_result
        
        # Validate
        try:
            is_valid, reason = await asyncio.wait_for(
                self.agent.validate_job_description(jd),
                timeout=ServiceConfig.JD_VALIDATION_TIMEOUT
            )
            
            result = (is_valid, reason)
            
            # Cache result
            await request_cache.set(
                jd_hash,
                result,
                ttl=ServiceConfig.VALIDATION_CACHE_TTL
            )
            
            return result
        
        except asyncio.TimeoutError:
            logger.error("JD validation timeout")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Job description validation timed out"
            )


# ═══════════════════════════════════════════════════════════════════════
# PDF SERVICE
# ═══════════════════════════════════════════════════════════════════════

class PDFService:
    """Handles PDF extraction and validation"""
    
    async def extract_resume_text(self, pdf_path: str) -> str:
        """
        Extract resume text with concurrency limiting.
        Prevents resource exhaustion from concurrent PDF parsing.
        """
        async with concurrency_mgr.pdf_limit():
            try:
                import asyncio
                cv_text = await asyncio.wait_for(
                    asyncio.to_thread(
                        PDFParsingService.extract_text_from_pdf,
                        pdf_path
                    ),
                    timeout=ServiceConfig.PDF_PARSING_TIMEOUT
                )
                
                if not cv_text or len(cv_text.strip()) < 50:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Insufficient text extracted from PDF (minimum 50 characters)"
                    )
                
                return cv_text
            
            except asyncio.TimeoutError:
                logger.error("PDF parsing timeout")
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="PDF extraction timed out"
                )


# ═══════════════════════════════════════════════════════════════════════
# FILE HANDLING SERVICE
# ═══════════════════════════════════════════════════════════════════════

class FileHandlingService:
    """Handles file upload validation and processing"""
    
    @staticmethod
    async def save_uploaded_file(cv_file: UploadFile) -> str:
        """
        Save uploaded file to temporary location.
        Returns path to temporary file.
        """
        try:
            # Read file content
            file_content = await cv_file.read()
            
            if not file_content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded file is empty"
                )
            
            # Validate file size
            file_size_mb = len(file_content) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds {MAX_FILE_SIZE_MB} MB limit"
                )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".pdf",
                prefix=ServiceConfig.TEMP_FILE_PREFIX
            ) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            logger.debug(f"Temp file created: {tmp_path}")
            return tmp_path
        
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"File save error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error processing file upload"
            )
    
    @staticmethod
    def validate_pdf_file(file_path: str) -> None:
        """Validate PDF file integrity"""
        if not PDFParsingService.validate_pdf_file(file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted PDF file"
            )


# ═══════════════════════════════════════════════════════════════════════
# STREAMING SERVICE
# ═══════════════════════════════════════════════════════════════════════

class StreamingService:
    """Handles SSE streaming with backpressure and error handling"""
    
    def __init__(self, agent: ResumeTailorAgent):
        self.agent = agent
    
    async def stream_resume_generation(
        self,
        cv_text: str,
        job_description: str,
        request_id: str,
        start_time: float
    ) -> AsyncGenerator[str, None]:
        """
        Stream tailored resume with parallel execution + filtered output.
        Only emits events from compare_skills and polish_resume for faster UX.
        """
        try:
            # Start event
            yield sse_event("started", {
                "message": "Resume tailoring started (parsing & analyzing in parallel)",
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Stream from agent - events are pre-formatted JSON strings
            async for event_data in self.agent.astream_tailored_resume(
                cv_text=cv_text,
                job_description=job_description,
            ):
                if not event_data:
                    continue
                
                # Parse the event JSON and re-emit as SSE
                try:
                    event_obj = json.loads(event_data)
                    event_type = event_obj.get("type")
                    
                    # Re-emit event with proper SSE formatting
                    yield sse_event(event_type, event_obj)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse event JSON: {event_data}")
                    continue
                
                # Backpressure: yield control to allow client to consume
                if STREAM_DELAY:
                    import asyncio
                    await asyncio.sleep(STREAM_DELAY)
            
            # Success event with metadata
            total_time = round(time.time() - start_time, 2)
            
            yield sse_event("completed", {
                "success": True,
                "request_id": request_id,
                "processing_time_seconds": total_time,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            circuit_breaker.record_success()
        
        except asyncio.CancelledError:
            logger.warning(f"Request {request_id}: Client disconnected during stream")
            raise
        
        except Exception as stream_error:
            logger.exception(f"Request {request_id}: Streaming error: {str(stream_error)}")
            circuit_breaker.record_failure()
            
            yield sse_event("error", {
                "success": False,
                "request_id": request_id,
                "error": str(stream_error),
                "error_type": type(stream_error).__name__,
                "timestamp": datetime.utcnow().isoformat()
            })


# ═══════════════════════════════════════════════════════════════════════
# REQUEST VALIDATION SERVICE
# ═══════════════════════════════════════════════════════════════════════

class RequestValidationService:
    """Validates incoming requests"""
    
    @staticmethod
    def validate_job_description_input(job_description: str) -> str:
        """Validate and clean job description input"""
        cleaned_jd = job_description.strip()
        
        if not cleaned_jd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description is required"
            )
        
        if len(cleaned_jd) < MIN_JOB_DESCRIPTION_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job description must be at least {MIN_JOB_DESCRIPTION_LENGTH} characters"
            )
        
        return cleaned_jd
    
    @staticmethod
    def validate_pdf_content_type(content_type: Optional[str]) -> None:
        """Validate PDF content type"""
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed"
            )


# ═══════════════════════════════════════════════════════════════════════
# RESUME TAILOR SERVICE (Orchestrator)
# ═══════════════════════════════════════════════════════════════════════

class ResumeTailorService:
    """
    Main service orchestrator for resume tailoring.
    Coordinates validation, file handling, and streaming.
    """
    
    def __init__(self, agent: ResumeTailorAgent):
        self.agent = agent
        self.validation_service = ValidationService(agent)
        self.pdf_service = PDFService()
        self.file_service = FileHandlingService()
        self.request_validation_service = RequestValidationService()
        self.streaming_service = StreamingService(agent)
    
    async def validate_and_prepare(
        self,
        job_description: str,
        cv_file: UploadFile
    ) -> Tuple[str, str]:
        """
        Validate inputs and prepare for streaming.
        Returns (cleaned_jd, cv_text)
        """
        # Validate job description input
        cleaned_jd = self.request_validation_service.validate_job_description_input(
            job_description
        )
        
        # Validate PDF content type
        self.request_validation_service.validate_pdf_content_type(
            cv_file.content_type
        )
        
        # Save uploaded file
        tmp_path = await self.file_service.save_uploaded_file(cv_file)
        
        try:
            # Validate PDF file
            self.file_service.validate_pdf_file(tmp_path)
            
            # Extract resume text
            logger.info("Extracting resume text")
            cv_text = await self.pdf_service.extract_resume_text(tmp_path)
            logger.info(f"Resume extracted - {len(cv_text)} chars")
            
            # Validate job description
            is_valid_jd, reason = await self.validation_service.validate_job_description(
                cleaned_jd
            )
            
            if not is_valid_jd:
                logger.warning(f"Invalid JD - {reason}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid job description: {reason}"
                )
            
            return cleaned_jd, cv_text
        
        finally:
            # Cleanup temp file
            with suppress(Exception):
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)


import asyncio
from app.utils import MAX_FILE_SIZE_MB
