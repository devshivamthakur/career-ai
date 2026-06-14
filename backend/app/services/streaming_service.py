"""
SSE streaming service for resume tailoring responses.

Handles backpressure, keep-alive signals, caching of final results,
and circuit-breaker health tracking during long-running streams.
"""

import json
import time
import asyncio
import logging
from datetime import datetime
from typing import AsyncGenerator

from app.core.caching import get_cache
from app.core.infrastructure import circuit_breaker
from app.core.config import settings
from app.utils.sse import sse_event
from app.utils.constants import STREAM_DELAY
from langchain_core.outputs import Generation

logger = logging.getLogger(__name__)


class StreamingService:
    """Handles SSE streaming with backpressure, error handling, and caching."""

    def __init__(self, agent) -> None:
        self.agent = agent
        self.cacheInstance = get_cache()

    async def stream_resume_generation(
        self,
        cv_text: str,
        job_description: str,
        request_id: str,
        start_time: float,
    ) -> AsyncGenerator[str, None]:
        """Stream a tailored resume with parallel execution and filtered output.

        Caches the final result and serves it directly on cache hit.
        Yields ``sse_event`` strings for each lifecycle event.
        """
        try:
            yield sse_event("started", {
                "message": "Resume tailoring started (parsing & analysing in parallel)",
                "request_id": request_id,
                "timestamp": datetime.utcnow().isoformat(),
            })

            final_data_to_cache = {}
            prompt = job_description
            llm_string = f"tailor_resume_{settings.FAST_MODEL_NAME}"

            async for event_data in self.agent.astream_tailored_resume(
                cv_text=cv_text,
                job_description=job_description,
            ):
                if not event_data:
                    continue

                try:
                    event_obj = json.loads(event_data)
                    event_type = event_obj.get("type")

                    # Collect data for caching
                    if event_type == "step_end":
                        if event_obj.get("node") == "compare_skills":
                            final_data_to_cache["matched_skills"] = event_obj.get("matched_skills", [])
                            final_data_to_cache["missing_skills"] = event_obj.get("missing_skills", [])
                            final_data_to_cache["ats_score"] = event_obj.get("ats_score", 0)
                        elif event_obj.get("node") == "polish_resume":
                            final_data_to_cache["final_resume"] = event_obj.get("final_result", "")

                    yield sse_event(event_type, event_obj)

                except json.JSONDecodeError:
                    logger.warning("Failed to parse event JSON: %s", event_data)
                    continue

                if STREAM_DELAY:
                    await asyncio.sleep(STREAM_DELAY)

            total_time = round(time.time() - start_time, 2)
            yield sse_event("completed", {
                "success": True,
                "request_id": request_id,
                "processing_time_seconds": total_time,
                "timestamp": datetime.utcnow().isoformat(),
            })

            # Update cache at the end
            if self.cacheInstance and "final_resume" in final_data_to_cache:
                await self.cacheInstance.aupdate(
                    prompt, llm_string, [Generation(text=json.dumps(final_data_to_cache))]
                )
                logger.info("Semantic cache updated for tailor_resume_stream.")

            circuit_breaker.record_success()

        except asyncio.CancelledError:
            logger.warning("Request %s: Client disconnected during stream", request_id)
            raise

        except Exception as stream_error:
            logger.exception(
                "Request %s: Streaming error: %s", request_id, stream_error
            )
            circuit_breaker.record_failure()

            yield sse_event("error", {
                "success": False,
                "request_id": request_id,
                "error": str(stream_error),
                "error_type": type(stream_error).__name__,
                "timestamp": datetime.utcnow().isoformat(),
            })
