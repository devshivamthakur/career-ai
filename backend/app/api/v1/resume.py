"""
Resume API v1 — resume tailoring & PDF export (thin HTTP layer).

Business logic lives in ``app.services.resume_tailor_service`` (orchestration,
validation, file handling) and ``app.services.streaming_service`` (SSE events).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api.v1.deps import (
    ensure_capacity,
    ensure_circuit_closed,
    get_resume_tailor_service,
)
from app.core.config import settings
from app.core.infrastructure import ServiceConfig, circuit_breaker, concurrency_mgr
from app.schemas.resume_schemas import ResumeExportRequest
from app.services.pdf_export import PDFExportService
from app.services.resume_tailor_service import ResumeTailorService
from app.utils.constants import MAX_FILE_SIZE_MB, MAX_JOB_DESCRIPTION_LENGTH, MIN_JOB_DESCRIPTION_LENGTH
from app.utils.helpers import generate_request_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"])


def _keepalive_stream(
    request: Request,
    stream,
    request_id: str,
) -> StreamingResponse:
    """Yield SSE chunks with keep-alive heartbeats and disconnect detection."""

    async def stream_gen():
        next_chunk_task = asyncio.create_task(stream.__anext__())
        try:
            while True:
                if await request.is_disconnected():
                    logger.warning("Request %s: client disconnected", request_id)
                    break

                done, _ = await asyncio.wait(
                    {next_chunk_task},
                    timeout=ServiceConfig.KEEP_ALIVE_TIMEOUT,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if not done:
                    yield ": keep-alive\n\n"  # heartbeat
                    continue

                try:
                    chunk = next_chunk_task.result()
                except StopAsyncIteration:
                    break
                except Exception as exc:
                    logger.error("Request %s: stream error - %s", request_id, exc)
                    circuit_breaker.record_failure()
                    from app.utils.sse import sse_event

                    yield sse_event("error", {"error": str(exc), "success": False})
                    break

                yield chunk
                next_chunk_task = asyncio.create_task(stream.__anext__())
        finally:
            if not next_chunk_task.done():
                next_chunk_task.cancel()

    return StreamingResponse(
        stream_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
            "X-Request-ID": request_id,
        },
    )


@router.post(
    "/tailor/stream",
    summary="Tailor resume to job description (streaming)",
    response_class=StreamingResponse,
)
async def tailor_resume_stream(
    request: Request,
    resume_pdf: UploadFile = File(..., description="Resume/CV PDF file"),
    job_description: str = Form(
        ...,
        min_length=MIN_JOB_DESCRIPTION_LENGTH,
        max_length=MAX_JOB_DESCRIPTION_LENGTH,
        description="Target job description",
    ),
    service: ResumeTailorService = Depends(get_resume_tailor_service),
    _: None = Depends(ensure_capacity),
    __: None = Depends(ensure_circuit_closed),
):
    """Tailor a resume to a job description, streaming SSE events."""
    request_id = generate_request_id()
    request_start_time = asyncio.get_event_loop().time()
    logger.info("Request %s: Resume tailoring initiated", request_id)

    try:
        async with concurrency_mgr.request_limit(request_id):
            cleaned_jd, cv_text = await service.validate_and_prepare(
                job_description, resume_pdf
            )
            logger.info("Request %s: Inputs validated, starting stream", request_id)

            stream = service.streaming_service.stream_resume_generation(
                cv_text=cv_text,
                job_description=cleaned_jd,
                request_id=request_id,
                start_time=request_start_time,
            )
            return _keepalive_stream(request, stream, request_id)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Unhandled error - %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while tailoring resume",
        )


@router.post(
    "/export-pdf",
    summary="Export tailored resume as PDF",
    response_class=StreamingResponse,
)
async def export_pdf(resume_request: ResumeExportRequest):
    """Export tailored resume text as a downloadable PDF file."""
    request_id = generate_request_id()

    if not resume_request.resume_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume text is required",
        )

    try:
        pdf_buffer = await asyncio.wait_for(
            asyncio.to_thread(
                PDFExportService.generate_pdf,
                resume_request.resume_text,
            ),
            timeout=30,
        )
    except asyncio.TimeoutError:
        logger.error("Request %s: PDF generation timeout", request_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF generation timed out",
        )
    except Exception as exc:
        logger.error("Request %s: PDF export error - %s", request_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating PDF",
        )

    logger.info("Request %s: PDF exported successfully", request_id)
    return StreamingResponse(
        iter([pdf_buffer.getvalue()]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="tailored_resume.pdf"',
            "Cache-Control": "no-cache",
            "X-Request-ID": request_id,
        },
    )


@router.get("/status", summary="Service health and detailed status")
async def resume_service_status(
    service: ResumeTailorService = Depends(get_resume_tailor_service),
):
    """Detailed service status for monitoring and debugging."""
    return {
        "status": "operational",
        "service": "Resume Tailor v2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "capabilities": {
            "pdf_extraction": True,
            "resume_tailoring": True,
            "streaming": True,
            "pdf_export": True,
            "validation_caching": True,
            "parallel_execution": True,
        },
        "configuration": {
            "max_concurrent_requests": ServiceConfig.MAX_CONCURRENT_REQUESTS,
            "max_concurrent_pdf_tasks": ServiceConfig.MAX_CONCURRENT_PDF_PARSING,
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "jd_min_length": MIN_JOB_DESCRIPTION_LENGTH,
            "jd_validation_timeout_sec": ServiceConfig.JD_VALIDATION_TIMEOUT,
            "pdf_parsing_timeout_sec": ServiceConfig.PDF_PARSING_TIMEOUT,
            "keep_alive_timeout_sec": ServiceConfig.KEEP_ALIVE_TIMEOUT,
        },
        "performance": {
            "active_requests": concurrency_mgr.get_active_request_count(),
            "cache_ttl_sec": ServiceConfig.VALIDATION_CACHE_TTL,
            "circuit_breaker_state": circuit_breaker.state.value,
        },
        "model": {
            "provider": settings.LLM_PROVIDER.capitalize(),
            "fast_model": settings.FAST_MODEL_NAME,
            "quality_model": settings.QUALITY_MODEL_NAME,
        },
    }


@router.get("/health", summary="Liveness probe")
async def health_check(
    service: ResumeTailorService = Depends(get_resume_tailor_service),
):
    """Minimal liveness probe for orchestration systems (K8s, Docker, etc.)."""
    return {"status": "healthy"}
