"""
CareerAI Assistant API routes.
Handles cover letter generation and interview prep endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import StreamingResponse
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional

from app.agents.career_assistant import CareerAssistantAgent
from app.core.infrastructure import circuit_breaker, concurrency_mgr, ServiceConfig
from app.services.career_assistant_service import CareerAssistantService
from app.utils.helpers import generate_request_id
from app.utils.constants import MAX_JOB_DESCRIPTION_LENGTH, MIN_JOB_DESCRIPTION_LENGTH
from app.schemas.resume_schemas import (
    CoverLetterRequest,
    InterviewPrepRequest,
    InterviewPrepResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/career", tags=["career"])

career_agent: Optional[CareerAssistantAgent] = None
career_service: Optional[CareerAssistantService] = None
assistant_init_error: Optional[str] = None

try:
    career_agent = CareerAssistantAgent()
    career_service = CareerAssistantService(career_agent)
    logger.info("Career Assistant Agent initialized successfully")
except Exception as exc:
    assistant_init_error = str(exc)
    logger.error("Failed to initialize Career Assistant Agent: %s", exc, exc_info=True)


def _check_service_availability() -> None:
    if not career_agent or not career_service:
        logger.error("Career assistant unavailable - %s", assistant_init_error)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Career assistant service unavailable",
        )
    if not circuit_breaker.is_available():
        logger.warning("Circuit breaker open for assistant service")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Career assistant is temporarily unavailable",
        )


def _check_concurrency() -> None:
    active_count = concurrency_mgr.get_active_request_count()
    if active_count >= ServiceConfig.MAX_CONCURRENT_REQUESTS:
        logger.warning("Career assistant concurrency limit reached (%s)", active_count)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server busy, please try again shortly",
        )


@router.post(
    "/cover-letter",
    summary="Generate a tailored cover letter (streaming)",
    response_class=StreamingResponse,
)
async def generate_cover_letter(
    request: Request,
    body: CoverLetterRequest,
):
    """
    Generate a tailored cover letter with SSE streaming.
    Accepts JSON body; returns token-by-token streaming response.
    """
    request_id = generate_request_id()
    logger.info("Request %s: Cover letter generation started (streaming)", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        async with concurrency_mgr.request_limit(request_id):
            async def event_stream() -> AsyncGenerator[str, None]:
                try:
                    async for sse_line in career_service.stream_cover_letter_from_text(
                        job_description=body.job_description,
                        company=body.company,
                        role=body.role,
                        resume_text=body.resume_text,
                    ):
                        if await request.is_disconnected():
                            break
                        yield sse_line
                except Exception as e:
                    logger.exception("Cover letter stream error")
                    yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Request-ID": request_id,
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Cover letter stream failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cover letter",
        )


@router.post(
    "/interview-prep",
    summary="Generate interview prep questions",
    response_model=InterviewPrepResponse,
)
async def generate_interview_prep(
    request: Request,
    body: InterviewPrepRequest,
):
    """Generate interview prep questions and answers with structured output."""
    request_id = generate_request_id()
    logger.info("Request %s: Interview prep generation started", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        questions = await career_service.generate_interview_prep(
            job_description=body.job_description,
            role=body.role,
            company=body.company,
            resume_text=body.resume_text,
        )
        logger.info(
            "Request %s: Interview prep generation completed (%d questions)",
            request_id,
            len(questions),
        )
        return InterviewPrepResponse(questions=questions)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Interview prep generation failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate interview prep",
        )


# ═══════════════════════════════════════════════════════════════
# STREAMING ENDPOINTS (token-by-token SSE)
# ═══════════════════════════════════════════════════════════════


@router.post(
    "/cover-letter/stream",
    summary="Generate a tailored cover letter (streaming)",
    response_class=StreamingResponse,
)
async def stream_cover_letter(
    request: Request,
    cv_file: UploadFile = File(..., description="Resume/CV PDF file"),
    job_description: str = Form(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH, description="Target job description"),
):
    """Stream a cover letter token-by-token via SSE."""
    request_id = generate_request_id()
    logger.info("Request %s: Streaming cover letter started", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        async with concurrency_mgr.request_limit(request_id):
            async def event_stream() -> AsyncGenerator[str, None]:
                try:
                    async for sse_line in career_service.stream_cover_letter(
                        job_description=job_description, cv_file=cv_file
                    ):
                        if await request.is_disconnected():
                            break
                        yield sse_line
                except Exception as e:
                    logger.exception("Cover letter stream error")
                    yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Request-ID": request_id,
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Cover letter stream failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cover letter",
        )


@router.post(
    "/interview-prep/stream",
    summary="Generate interview prep questions and answers (streaming)",
    response_class=StreamingResponse,
)
async def stream_interview_prep(
    request: Request,
    job_description: str = Form(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH, description="Target job description"),
    cv_file: Optional[UploadFile] = File(None, description="Optional resume/CV PDF file"),
):
    """Stream interview prep content token-by-token via SSE."""
    request_id = generate_request_id()
    logger.info("Request %s: Streaming interview prep started", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        async with concurrency_mgr.request_limit(request_id):
            async def event_stream() -> AsyncGenerator[str, None]:
                try:
                    async for sse_line in career_service.stream_interview_prep(
                        job_description=job_description, cv_file=cv_file
                    ):
                        if await request.is_disconnected():
                            break
                        yield sse_line
                except Exception as e:
                    logger.exception("Interview prep stream error")
                    yield f"event: error\ndata: {json.dumps({'content': str(e)})}\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache, no-transform",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Request-ID": request_id,
                },
            )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Interview prep stream failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate interview prep",
        )


@router.get("/status", summary="Career assistant status")
async def career_status():
    return {
        "status": "operational" if career_agent else "unavailable",
        "error": assistant_init_error,
    }
