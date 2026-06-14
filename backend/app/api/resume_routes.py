"""
Resume Tailor API Endpoints - Clean, Scalable Architecture
FastAPI routes with service layer separation and production optimizations.

Architecture:
  - Route handlers: HTTP concerns only
  - Service layer: Business logic and orchestration
  - Infrastructure: Config, caching, circuit breaker, concurrency
  - Clear separation of concerns for scalability
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import StreamingResponse
import logging
from typing import AsyncGenerator, Optional
from datetime import datetime
import asyncio

from app.schemas.resume_schemas import ResumeExportRequest
from app.services.pdf_export import PDFExportService
from app.agents.resume_tailor import ResumeTailorAgent
from app.core.config import settings
from app.utils import MAX_JOB_DESCRIPTION_LENGTH, MIN_JOB_DESCRIPTION_LENGTH, MAX_FILE_SIZE_MB

# Import from API infrastructure
from app.core.infrastructure import (
    ServiceConfig,
    circuit_breaker,
    concurrency_mgr,
)
from app.services.resume_tailor_service import ResumeTailorService
from app.utils.helpers import generate_request_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resume", tags=["resume"])

# ═══════════════════════════════════════════════════════════════════════
# SERVICE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════

resume_tailor_agent: Optional[ResumeTailorAgent] = None
resume_tailor_service: Optional[ResumeTailorService] = None
agent_init_error: Optional[str] = None

try:
    resume_tailor_agent = ResumeTailorAgent()
    resume_tailor_service = ResumeTailorService(resume_tailor_agent)
    logger.info("Resume Tailor Agent and Service initialized successfully")
except Exception as e:
    error_msg = f"Failed to initialize Resume Tailor Agent: {str(e)}"
    logger.error(error_msg, exc_info=True)
    agent_init_error = error_msg


# ═══════════════════════════════════════════════════════════════════════
# DEPENDENCY CHECKS
# ═══════════════════════════════════════════════════════════════════════

def _check_service_availability() -> None:
    """Check if service is available to handle requests"""
    if not resume_tailor_agent or not resume_tailor_service:
        logger.error(f"Agent unavailable - {agent_init_error}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Resume tailoring service unavailable"
        )
    
    if not circuit_breaker.is_available():
        logger.warning("Circuit breaker open")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service experiencing high failure rate, please retry later"
        )


def _check_concurrency() -> None:
    """Check if server is at capacity"""
    active_count = concurrency_mgr.get_active_request_count()
    if active_count >= ServiceConfig.MAX_CONCURRENT_REQUESTS:
        logger.warning(f"Concurrency limit reached ({active_count})")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server at capacity, please retry in a moment"
        )


# ═══════════════════════════════════════════════════════════════════════
# PRIMARY ENDPOINT: RESUME TAILORING WITH STREAMING
# ═══════════════════════════════════════════════════════════════════════

@router.post(
    "/tailor/stream",
    summary="Tailor resume to job description (streaming)",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK
)
async def tailor_resume_stream(
    request: Request,
    resume_pdf: UploadFile = File(..., description="Resume/CV PDF file"),
    job_description: str = Form(
        ...,
        min_length=MIN_JOB_DESCRIPTION_LENGTH,
        max_length=MAX_JOB_DESCRIPTION_LENGTH,
        description="Target job description"
    ),
):
    """
    Production-grade resume tailoring endpoint with streaming.
    
    Flow:
    1. Validate service availability and concurrency
    2. Validate job description and PDF inputs
    3. Extract resume text from PDF
    4. Stream tailored resume with skills comparison and ATS score
    
    Features:
    - Parallel JD parsing and CV analysis for speed
    - Filtered output (only critical nodes emitted)
    - Server-sent events (SSE) streaming
    - Circuit breaker for service degradation
    - Backpressure handling
    
    Returns:
        StreamingResponse with SSE events containing:
        - Skills comparison (matched/missing skills, ATS score)
        - Tailored resume text
    
    Raises:
        HTTPException: Validation or processing errors
    """
    
    request_id = generate_request_id()
    request_start_time = asyncio.get_event_loop().time()
    tmp_path: Optional[str] = None
    
    logger.info(f"Request {request_id}: Resume tailoring initiated")
    
    try:
        # ─────────────────────────────────────────────────────────────────
        # PRE-FLIGHT CHECKS
        # ─────────────────────────────────────────────────────────────────
        
        _check_service_availability()
        _check_concurrency()
        
        # ─────────────────────────────────────────────────────────────────
        # REQUEST PROCESSING
        # ─────────────────────────────────────────────────────────────────
        
        async with concurrency_mgr.request_limit(request_id):
            
            logger.info(f"Request {request_id}: Validating and preparing inputs")
            cleaned_jd, cv_text = await resume_tailor_service.validate_and_prepare(
                job_description, resume_pdf
            )
            
            logger.info(f"Request {request_id}: Inputs validated, starting stream")
            
            # ─────────────────────────────────────────────────────────────────
            # STREAM RESPONSE
            # ─────────────────────────────────────────────────────────────────
            
            async def stream_gen() -> AsyncGenerator[str, None]:
                """Generate SSE stream with keep-alive heartbeat"""
                stream = resume_tailor_service.streaming_service.stream_resume_generation(
                    cv_text=cv_text,
                    job_description=cleaned_jd,
                    request_id=request_id,
                    start_time=request_start_time
                )
                
                next_chunk_task = asyncio.create_task(stream.__anext__())
                try:
                    while True:
                        if await request.is_disconnected():
                            logger.warning(f"Request {request_id}: Client disconnected")
                            break
                        
                        done, _ = await asyncio.wait(
                            {next_chunk_task},
                            timeout=ServiceConfig.KEEP_ALIVE_TIMEOUT,
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        if not done:
                            # Send keep-alive to prevent browser/proxy disconnects
                            yield ": keep-alive\n\n"
                            continue
                        
                        try:
                            chunk = next_chunk_task.result()
                        except StopAsyncIteration:
                            break
                        except Exception as e:
                            logger.error(f"Request {request_id}: Stream error - {str(e)}")
                            from app.utils.sse import sse_event
                            yield sse_event("error", {
                                "error": str(e),
                                "success": False
                            })
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
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Request {request_id}: Unhandled error - {str(e)}")
        circuit_breaker.record_failure()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while tailoring resume"
        )


# ═══════════════════════════════════════════════════════════════════════
# PDF EXPORT ENDPOINT
# ═══════════════════════════════════════════════════════════════════════

@router.post(
    "/export-pdf",
    summary="Export tailored resume as PDF",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK
)
async def export_pdf(resume_request: ResumeExportRequest):
    """
    Export tailored resume as a PDF file.
    
    Args:
        resume_request: Contains the tailored resume text
    
    Returns:
        PDF file with proper attachment headers
    
    Raises:
        HTTPException: Validation or processing errors
    """
    
    request_id = generate_request_id()
    
    try:
        if not resume_request.resume_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Resume text is required"
            )
        
        # Generate PDF with timeout protection
        pdf_buffer = await asyncio.wait_for(
            asyncio.to_thread(
                PDFExportService.generate_pdf,
                resume_request.resume_text
            ),
            timeout=30
        )
        
        logger.info(f"Request {request_id}: PDF exported successfully")
        
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="tailored_resume.pdf"',
                "Cache-Control": "no-cache",
                "X-Request-ID": request_id,
            }
        )
    
    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error(f"Request {request_id}: PDF generation timeout")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="PDF generation timed out"
        )
    except Exception as e:
        logger.error(f"Request {request_id}: PDF export error - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating PDF"
        )


# ═══════════════════════════════════════════════════════════════════════
# HEALTH & STATUS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get(
    "/status",
    summary="Service health and detailed status",
    status_code=status.HTTP_200_OK
)
async def resume_service_status():
    """
    Get detailed status of the resume tailor service.
    Useful for monitoring and debugging.
    
    Returns:
        JSON with status, configuration, capabilities, and metrics
    """
    
    return {
        "status": "operational" if resume_tailor_agent else "unavailable",
        "service": "Resume Tailor v2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "capabilities": {
            "pdf_extraction": True,
            "resume_tailoring": bool(resume_tailor_agent),
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
            "fast_model": settings.AWS_FAST_MODEL_NAME if settings.LLM_PROVIDER.lower() == "aws" else settings.FAST_MODEL_NAME,
            "quality_model": settings.QUALITY_MODEL_NAME,
            "api_configured": bool(settings.OPENAI_API_KEY)
            if settings.LLM_PROVIDER.lower() == "openai"
            else bool(
                settings.AWS_REGION
                and (
                    settings.AWS_ACCESS_KEY_ID
                    or settings.AWS_SECRET_ACCESS_KEY
                    or settings.AWS_CREDENTIALS_PROFILE_NAME
                )
            ),
        },
        "errors": {
            "initialization_error": agent_init_error,
        } if agent_init_error else {}
    }


@router.get(
    "/health",
    summary="Liveness probe",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Minimal health check for orchestration systems (K8s, Docker, etc.).
    Returns 200 if service is alive and ready to process requests.
    
    Returns:
        JSON with health status
    
    Raises:
        HTTPException: 503 if service is unavailable
    """
    
    _check_service_availability()
    return {"status": "healthy"}



