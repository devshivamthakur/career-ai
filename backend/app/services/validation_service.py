"""
Validation services for job descriptions and request inputs.

Provides caching-aware JD validation and reusable request-scope
validation helpers used across the API layer.
"""

import json
import asyncio
import logging
from typing import Optional, Tuple

from fastapi import HTTPException, status

from app.core.caching import get_cache
from app.core.config import settings
from app.core.infrastructure import ServiceConfig
from app.utils.constants import MIN_JOB_DESCRIPTION_LENGTH, MAX_JOB_DESCRIPTION_LENGTH
from langchain_core.outputs import Generation

logger = logging.getLogger(__name__)


class ValidationService:
    """Handles validation of job descriptions with semantic caching.

    Delegates the actual LLM call to the agent and caches results
    to reduce cost and latency on repeated or similar inputs.
    """

    def __init__(self, agent) -> None:
        self.agent = agent
        self.cacheInstance = get_cache()

    async def validate_job_description(self, jd: str) -> Tuple[bool, str]:
        """Validate a job description, using semantic cache when possible.

        Returns:
            A ``(is_valid, reason)`` tuple.
        """
        prompt = jd
        llm_string = f"validate_jd_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for validate_job_description.")
                try:
                    is_valid, reason = json.loads(cached_result[0].text)
                    return is_valid, reason
                except (json.JSONDecodeError, IndexError, TypeError):
                    logger.warning(
                        "Failed to parse cached validation result. Re-running validation."
                    )

        try:
            is_valid, reason = await asyncio.wait_for(
                self.agent.validate_job_description(jd),
                timeout=ServiceConfig.JD_VALIDATION_TIMEOUT,
            )

            if self.cacheInstance:
                result_str = json.dumps([is_valid, reason])
                await self.cacheInstance.aupdate(
                    prompt, llm_string, [Generation(text=result_str)]
                )
                logger.info("Semantic cache updated for validate_job_description.")

            return is_valid, reason

        except asyncio.TimeoutError:
            logger.error("JD validation timeout")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Job description validation timed out",
            )


class RequestValidationService:
    """Validates incoming request parameters."""

    @staticmethod
    def validate_job_description_input(job_description: str) -> str:
        """Validate and clean a job description input string."""
        cleaned_jd = job_description.strip()

        if not cleaned_jd:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job description is required",
            )

        if len(cleaned_jd) < MIN_JOB_DESCRIPTION_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Job description must be at least "
                    f"{MIN_JOB_DESCRIPTION_LENGTH} characters"
                ),
            )

        if len(cleaned_jd) > MAX_JOB_DESCRIPTION_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Job description cannot exceed "
                    f"{MAX_JOB_DESCRIPTION_LENGTH} characters"
                ),
            )

        return cleaned_jd

    @staticmethod
    def validate_pdf_content_type(content_type: Optional[str]) -> None:
        """Validate that the uploaded file is a PDF."""
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed",
            )
