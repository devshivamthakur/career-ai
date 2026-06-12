import asyncio
import logging
import os
import hashlib
import json
from typing import Optional

from app.core.llm import build_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.outputs import Generation

from app.core.config import settings
from app.core.caching import get_cache
from app.prompts.resume_tailoring_prompts import (
    PARSE_JD_PROMPT,
    EXTRACT_SKILLS_PROMPT,
    EXTRACT_PROJECTS_PROMPT,
    COVER_LETTER_PROMPT,
    INTERVIEW_PREP_PROMPT,
    VALIDATE_JD_PROMPT,
)
from app.schemas.resume_schemas import JDValidationResult

logger = logging.getLogger(__name__)

def _build_langfuse_callbacks():
    callbacks = []
    if not (
        settings.LANGFUSE_PUBLIC_KEY
        or settings.LANGFUSE_SECRET_KEY
    ):
        return callbacks

    if settings.LANGFUSE_BASE_URL:
        os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_BASE_URL)
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
    if settings.LANGFUSE_SECRET_KEY:
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
    try:
        from langfuse.langchain import CallbackHandler

        callbacks.append(CallbackHandler())
        logger.info("LangFuse callback handler enabled for CareerAssistantAgent")
    except Exception as exc:
        logger.warning("LangFuse callback handler unavailable: %s", exc)

    return callbacks


class CareerAssistantAgent:
    """AI workflow agent for cover letters and interview preparation."""

    def __init__(self):
        callbacks = _build_langfuse_callbacks()

        self.fast_llm = build_chat_model(streaming=False, callbacks=callbacks)
        self.cacheInstance = get_cache()

        self.jdvalidation_parser = PydanticOutputParser(pydantic_object=JDValidationResult)

    def _build_callbacks(self):
        """Return additional callbacks if configured."""
        return []

    @staticmethod
    def _hash_input(text: str) -> str:
        """Generate hash for caching input."""
        return hashlib.sha256(text.encode()).hexdigest()

    async def validate_job_description(self, job_description: str) -> tuple[bool, str]:
        """Validate whether the input text is a processable job description with caching."""
        logger.info("Validating job description for assistant workflow...")
        prompt = job_description
        llm_string = f"validate_jd_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for career_assistant.validate_job_description.")
                try:
                    is_valid, reason = json.loads(cached_result[0].text)
                    return is_valid, reason
                except (json.JSONDecodeError, IndexError, TypeError):
                    logger.warning("Failed to parse cached validation result. Re-running validation.")

        try:
            structured_llm = self.fast_llm | self.jdvalidation_parser
            prompt_text = VALIDATE_JD_PROMPT.format(
                job_description=job_description,
                output_format=self.jdvalidation_parser.get_format_instructions(),
            )
            messages = [HumanMessage(content=prompt_text)]
            validation_result = await structured_llm.ainvoke(messages)
            is_valid, reason = validation_result.is_valid, validation_result.reason

            if self.cacheInstance:
                result_str = json.dumps([is_valid, reason])
                await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result_str)])
                logger.info("Semantic cache updated for career_assistant.validate_job_description.")

            return is_valid, reason
        except Exception as exc:
            logger.exception("JD validation failed in assistant workflow: %s", exc)
            return False, "Failed to validate job description"

    async def _parse_job_context(self, job_description: str) -> str:
        """Parse job context with caching."""
        logger.info("Parsing job description for context...")
        prompt = PARSE_JD_PROMPT.format(job_description=job_description)
        llm_string = f"parse_jd_context_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached = await self.cacheInstance.alookup(prompt, llm_string)
            if cached:
                logger.info("Semantic cache hit for _parse_job_context.")
                return cached[0].text

        response = await self.fast_llm.ainvoke(prompt)
        result = response.content

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])

        return result

    async def _extract_resume_profile(self, resume_text: str) -> str:
        """Extract resume profile with caching."""
        logger.info("Extracting resume profile for assistant workflow...")
        prompt = EXTRACT_SKILLS_PROMPT.format(resume_text=resume_text)
        llm_string = f"extract_resume_profile_{settings.FAST_MODEL_NAME}"
        
        if self.cacheInstance:
            cached = await self.cacheInstance.alookup(prompt, llm_string)
            if cached:
                logger.info("Semantic cache hit for _extract_resume_profile.")
                return cached[0].text

        response = await self.fast_llm.ainvoke(prompt)
        result = response.content

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])

        return result

    async def _extract_projects(self, resume_text: str) -> str:
        """Extract projects with caching."""
        prompt = EXTRACT_PROJECTS_PROMPT.format(resume_text=resume_text)
        llm_string = f"extract_projects_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached = await self.cacheInstance.alookup(prompt, llm_string)
            if cached:
                logger.info("Semantic cache hit for _extract_projects.")
                return cached[0].text
        
        response = await self.fast_llm.ainvoke(prompt)
        result = response.content

        if self.cacheInstance:
            await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])

        return result

    async def generate_cover_letter(self, cv_text: str, job_description: str) -> str:
        """Generate a targeted cover letter using the resume and job description."""
        logger.info("Generating cover letter...")

        job_context = await self._parse_job_context(job_description)
        resume_profile = await self._extract_resume_profile(cv_text)

        prompt = COVER_LETTER_PROMPT.format(
            job_description=job_description,
            resume_profile=resume_profile,
            job_context=job_context,
        )

        response = await self.fast_llm.ainvoke(prompt)
        return response.content.removesuffix("</assistant>")

    async def generate_interview_prep(
        self,
        job_description: str,
        cv_text: Optional[str] = None,
    ) -> str:
        """Generate interview questions and tailored answers for the job description."""
        logger.info("Generating interview prep...")

        job_context = await self._parse_job_context(job_description)
        resume_profile = "No resume text provided. Generate role-focused guidance and common developer interview questions."
        project_summary = ""

        if cv_text:
            resume_profile = await self._extract_resume_profile(cv_text)
            project_summary = await self._extract_projects(cv_text)

        prompt = INTERVIEW_PREP_PROMPT.format(
            job_description=job_description,
            job_context=job_context,
            resume_profile=resume_profile,
            project_summary=project_summary,
        )

        response = await self.fast_llm.ainvoke(prompt)
        return response.content.removesuffix("</assistant>")
