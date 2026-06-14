import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import HTTPException, status
from app.core.llm import build_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.outputs import Generation

from app.core.config import settings
from app.core.caching import get_cache
from app.prompts.jd_parsing_prompts import PARSE_JD_PROMPT
from app.prompts.skills_prompts import EXTRACT_SKILLS_PROMPT, EXTRACT_PROJECTS_PROMPT
from app.prompts.cover_letter_prompts import COVER_LETTER_PROMPT
from app.prompts.interview_prompts import INTERVIEW_PREP_PROMPT
from app.prompts.validation_prompts import VALIDATE_JD_PROMPT
from app.schemas.resume_schemas import (
    JDValidationResult,
    InterviewQuestions,
    InterviewQuestion,
    StarAnswer,
)
from app.utils import build_langfuse_callbacks

logger = logging.getLogger(__name__)


class CareerAssistantAgent:
    """AI workflow agent for cover letters and interview preparation."""

    def __init__(self):
        callbacks = build_langfuse_callbacks("CareerAssistantAgent")

        self.fast_llm = build_chat_model(streaming=False, callbacks=callbacks)
        self.streaming_llm = build_chat_model(
            streaming=True,
            callbacks=callbacks,
            max_tokens=settings.COVER_LETTER_MAX_TOKENS,
        )
        self.cacheInstance = get_cache()

        self.jdvalidation_parser = PydanticOutputParser(pydantic_object=JDValidationResult)
        self.interview_structured_llm = build_chat_model(
            streaming=False,
            callbacks=callbacks,
            max_tokens=settings.INTERVIEW_PREP_MAX_TOKENS,
        )

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

    async def generate_cover_letter(
        self,
        cv_text: str,
        job_description: str,
        company: str = "",
        role: str = "",
    ) -> str:
        """Generate a targeted cover letter using the resume and job description."""
        logger.info("Generating cover letter...")

        job_context = await self._parse_job_context(job_description)

        # Build resume profile from text (or empty if not provided)
        resume_profile = "No resume provided. Write a general cover letter based on the job description."
        if cv_text.strip():
            resume_profile = await self._extract_resume_profile(cv_text)

        # Include company and role in the job context for personalization
        if company or role:
            extra_context = f"ROLE: {role}\nCOMPANY: {company}\n\n"
            job_context = extra_context + job_context

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
        role: str = "",
        company: Optional[str] = None,
        cv_text: Optional[str] = None,
    ) -> list[InterviewQuestion]:
        """Generate interview questions and tailored answers for the job description."""
        logger.info("Generating interview prep...")

        job_context = await self._parse_job_context(job_description)
        resume_profile = "No resume text provided. Generate role-focused guidance and common developer interview questions."
        project_summary = ""

        if cv_text:
            resume_profile = await self._extract_resume_profile(cv_text)
            project_summary = await self._extract_projects(cv_text)

        # Include role and company in context
        if role or company:
            extra = f"TARGET ROLE: {role}\n"
            if company:
                extra += f"COMPANY: {company}\n"
            job_context = extra + job_context

        prompt = INTERVIEW_PREP_PROMPT.format(
            job_description=job_description,
            job_context=job_context,
            resume_profile=resume_profile,
            project_summary=project_summary,
        )

        # Use structured output to get typed InterviewQuestions
        try:
            structured_llm = self.interview_structured_llm.with_structured_output(InterviewQuestions)
            print(f"Structured LLM prompt: {prompt}")  # Debugging line
            result: InterviewQuestions = await structured_llm.ainvoke(prompt)
            return result.questions
        except Exception as exc:
            logger.warning(
                "Structured output failed for interview prep (%s), falling back to text parsing",
                exc,
            )
            # Fallback: use regular LLM call and try to parse JSON from response
            response = await self.interview_structured_llm.ainvoke(prompt)
            questions = self._parse_interview_questions_from_text(response.content)
            if questions:
                return questions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate structured interview questions. Please try again.",
            )

    @staticmethod
    def _parse_interview_questions_from_text(raw: str) -> list[InterviewQuestion] | None:
        """Parse interview questions from a raw LLM text response, handling partial data gracefully."""
        # Strip common wrappers
        cleaned = raw.strip()
        # Remove code fences if present
        if cleaned.startswith("```"):
            # Remove opening fence (possibly with "json" after it)
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                cleaned = cleaned[first_newline:]
            # Remove closing fence
            cleaned = cleaned.removesuffix("```").strip()
        # Remove trailing assistant tag
        cleaned = cleaned.removesuffix("</assistant>").strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error("Failed to decode JSON from interview prep fallback response")
            return None

        # Normalize to a list of question dicts
        question_dicts: list[dict] = []
        if isinstance(parsed, dict) and "questions" in parsed:
            question_dicts = parsed["questions"]
        elif isinstance(parsed, list):
            question_dicts = parsed
        else:
            logger.error("Unexpected JSON structure in interview prep fallback")
            return None

        valid_questions: list[InterviewQuestion] = []
        for i, qdict in enumerate(question_dicts):
            try:
                question_text = qdict.get("question", "")
                star = qdict.get("star_answer", {})

                # Build star_answer with fallback defaults for missing fields
                star_kwargs = {
                    "situation": star.get("situation") or "Context not provided by the model.",
                    "task": star.get("task") or "Task not provided by the model.",
                    "action": star.get("action") or "Action not provided by the model.",
                    "result": star.get("result") or "Result not provided by the model.",
                }
                validated = InterviewQuestion(
                    question=question_text or f"Question {i + 1}",
                    star_answer=StarAnswer(**star_kwargs),
                )
                valid_questions.append(validated)
            except Exception as q_error:
                logger.warning("Skipping malformed interview question %d: %s", i, q_error)
                continue

        if not valid_questions:
            logger.error("No valid interview questions could be parsed from fallback response")
            return None

        logger.info(
            "Parsed %d/%d valid interview questions from fallback text response",
            len(valid_questions),
            len(question_dicts),
        )
        return valid_questions

    @staticmethod
    def _extract_text_from_chunk(chunk) -> str:
        """Extract plain text from an LLM streaming chunk, handling content blocks."""
        raw = chunk.content if hasattr(chunk, "content") else (str(chunk) if chunk else "")
        if isinstance(raw, list):
            # Bedrock Converse API returns content as a list of blocks:
            #   [{"type": "text", "text": "...", "index": 0}]
            parts: list[str] = []
            for block in raw:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                elif hasattr(block, "type") and getattr(block, "type", None) == "text":
                    parts.append(getattr(block, "text", "") or str(block))
                else:
                    parts.append(str(block))
            return "".join(parts)
        if isinstance(raw, str):
            return raw
        return str(raw)

    # ── Streaming methods ──────────────────────────────────────

    async def astream_cover_letter(
        self, cv_text: str, job_description: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream a cover letter token by token.

        Yields JSON lines: ``{"type": "token", "content": "..."}``
        """
        logger.info("Streaming cover letter generation...")

        # Prepare context in parallel
        job_context, resume_profile = await asyncio.gather(
            self._parse_job_context(job_description),
            self._extract_resume_profile(cv_text),
        )

        prompt = COVER_LETTER_PROMPT.format(
            job_description=job_description,
            resume_profile=resume_profile,
            job_context=job_context,
        )

        async for chunk in self.streaming_llm.astream(prompt):
            content = self._extract_text_from_chunk(chunk)
            if content:
                yield json.dumps({"type": "token", "content": content}) + "\n"

        yield json.dumps({"type": "complete", "data": "Cover letter generation completed"}) + "\n"

    async def astream_interview_prep(
        self,
        job_description: str,
        cv_text: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream interview prep content token by token.

        Yields JSON lines: ``{"type": "token", "content": "..."}``
        """
        logger.info("Streaming interview prep generation...")

        job_context = await self._parse_job_context(job_description)
        resume_profile = "No resume text provided. Generate role-focused guidance and common developer interview questions."
        project_summary = ""

        if cv_text:
            resume_profile, project_summary = await asyncio.gather(
                self._extract_resume_profile(cv_text),
                self._extract_projects(cv_text),
            )

        prompt = INTERVIEW_PREP_PROMPT.format(
            job_description=job_description,
            job_context=job_context,
            resume_profile=resume_profile,
            project_summary=project_summary,
        )

        async for chunk in self.streaming_llm.astream(prompt):
            content = self._extract_text_from_chunk(chunk)
            if content:
                yield json.dumps({"type": "token", "content": content}) + "\n"

        yield json.dumps({"type": "complete", "data": "Interview prep generation completed"}) + "\n"
