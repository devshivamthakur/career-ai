"""
Career Assistant Service
Separates cover letter and interview prep orchestration into a dedicated backend service module.
"""

import logging
from typing import Optional

from fastapi import HTTPException, UploadFile, status

import json
from typing import AsyncGenerator
from app.services.validation_service import ValidationService, RequestValidationService
from app.agents.career_assistant import CareerAssistantAgent
from app.core.caching import get_cache
from langchain_core.outputs import Generation
from app.core.config import settings
from app.schemas.resume_schemas import InterviewQuestion
from app.utils.sse import sse_event

logger = logging.getLogger(__name__)


class CareerAssistantService:
    """Service orchestrator for cover letters and interview prep."""

    def __init__(self, agent: CareerAssistantAgent):
        self.agent = agent
        self.validation_service = ValidationService(agent)
        self.request_validation_service = RequestValidationService()
        self.cacheInstance = get_cache()

    async def generate_cover_letter(
        self,
        job_description: str,
        company: str,
        role: str,
        resume_text: Optional[str] = None,
    ) -> str:
        cleaned_jd = self.request_validation_service.validate_job_description_input(
            job_description
        )

        prompt = f"job_description: {cleaned_jd}\ncompany: {company}\nrole: {role}\nresume: {resume_text or 'N/A'}"
        llm_string = f"cover_letter_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for generate_cover_letter.")
                return cached_result[0].text

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            logger.warning("Invalid JD for cover letter - %s", reason)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid job description: {reason}"
            )

        result = await self.agent.generate_cover_letter(
            cv_text=resume_text or "",
            job_description=cleaned_jd,
            company=company,
            role=role,
        )

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])
            logger.info("Semantic cache updated for generate_cover_letter.")

        return result

    async def generate_interview_prep(
        self,
        job_description: str,
        role: str,
        company: Optional[str] = None,
        resume_text: Optional[str] = None,
    ) -> list[InterviewQuestion]:
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)

        prompt = f"job_description: {cleaned_jd}\nrole: {role}\ncompany: {company or 'N/A'}\nresume: {resume_text or 'N/A'}"
        llm_string = f"interview_prep_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for generate_interview_prep.")
                try:
                    parsed = json.loads(cached_result[0].text)
                    return [InterviewQuestion(**q) for q in parsed]
                except (json.JSONDecodeError, TypeError, Exception):
                    logger.warning("Failed to parse cached interview prep. Re-running.")

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            logger.warning("Invalid JD for interview prep - %s", reason)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid job description: {reason}"
            )

        questions = await self.agent.generate_interview_prep(
            job_description=cleaned_jd,
            role=role,
            company=company,
            cv_text=resume_text,
        )

        if self.cacheInstance:
            json_str = json.dumps([q.dict() for q in questions])
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=json_str)])
            logger.info("Semantic cache updated for generate_interview_prep.")

        return questions

    # ── Streaming methods ──────────────────────────────────────

    async def stream_cover_letter(
        self, job_description: str, cv_file: UploadFile
    ) -> AsyncGenerator[str, None]:
        """
        Stream cover letter generation token-by-token as SSE events.
        Yields: ``event: token``, ``event: done``, ``event: error``
        """
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)
        self.request_validation_service.validate_pdf_content_type(cv_file.content_type)

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            yield sse_event("error", {"content": f"Invalid job description: {reason}"})
            return

        resume_text = await self._prepare_resume_text(cv_file)

        try:
            async for token_line in self.agent.astream_cover_letter(
                cv_text=resume_text, job_description=cleaned_jd
            ):
                # astream_cover_letter yields JSON lines: {"type": "token", "content": "..."}
                try:
                    data = json.loads(token_line.strip())
                    if data.get("type") == "token":
                        yield sse_event("token", {"content": data["content"]})
                except json.JSONDecodeError:
                    pass

            yield sse_event("done", {"content": ""})
        except Exception as e:
            logger.exception("Cover letter streaming failed")
            yield sse_event("error", {"content": str(e)})

    async def stream_interview_prep(
        self, job_description: str, cv_file: Optional[UploadFile] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream interview prep generation token-by-token as SSE events.
        Yields: ``event: token``, ``event: done``, ``event: error``
        """
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            yield sse_event("error", {"content": f"Invalid job description: {reason}"})
            return

        resume_text = None
        if cv_file is not None:
            self.request_validation_service.validate_pdf_content_type(cv_file.content_type)
            resume_text = await self._prepare_resume_text(cv_file)

        try:
            async for token_line in self.agent.astream_interview_prep(
                job_description=cleaned_jd, cv_text=resume_text
            ):
                try:
                    data = json.loads(token_line.strip())
                    if data.get("type") == "token":
                        yield sse_event("token", {"content": data["content"]})
                except json.JSONDecodeError:
                    pass

            yield sse_event("done", {"content": ""})
        except Exception as e:
            logger.exception("Interview prep streaming failed")
            yield sse_event("error", {"content": str(e)})

    # ── Streaming from text (for JSON-body endpoints) ─────────

    async def stream_cover_letter_from_text(
        self,
        job_description: str,
        company: str,
        role: str,
        resume_text: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream cover letter generation from text strings (no UploadFile).
        Yields SSE events: ``event: token``, ``event: done``, ``event: error``
        """
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            yield sse_event("error", {"content": f"Invalid job description: {reason}"})
            return

        try:
            async for token_line in self.agent.astream_cover_letter(
                cv_text=resume_text or "",
                job_description=cleaned_jd,
            ):
                try:
                    data = json.loads(token_line.strip())
                    if data.get("type") == "token":
                        yield sse_event("token", {"content": data["content"]})
                except json.JSONDecodeError:
                    pass

            yield sse_event("done", {"content": ""})
        except Exception as e:
            logger.exception("Cover letter streaming failed (from text)")
            yield sse_event("error", {"content": str(e)})

    async def stream_interview_prep_from_text(
        self,
        job_description: str,
        role: str,
        company: Optional[str] = None,
        resume_text: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream interview prep generation from text strings (no UploadFile).
        Yields SSE events: ``event: token``, ``event: done``, ``event: error``
        """
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            yield sse_event("error", {"content": f"Invalid job description: {reason}"})
            return

        try:
            async for token_line in self.agent.astream_interview_prep(
                job_description=cleaned_jd, cv_text=resume_text
            ):
                try:
                    data = json.loads(token_line.strip())
                    if data.get("type") == "token":
                        yield sse_event("token", {"content": data["content"]})
                except json.JSONDecodeError:
                    pass

            yield sse_event("done", {"content": ""})
        except Exception as e:
            logger.exception("Interview prep streaming failed (from text)")
            yield sse_event("error", {"content": str(e)})