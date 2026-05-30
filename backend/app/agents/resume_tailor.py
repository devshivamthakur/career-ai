"""
LangGraph + True Token Streaming
================================

This implementation:
- Uses LangGraph properly
- Streams token-by-token
- Reduces latency
- Uses astream_events()
- Streams during node execution
- Production ready
"""

import asyncio
import logging
import json
import hashlib
from typing import (
    TypedDict,
    AsyncGenerator,
    Dict,
    Any,
)

from langgraph.graph import (
    StateGraph,
    END,
    START,
)

from langchain_openai import ChatOpenAI

from langchain_core.messages import (
    AIMessageChunk,
)
from langchain_core.messages import (
    HumanMessage,
)
from langchain_core.output_parsers import PydanticOutputParser


from app.core.config import settings
from langchain_core.outputs import Generation

from app.prompts.resume_tailoring_prompts import (
    PARSE_JD_PROMPT,
    EXTRACT_SKILLS_PROMPT,
    COMPARE_SKILLS_PROMPT,
    REWRITE_RESUME_PROMPT,
    POLISH_RESUME_PROMPT,
    VALIDATE_JD_PROMPT,
)
from app.schemas.resume_schemas import JDValidationResult, ResumeTailorState, SkillsComparisonResult
from app.core.caching import get_cache

logger = logging.getLogger(__name__)


def _build_langfuse_callbacks():
    callbacks = []
    if not (
        settings.LANGFUSE_PUBLIC_KEY
        or settings.LANGFUSE_SECRET_KEY
    ):
        return callbacks

    try:
        import os

        if settings.LANGFUSE_BASE_URL:
            os.environ.setdefault("LANGFUSE_BASE_URL", settings.LANGFUSE_BASE_URL)
        if settings.LANGFUSE_PUBLIC_KEY:
            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
        if settings.LANGFUSE_SECRET_KEY:
            os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)

        from langfuse.langchain import CallbackHandler

        callbacks.append(CallbackHandler())
        logger.info("LangFuse callback handler enabled for ResumeTailorAgent")
    except Exception as exc:
        logger.warning("Could not initialize LangFuse tracer: %s", exc)

    return callbacks


# =========================================================
# STATE
# =========================================================

# =========================================================
# AGENT
# =========================================================

class ResumeTailorAgent:

    def __init__(self):

        # =================================================
        # FAST MODEL
        # =================================================

        callbacks = _build_langfuse_callbacks()

        self.fast_llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.FAST_MODEL_NAME,
            temperature=0.2,
            streaming=True,
            callbacks=callbacks,
            # max_tokens=2500,
        )
        self.cacheInstance = get_cache()

        # =================================================
        # QUALITY MODEL
        # =================================================

        self.graph = self._build_graph()
        self.jdvalidation_parser = PydanticOutputParser(pydantic_object=JDValidationResult)

    @staticmethod
    def _hash_input(text: str) -> str:
        """Generate hash for caching input."""
        return hashlib.sha256(text.encode()).hexdigest()

    # =====================================================
    # BUILD GRAPH
    # =====================================================
    async def validate_job_description(
    self,
    job_description: str
) -> tuple[bool, str]:

        """
        Validate JD using structured output with caching.
        """
        prompt = job_description
        llm_string = f"validate_jd_{settings.FAST_MODEL_NAME}"

        if self.cacheInstance:
            cached_result = await self.cacheInstance.alookup(prompt, llm_string)
            if cached_result:
                logger.info("Semantic cache hit for validate_job_description.")
                try:
                    is_valid, reason = json.loads(cached_result[0].text)
                    return is_valid, reason
                except (json.JSONDecodeError, IndexError, TypeError):
                    logger.warning("Failed to parse cached validation result. Re-running validation.")

        try:

            structured_llm = (
                self.fast_llm
                | self.jdvalidation_parser
            )

            prompt_text = (
                VALIDATE_JD_PROMPT.format(
                    job_description=job_description,
                    output_format=self.jdvalidation_parser.get_format_instructions(),
                )
            )

            messages = [
                HumanMessage(content=prompt_text)
            ]

            validation_result = (
                await structured_llm.ainvoke(
                    messages
                )
            )

            logger.info(
                f"JD Validation Result: {validation_result}"
            )

            is_valid, reason = validation_result.is_valid, validation_result.reason

            if self.cacheInstance:
                result_str = json.dumps([is_valid, reason])
                await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result_str)])
                logger.info("Semantic cache updated for validate_job_description.")

            return is_valid, reason

        except Exception as e:

            logger.exception(
                f"JD validation failed: {str(e)}"
            )

            return (
                False,
                "Failed to validate job description",
            )


    def _build_graph(self):

        workflow = StateGraph(
            ResumeTailorState
        )

        workflow.add_node(
            "parallel_analyze",
            self._parallel_analyze,
        )

        workflow.add_node(
            "compare_skills",
            self._compare_skills,
        )

        workflow.add_node(
            "rewrite_resume",
            self._rewrite_resume,
        )

        workflow.add_node(
            "polish_resume",
            self._polish_resume,
        )

        workflow.add_edge(
            START,
            "parallel_analyze",
        )

        workflow.add_edge(
            "parallel_analyze",
            "compare_skills",
        )

        workflow.add_edge(
            "compare_skills",
            "rewrite_resume",
        )

        workflow.add_edge(
            "rewrite_resume",
            "polish_resume",
        )

        workflow.add_edge(
            "polish_resume",
            END,
        )

        return workflow.compile()

    # =====================================================
    # NODES
    # =====================================================

    async def _parallel_analyze(
        self,
        state: ResumeTailorState,
    ) -> Dict[str, Any]:
        """Parse JD and analyze CV in parallel for speed with caching."""
        logger.info("Starting parallel analysis...")
        
        async def parse_jd():
            prompt = PARSE_JD_PROMPT.format(job_description=state["job_description"])
            llm_string = f"parse_jd_{settings.FAST_MODEL_NAME}"
            if self.cacheInstance:
                cached = await self.cacheInstance.alookup(prompt, llm_string)
                if cached:
                    logger.info("Semantic cache hit for parse_jd.")
                    return cached[0].text
            
            response = await self.fast_llm.ainvoke(prompt)
            result = response.content
            
            if self.cacheInstance:
                await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])
            return result
        
        async def analyze_cv():
            prompt = EXTRACT_SKILLS_PROMPT.format(resume_text=state["cv_text"])
            llm_string = f"analyze_cv_{settings.FAST_MODEL_NAME}"
            if self.cacheInstance:
                cached = await self.cacheInstance.alookup(prompt, llm_string)
                if cached:
                    logger.info("Semantic cache hit for analyze_cv.")
                    return cached[0].text

            response = await self.fast_llm.ainvoke(prompt)
            result = response.content

            if self.cacheInstance:
                await self.cacheInstance.aupdate(prompt, llm_string, [Generation(text=result)])
            return result
        
        # Run both in parallel
        jd_analysis, cv_analysis = await asyncio.gather(
            parse_jd(),
            analyze_cv(),
        )
        
        logger.info("Parallel analysis completed.")
        return {
            "jd_analysis": jd_analysis,
            "cv_analysis": cv_analysis,
        }

    async def _compare_skills(
        self,
        state: ResumeTailorState,
    ) ->Dict[str, Any]:
        logger.info("Comparing skills...")
        
        structured_llm = self.fast_llm.with_structured_output(SkillsComparisonResult)

        prompt = COMPARE_SKILLS_PROMPT.format(
            job_requirements=state["jd_analysis"],
            user_profile=state["cv_analysis"],
        )

        response = await structured_llm.ainvoke(
            prompt
        )

        return {
            "skills_comparison": response.skills_comparison,
            "matched_skills": response.matched_skills,
            "missing_skills": response.missing_skills,
            "ats_score": response.ats_score
        }

    async def _rewrite_resume(
        self,
        state: ResumeTailorState,
    ) -> Dict[str, Any]:

        logger.info("Rewriting resume...")

        prompt = REWRITE_RESUME_PROMPT.format(
            resume_text=state["cv_text"],
            job_description=state["job_description"],
            analysis=state["skills_comparison"],
        )

        response = await self.fast_llm.ainvoke(
            prompt
        )

        return {
            "tailored_resume": response.content
        }

    async def _polish_resume(
        self,
        state: ResumeTailorState,
    ) -> Dict[str, Any]:

        logger.info("Polishing resume...")

        prompt = POLISH_RESUME_PROMPT.format(
            tailored_resume=state["tailored_resume"],
            job_description=state["job_description"],
        )

        response = await self.fast_llm.ainvoke(
            prompt
        )

        return {
            "final_resume": response.content
        }

    # =====================================================
    # TRUE TOKEN STREAMING WITH LANGGRAPH
    # =====================================================

    async def astream_tailored_resume(
        self,
        cv_text: str,
        job_description: str,
    ) -> AsyncGenerator[str, None]:

        """
        Stream only critical outputs (skills comparison + final resume).
        Skips intermediate analysis steps for faster UX.
        
        Optimization:
        - Parallel execution of JD parsing and CV analysis
        - Filtered output: only compare_skills and polish_resume
        - Faster perceived performance
        """

        initial_state = {
            "cv_text": cv_text,
            "job_description": job_description,
        }

        try:
            logger.info("Starting resume tailoring stream (parallel optimized)...")

            async for event in self.graph.astream_events(
                initial_state,
                version="v2",
            ):
                event_type = event["event"]
                node_name = event.get("name", "")

                # Only emit events from critical nodes
                if event_type == "on_chain_start":
                    if node_name == "compare_skills":
                        logger.info("Node 'compare_skills' started.")
                        yield json.dumps({
                            "type": "step_start",
                            "node": "compare_skills",
                            "data": "Comparing Skills"
                        }) + "\n"
                    elif node_name == "polish_resume":
                        logger.info("Node 'polish_resume' started.")
                        yield json.dumps({
                            "type": "step_start",
                            "node": "polish_resume",
                            "data": "Final Optimization"
                        }) + "\n"

                elif event_type == "on_chain_end":
                    if node_name == "compare_skills":
                        logger.info("Node 'compare_skills' ended.")
                        output = event["data"].get("output")
                        if output and isinstance(output, dict):
                            yield json.dumps({
                                "type": "step_end",
                                "node": "compare_skills",
                                "matched_skills": output.get("matched_skills", []),
                                "missing_skills": output.get("missing_skills", []),
                                "ats_score": output.get("ats_score", 0)
                            }) + "\n"

                    elif node_name == "polish_resume":
                        logger.info("Node 'polish_resume' ended.")
                        output = event["data"].get("output")
                        if output and isinstance(output, dict) and "final_resume" in output:
                            yield json.dumps({
                                "type": "step_end",
                                "node": "polish_resume",
                                "final_result": output["final_resume"]
                            }) + "\n"

                    elif node_name == "LangGraph":
                        logger.info("Resume tailoring stream completed.")
                        yield json.dumps({
                            "type": "complete",
                            "node": "LangGraph",
                            "data": "Resume Tailoring Completed"
                        }) + "\n"

        except asyncio.CancelledError:
            logger.warning("Client disconnected during stream.")
            raise

        except Exception as e:
            logger.exception("Streaming failed")
            yield json.dumps({
                "type": "error",
                "data": f"Streaming failed: {str(e)}"
            }) + "\n"