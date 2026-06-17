"""
Resume Tailor Agent – simple step-by-step orchestration.
Uses plain async functions instead of LangGraph StateGraph.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Any

from app.core.llm import build_chat_model

from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.outputs import Generation

from app.core.config import settings
from app.prompts.jd_parsing_prompts import PARSE_JD_PROMPT
from app.prompts.skills_prompts import EXTRACT_SKILLS_PROMPT, COMPARE_SKILLS_PROMPT
from app.prompts.resume_prompts import REWRITE_RESUME_PROMPT, POLISH_RESUME_PROMPT
from app.prompts.validation_prompts import VALIDATE_JD_PROMPT
from app.schemas.resume_schemas import JDValidationResult, SkillsComparisonResult
from app.core.caching import get_cache
from app.utils import build_langfuse_callbacks

logger = logging.getLogger(__name__)


class ResumeTailorAgent:
    """
    Orchestrates resume tailoring by calling LLM steps in sequence.
    No LangGraph – just plain async functions.
    """

    def __init__(self):
        callbacks = build_langfuse_callbacks("ResumeTailorAgent")
        self.structure_llm = build_chat_model(streaming=False, callbacks=callbacks)
        self.helper_llm = build_chat_model(streaming=False, callbacks=callbacks)
        self.streaming_llm = build_chat_model(
            streaming=True,
            callbacks=callbacks,
            max_tokens=settings.AGENT_MAX_TOKENS,
        )
        self.cacheInstance = get_cache()
        self.jdvalidation_parser = PydanticOutputParser(pydantic_object=JDValidationResult)
        self.skillscomparison_parser = PydanticOutputParser(pydantic_object=SkillsComparisonResult)

    @staticmethod
    def _extract_text_from_response(response: Any) -> str:
        if hasattr(response, "content"):
            content = response.content
            if isinstance(content, list):
                texts = [str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content]
                return "".join(texts)
            return str(content)
        if hasattr(response, "generations"):
            gens = response.generations
            if gens and len(gens) > 0:
                first = gens[0]
                if isinstance(first, list) and len(first) > 0:
                    return str(getattr(first[0], "text", ""))
                return str(getattr(first, "text", ""))
        return str(response)

    async def validate_job_description(self, job_description: str) -> tuple[bool, str]:
        prompt = job_description
        llm_string = f"validate_jd_{settings.FAST_MODEL_NAME}"
        if self.cacheInstance:
            cached = await self.cacheInstance.alookup(prompt, llm_string)
            if cached:
                try:
                    is_valid, reason = json.loads(cached[0].text)
                    return is_valid, reason
                except (json.JSONDecodeError, IndexError, TypeError):
                    pass
        try:
            structured_llm = self.structure_llm | self.jdvalidation_parser
            prompt_text = VALIDATE_JD_PROMPT.format(
                job_description=job_description,
                output_format=self.jdvalidation_parser.get_format_instructions(),
            )
            result = await structured_llm.ainvoke([HumanMessage(content=prompt_text)])
            is_valid, reason = result.is_valid, result.reason
            if self.cacheInstance:
                self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=json.dumps([is_valid, reason]))])
            return is_valid, reason
        except Exception as e:
            logger.exception("JD validation failed: %s", e)
            return False, "Failed to validate job description"

    # ── Step functions (called sequentially) ─────────────────────

    async def parallel_analyze(self, cv_text: str, job_description: str) -> dict:
        async def parse_jd():
            p = PARSE_JD_PROMPT.format(job_description=job_description)
            ls = f"parse_jd_{settings.FAST_MODEL_NAME}"
            if self.cacheInstance:
                c = await self.cacheInstance.alookup(p, ls)
                if c:
                    return c[0].text
            r = await self.helper_llm.ainvoke(p)
            t = self._extract_text_from_response(r)
            if self.cacheInstance:
                self.cacheInstance.aupdate(p, ls, [Generation(text=t)])
            return t

        async def analyze_cv():
            p = EXTRACT_SKILLS_PROMPT.format(resume_text=cv_text)
            ls = f"analyze_cv_{settings.FAST_MODEL_NAME}"
            if self.cacheInstance:
                c = await self.cacheInstance.alookup(p, ls)
                if c:
                    return c[0].text
            r = await self.helper_llm.ainvoke(p)
            t = self._extract_text_from_response(r)
            if self.cacheInstance:
                self.cacheInstance.aupdate(p, ls, [Generation(text=t)])
            return t

        jd_analysis, cv_analysis = await asyncio.gather(parse_jd(), analyze_cv())
        return {"jd_analysis": jd_analysis, "cv_analysis": cv_analysis}

    async def compare_skills(self, jd_analysis: str, cv_analysis: str) -> dict:
        prompt = COMPARE_SKILLS_PROMPT.format(
            job_requirements=jd_analysis,
            user_profile=cv_analysis,
            output_format=self.skillscomparison_parser.get_format_instructions(),
        )
        try:
            structured = self.structure_llm | self.skillscomparison_parser
            response = await structured.ainvoke(prompt)
        except Exception:
            logger.warning("Pydantic parsing failed, retrying with manual fence stripping")
            raw = self._extract_text_from_response(
                await self.structure_llm.ainvoke(prompt)
            )
            # Strip markdown code fences that confuse LangChain's parser
            cleaned = raw.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            response = self.skillscomparison_parser.parse(cleaned)
        return {
            "skills_comparison": response.skills_comparison,
            "matched_skills": response.matched_skills,
            "missing_skills": response.missing_skills,
            "ats_score": response.ats_score,
        }

    async def rewrite_resume(self, cv_text: str, job_description: str, analysis: str) -> str:
        prompt = REWRITE_RESUME_PROMPT.format(resume_text=cv_text, job_description=job_description, analysis=analysis)
        response = await self.helper_llm.ainvoke(prompt)
        return self._strip_analysis_leakage(
            self._extract_text_from_response(response).removesuffix("</assistant>")
        )

    async def polish_resume(self, tailored_resume: str, job_description: str) -> str:
        prompt = POLISH_RESUME_PROMPT.format(tailored_resume=tailored_resume, job_description=job_description)
        response = await self.helper_llm.ainvoke(prompt)
        return self._strip_analysis_leakage(
            self._extract_text_from_response(response).removesuffix("</assistant>")
        )

    # ── Full pipeline (non-streaming) ────────────────────────────

    async def run_full_pipeline(self, cv_text: str, job_description: str) -> dict:
        analysis = await self.parallel_analyze(cv_text, job_description)
        skills = await self.compare_skills(analysis["jd_analysis"], analysis["cv_analysis"])
        tailored = await self.rewrite_resume(cv_text, job_description, skills["skills_comparison"])
        final = await self.polish_resume(tailored, job_description)
        return {
            "final_resume": final,
            "matched_skills": skills["matched_skills"],
            "missing_skills": skills["missing_skills"],
            "ats_score": skills["ats_score"],
        }

    # ── Post-processing ──────────────────────────────────────────

    @staticmethod
    def _strip_analysis_leakage(text: str) -> str:
        """Remove any leaked analysis labels / metadata from the final resume.

        The LLM sometimes echoes the analysis section labels (matched_skills,
        missing_skills, skills_comparison, ats_score, etc.) into the resume
        output.  This post-processing step strips those lines.
        """
        forbidden_labels = [
            "matched_skills",
            "missing_skills",
            "skills_comparison",
            "ats_score",
            "gap & alignment analysis",
            "for reference only",
        ]

        lines = text.split("\n")
        clean = []
        for line in lines:
            lower = line.strip().lower()
            # Skip lines that match or are dominated by forbidden labels
            if any(label in lower for label in forbidden_labels):
                continue
            # Skip lines containing forbidden keys
            if any(label in line for label in ["matched_skills", "missing_skills", "skills_comparison", "ats_score"]):
                continue
            clean.append(line)

        cleaned = "\n".join(clean).strip()
        # Remove leading/trailing blank lines
        return cleaned.strip()

    # ── Streaming helpers ──────────────────────────────────────

    async def _stream_llm_response(
        self, prompt: str
    ) -> AsyncGenerator[str, None]:
        """Stream an LLM response token by token, yielding SSE token events."""
        try:
            async for chunk in self.streaming_llm.astream(prompt):
                content = ""
                if hasattr(chunk, "content"):
                    raw = chunk.content or ""
                    if isinstance(raw, list):
                        # AIMessageChunk.content can be a list of content blocks
                        texts = [
                            str(item.get("text", ""))
                            if isinstance(item, dict)
                            else str(item)
                            for item in raw
                        ]
                        content = "".join(texts)
                    else:
                        content = raw
                elif isinstance(chunk, str):
                    content = chunk
                if content:
                    yield json.dumps({
                        "type": "token",
                        "content": content,
                    }) + "\n"
        except Exception as e:
            logger.exception("Token streaming failed")
            yield json.dumps({
                "type": "token",
                "content": f"\n\n[Stream error: {e}]",
            }) + "\n"

    # ── Streaming (emits step + token events) ──────────────────

    async def astream_tailored_resume(
        self, cv_text: str, job_description: str
    ) -> AsyncGenerator[str, None]:
        """
        Stream tailored resume with token-level events during LLM generation.

        Yields JSON lines:
          - ``{"type": "step_start", ...}``
          - ``{"type": "token", "content": "..."}``  (token-by-token)
          - ``{"type": "step_end", ...}``
          - ``{"type": "complete", ...}``
          - ``{"type": "error", ...}``
        """
        try:
            # ── Parallel analysis (no streaming needed) ──────────
            analysis = await self.parallel_analyze(cv_text, job_description)

            # ── Skills comparison ────────────────────────────────
            yield json.dumps({
                "type": "step_start",
                "node": "compare_skills",
                "data": "Comparing Skills",
            }) + "\n"
            skills = await self.compare_skills(
                analysis["jd_analysis"], analysis["cv_analysis"]
            )
            yield json.dumps({
                "type": "step_end",
                "node": "compare_skills",
                "matched_skills": skills["matched_skills"],
                "missing_skills": skills["missing_skills"],
                "ats_score": skills["ats_score"],
            }) + "\n"

            # ── Rewrite resume (streaming tokens) ────────────────
            yield json.dumps({
                "type": "step_start",
                "node": "rewrite_resume",
                "data": "Rewriting resume for ATS optimization",
            }) + "\n"

            rewrite_prompt = REWRITE_RESUME_PROMPT.format(
                resume_text=cv_text,
                job_description=job_description,
                analysis=skills["skills_comparison"],
            )
            tailored_chunks: list[str] = []
            async for token_line in self._stream_llm_response(rewrite_prompt):
                yield token_line
                # Accumulate for the polish step
                try:
                    td = json.loads(token_line.strip())
                    if td.get("type") == "token":
                        tailored_chunks.append(td.get("content", ""))
                except json.JSONDecodeError:
                    pass
            tailored_raw = "".join(tailored_chunks).removesuffix("</assistant>")
            tailored = self._strip_analysis_leakage(tailored_raw)

            # ── Polish resume (streaming tokens) ─────────────────
            yield json.dumps({
                "type": "step_start",
                "node": "polish_resume",
                "data": "Polishing final resume",
            }) + "\n"

            polish_prompt = POLISH_RESUME_PROMPT.format(
                tailored_resume=tailored,
                job_description=job_description,
            )
            final_chunks: list[str] = []
            async for token_line in self._stream_llm_response(polish_prompt):
                yield token_line
                try:
                    td = json.loads(token_line.strip())
                    if td.get("type") == "token":
                        final_chunks.append(td.get("content", ""))
                except json.JSONDecodeError:
                    pass
            final_raw = "".join(final_chunks).removesuffix("</assistant>")
            final = self._strip_analysis_leakage(final_raw)

            yield json.dumps({
                "type": "step_end",
                "node": "polish_resume",
                "final_result": final,
            }) + "\n"

            yield json.dumps({
                "type": "complete",
                "data": "Resume tailoring completed",
            }) + "\n"

        except asyncio.CancelledError:
            logger.warning("Client disconnected during stream")
            raise
        except Exception as e:
            logger.exception("Streaming failed")
            yield json.dumps({
                "type": "error",
                "data": f"Streaming failed: {str(e)}",
            }) + "\n"