"""
Career Assistant Service
Separates cover letter and interview prep orchestration into a dedicated backend service module.
"""

import logging
import os
from contextlib import suppress
from typing import Optional

from fastapi import HTTPException, status, UploadFile

from app.api.services import ValidationService, PDFService, FileHandlingService, RequestValidationService
from app.agents.career_assistant import CareerAssistantAgent
from app.core.caching import get_cache
from langchain_core.outputs import Generation
from app.core.config import settings

logger = logging.getLogger(__name__)


class CareerAssistantService:
    """Service orchestrator for cover letters and interview prep."""

    def __init__(self, agent: CareerAssistantAgent):
        self.agent = agent
        self.validation_service = ValidationService(agent)
        self.pdf_service = PDFService()
        self.file_service = FileHandlingService()
        self.request_validation_service = RequestValidationService()
        self.cacheInstance = get_cache()

    async def _prepare_resume_text(self, cv_file: UploadFile) -> str:
        tmp_path = await self.file_service.save_uploaded_file(cv_file)

        try:
            self.file_service.validate_pdf_file(tmp_path)
            logger.info("Extracting resume text for assistant service")
            resume_text = await self.pdf_service.extract_resume_text(tmp_path)
            if not resume_text.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Extracted resume text is empty"
                )
            return resume_text
        finally:
            with suppress(Exception):
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    async def generate_cover_letter(self, job_description: str, cv_file: UploadFile) -> str:
        cleaned_jd = self.request_validation_service.validate_job_description_input(
            job_description
        )
        self.request_validation_service.validate_pdf_content_type(cv_file.content_type)
        resume_text = await self._prepare_resume_text(cv_file)
        
        prompt = f"job_description: {cleaned_jd}\n---\nresume: {resume_text}"
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

        result = await self.agent.generate_cover_letter(cv_text=resume_text, job_description=cleaned_jd)

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])
            logger.info("Semantic cache updated for generate_cover_letter.")

        return result

    async def generate_interview_prep(self, job_description: str, cv_file: Optional[UploadFile] = None) -> str:
        cleaned_jd = self.request_validation_service.validate_job_description_input(job_description)

        resume_text = None
        if cv_file is not None:
            self.request_validation_service.validate_pdf_content_type(cv_file.content_type)
            resume_text = await self._prepare_resume_text(cv_file)
            
        prompt = f"job_description: {cleaned_jd}\n---\nresume: {resume_text or 'N/A'}"
        llm_string = f"interview_prep_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for generate_interview_prep.")
                return cached_result[0].text

        is_valid_jd, reason = await self.validation_service.validate_job_description(cleaned_jd)
        if not is_valid_jd:
            logger.warning("Invalid JD for interview prep - %s", reason)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid job description: {reason}"
            )

        result = await self.agent.generate_interview_prep(job_description=cleaned_jd, cv_text=resume_text)

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])
            logger.info("Semantic cache updated for generate_interview_prep.")

        return result