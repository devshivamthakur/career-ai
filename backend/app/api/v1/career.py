"""
Career API v1 — cover letter & interview prep (thin HTTP layer).

All business logic lives in ``app.services.career_assistant_service``.
Routers only marshal HTTP concerns: params, pre-flight deps, streaming.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.api.v1.deps import (
    ensure_capacity,
    ensure_circuit_closed,
    get_career_assistant_service,
)
from app.core.infrastructure import circuit_breaker
from app.schemas.resume_schemas import (
    CoverLetterRequest,
    InterviewPrepRequest,
    InterviewPrepResponse,
)
from app.services.career_assistant_service import CareerAssistantService
from app.utils.constants import MAX_JOB_DESCRIPTION_LENGTH, MIN_JOB_DESCRIPTION_LENGTH
from app.utils.helpers import generate_request_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/career", tags=["career"])


def _sse_headers(request_id: str) -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "X-Request-ID": request_id,
    }


def _stream_response(
    request: Request,
    stream: AsyncGenerator[str, None],
    request_id: str,
) -> StreamingResponse:
    """Wrap a service async-generator in a disconnect-aware SSE response."""

    async def event_stream():
        try:
            async for sse_line in stream:
                if await request.is_disconnected():
                    logger.warning("Request %s: client disconnected", request_id)
                    break
                yield sse_line
        except Exception as exc:
            logger.exception("Request %s: stream error", request_id)
            circuit_breaker.record_failure()
            yield f"event: error\ndata: {exc}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_sse_headers(request_id),
    )


@router.post(
    "/cover-letter",
    summary="Generate a tailored cover letter (streaming)",
    response_class=StreamingResponse,
)
async def generate_cover_letter(
    request: Request,
    body: CoverLetterRequest,
    service: CareerAssistantService = Depends(get_career_assistant_service),
    _: None = Depends(ensure_capacity),
    __: None = Depends(ensure_circuit_closed),
):
    """Generate a tailored cover letter with SSE streaming (JSON body)."""
    request_id = generate_request_id()
    logger.info("Request %s: Cover letter generation started (streaming)", request_id)

    stream = service.stream_cover_letter_from_text(
        job_description=body.job_description,
        company=body.company,
        role=body.role,
        resume_text=body.resume_text,
    )
    return _stream_response(request, stream, request_id)


@router.post(
    "/interview-prep",
    summary="Generate interview prep questions",
    response_model=InterviewPrepResponse,
)
async def generate_interview_prep(
    body: InterviewPrepRequest,
    service: CareerAssistantService = Depends(get_career_assistant_service),
    _: None = Depends(ensure_capacity),
    __: None = Depends(ensure_circuit_closed),
):
    """Generate interview prep questions and answers with structured output."""
    request_id = generate_request_id()
    logger.info("Request %s: Interview prep generation started", request_id)

    try:
        questions = await service.generate_interview_prep(
            job_description=body.job_description,
            role=body.role,
            company=body.company,
            resume_text=body.resume_text,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Interview prep generation failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=500,
            detail="Failed to generate interview prep",
        )

    logger.info(
        "Request %s: Interview prep generation completed (%d questions)",
        request_id,
        len(questions),
    )
    return InterviewPrepResponse(questions=questions)


@router.post(
    "/cover-letter/stream",
    summary="Generate a tailored cover letter from a PDF (streaming)",
    response_class=StreamingResponse,
)
async def stream_cover_letter(
    request: Request,
    cv_file: UploadFile = File(..., description="Resume/CV PDF file"),
    job_description: str = Form(
        ...,
        min_length=MIN_JOB_DESCRIPTION_LENGTH,
        max_length=MAX_JOB_DESCRIPTION_LENGTH,
        description="Target job description",
    ),
    service: CareerAssistantService = Depends(get_career_assistant_service),
    _: None = Depends(ensure_capacity),
    __: None = Depends(ensure_circuit_closed),
):
    """Stream a cover letter token-by-token via SSE (multipart upload)."""
    request_id = generate_request_id()
    logger.info("Request %s: Streaming cover letter started", request_id)

    stream = service.stream_cover_letter(
        job_description=job_description,
        cv_file=cv_file,
    )
    return _stream_response(request, stream, request_id)


@router.post(
    "/interview-prep/stream",
    summary="Generate interview prep questions and answers (streaming)",
    response_class=StreamingResponse,
)
async def stream_interview_prep(
    request: Request,
    job_description: str = Form(
        ...,
        min_length=MIN_JOB_DESCRIPTION_LENGTH,
        max_length=MAX_JOB_DESCRIPTION_LENGTH,
        description="Target job description",
    ),
    cv_file: Optional[UploadFile] = File(None, description="Optional resume/CV PDF file"),
    service: CareerAssistantService = Depends(get_career_assistant_service),
    _: None = Depends(ensure_capacity),
    __: None = Depends(ensure_circuit_closed),
):
    """Stream interview prep content token-by-token via SSE."""
    request_id = generate_request_id()
    logger.info("Request %s: Streaming interview prep started", request_id)

    stream = service.stream_interview_prep(
        job_description=job_description,
        cv_file=cv_file,
    )
    return _stream_response(request, stream, request_id)


@router.get("/status", summary="Career assistant status")
async def career_status(
    service: CareerAssistantService = Depends(get_career_assistant_service),
):
    return {"status": "operational"}
