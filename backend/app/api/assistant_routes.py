"""
CareerAI Assistant API routes.
Handles cover letter generation and interview prep endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import JSONResponse
import logging
import asyncio
from typing import Optional

from app.agents.career_assistant import CareerAssistantAgent
from app.api.config import circuit_breaker, concurrency_mgr, ServiceConfig
from app.services.career_assistant_service import CareerAssistantService
from app.api.services import generate_request_id
from app.utils import MAX_JOB_DESCRIPTION_LENGTH, MIN_JOB_DESCRIPTION_LENGTH

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


@router.post("/cover-letter", summary="Generate a tailored cover letter")
async def generate_cover_letter(
    request: Request,
    cv_file: UploadFile = File(..., description="Resume/CV PDF file"),
    job_description: str = Form(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH, description="Target job description"),
):
    request_id = generate_request_id()
    logger.info("Request %s: Cover letter generation started", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        async with concurrency_mgr.request_limit(request_id):
            cover_letter = await career_service.generate_cover_letter(
                job_description=job_description,
                cv_file=cv_file,
            )
            logger.info("Request %s: Cover letter generation completed", request_id)

            return JSONResponse({"cover_letter": cover_letter})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Cover letter generation failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate cover letter"
        )


@router.post("/interview-prep", summary="Generate interview prep questions and answers")
async def generate_interview_prep(
    request: Request,
    job_description: str = Form(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH, description="Target job description"),
    cv_file: Optional[UploadFile] = File(None, description="Optional resume/CV PDF file"),
):
    request_id = generate_request_id()
    logger.info("Request %s: Interview prep generation started", request_id)

    try:
        _check_service_availability()
        _check_concurrency()

        async with concurrency_mgr.request_limit(request_id):
            interview_prep = await career_service.generate_interview_prep(
                job_description=job_description,
                cv_file=cv_file,
            )
            logger.info("Request %s: Interview prep generation completed", request_id)
            return JSONResponse({"interview_prep": interview_prep})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Request %s: Interview prep generation failed: %s", request_id, exc)
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate interview prep"
        )


@router.get("/status", summary="Career assistant status")
async def career_status():
    return {
        "status": "operational" if career_agent else "unavailable",
        "error": assistant_init_error,
    }
