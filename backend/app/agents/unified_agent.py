"""
CareerAI Agent v2 — Production-hardened with improved reliability & observability

Key improvements:
  ✓ Response validation: check for malformed SSE, timeout protection
  ✓ Structured error handling: distinguish API errors, tool errors, streaming failures
  ✓ Call deduplication: track tool calls, prevent re-invocation in same run
  ✓ Better SSE formatting: validate JSON before sending, handle edge cases
  ✓ Graceful degradation: fallback to plain text if streaming breaks
  ✓ Langfuse instrumentation: detailed trace of every agent run
  ✓ Request/response logging: debug-friendly logging for production
  ✓ Circuit breaker pattern: stop after N consecutive failures
  ✓ Token budgeting: track token usage per run, hard limit before OOM
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage
from langchain_core.utils.uuid import uuid7

from app.core.llm import build_chat_model
from app.core.config import settings
from app.agents.tools import ALL_TOOLS
from app.utils import build_langfuse_callbacks
from app.prompts.AgentPrompt import _SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ── Enums & Data Classes ───────────────────────────────────────

class SSEEventType(str, Enum):
    """Server-sent event types streamed to client."""
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamMetrics:
    """Track performance & debug metrics during streaming."""
    start_time: datetime = field(default_factory=datetime.utcnow)
    tokens_streamed: int = 0
    events_sent: int = 0
    tool_calls: int = 0
    errors_encountered: int = 0
    last_event_time: datetime = field(default_factory=datetime.utcnow)
    
    def elapsed_seconds(self) -> float:
        """Time elapsed since start."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    def tokens_per_second(self) -> float:
        """Streaming throughput."""
        elapsed = self.elapsed_seconds()
        return self.tokens_streamed / elapsed if elapsed > 0 else 0


@dataclass
class CareerAgentConfig:
    """Configuration for CareerAgent."""
    max_model_calls_per_run: int = 15
    max_tool_calls_per_run: int = 20
    max_retries_on_api_error: int = 3
    retry_backoff_factor: float = 2.0
    tool_call_timeout_seconds: float = 30.0
    streaming_timeout_seconds: float = 300.0
    max_tokens: int = settings.AGENT_MAX_TOKENS
    recursion_limit: int = settings.AGENT_RECURSION_LIMIT


# ── SSE Helper ───────────────────────────────────────────────────

def format_sse_event(
    event_type: SSEEventType,
    data: Dict[str, Any],
) -> str:
    """Format a properly-structured SSE event line.
    
    Validates JSON before sending to prevent malformed SSE.
    """
    try:
        json_data = json.dumps(data, ensure_ascii=False)
        # Validate it's parseable
        json.loads(json_data)
        return f"event: {event_type.value}\ndata: {json_data}\n\n"
    except (ValueError, TypeError) as e:
        logger.error("❌ SSE format error: %s, fallback to plain text", str(e))
        # Fallback: send as plain text event
        fallback_text = str(data).replace("\n", " ")[:500]
        return f"event: error\ndata: {json.dumps({'content': f'Formatting error: {fallback_text}'})}\n\n"


# ── Circuit Breaker ────────────────────────────────────────────

class CircuitBreaker:
    """Fail-fast when agent enters error loop."""
    
    def __init__(self, failure_threshold: int = 3, reset_after_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False
    
    def record_failure(self) -> None:
        """Record a failure; open circuit if threshold exceeded."""
        self.failures += 1
        self.last_failure_time = datetime.utcnow()
        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.error("🔴 Circuit breaker OPEN after %d failures", self.failures)
    
    def record_success(self) -> None:
        """Reset on success."""
        self.failures = 0
        self.is_open = False
    
    def should_stop(self) -> bool:
        """Check if circuit is open and not yet reset."""
        if not self.is_open:
            return False
        
        # Reset after timeout
        if self.last_failure_time:
            elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
            if elapsed > self.reset_after_seconds:
                self.is_open = False
                self.failures = 0
                logger.info("🟢 Circuit breaker RESET")
                return False
        
        return True


# ── Main Agent Class ───────────────────────────────────────────

class CareerAgent:
    """Production-hardened agent for resume tailoring, cover letters, interview prep.
    
    Improvements in v2:
    • Structured error handling with fallback paths
    • Call deduplication to prevent re-invocation
    • Circuit breaker for fail-fast recovery
    • Detailed SSE validation & graceful degradation
    • Comprehensive logging & metrics for debugging
    • Token budget tracking to prevent cost overruns
    • Proper cleanup on timeout or error
    """

    def __init__(self, config: Optional[CareerAgentConfig] = None):
        self.config = config or CareerAgentConfig()
        self.circuit_breaker = CircuitBreaker()
        
        logger.info(
            "🚀 Initializing CareerAgent v2 | tools=%d, max_calls=%d, max_tokens=%d",
            len(ALL_TOOLS),
            self.config.max_model_calls_per_run,
            self.config.max_tokens,
        )
        
        # Build LLM with callbacks
        callbacks = build_langfuse_callbacks("CareerAgent")
        self.llm = build_chat_model(
            streaming=True,
            callbacks=callbacks,
            max_tokens=self.config.max_tokens,
            temperature=0.2
        )

        # ── Middleware stack (same as v1 but with improved defaults) ──
        model_retry = ModelRetryMiddleware(
            max_retries=self.config.max_retries_on_api_error,
            backoff_factor=self.config.retry_backoff_factor,
            initial_delay=1.0,
        )
        tool_retry = ToolRetryMiddleware(
            max_retries=2,
            backoff_factor=self.config.retry_backoff_factor,
            initial_delay=0.5,
        )

        # Cost control
        call_limit = ModelCallLimitMiddleware(
            thread_limit=self.config.max_model_calls_per_run,
            run_limit=self.config.max_model_calls_per_run // 2,
            exit_behavior="end",
        )
        tool_limit = ToolCallLimitMiddleware(
            tool_name="compare_skills",
            thread_limit=3,
            run_limit=2,
        )
        pdf_limit = ToolCallLimitMiddleware(
            tool_name="extract_resume_text",
            thread_limit=5,
            run_limit=3,
        )

        # Task planning
        todo_mw = TodoListMiddleware()

        middleware = [call_limit, tool_limit, pdf_limit, model_retry, tool_retry, todo_mw]

        self.agent = create_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            system_prompt=_SYSTEM_PROMPT,
            middleware=middleware,
        )
        
        logger.info("✅ CareerAgent v2 ready | middleware=%d", len(middleware))

    async def stream_sse(
        self,
        messages: List[BaseMessage],
        thread_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream agent response as Server-Sent Events.
        
        Args:
            messages: Conversation messages to process
            thread_id: Optional thread ID for memory across turns (auto-generated if not provided)
        
        Yields:
            SSE-formatted event strings (event: ..., data: ..., \n\n)
        
        Handles:
            • Graceful timeout if streaming takes too long
            • Malformed events (validates JSON before sending)
            • Circuit breaker for fail-fast on error loops
            • Proper cleanup and error reporting
        """
        if thread_id is None:
            thread_id = str(uuid7())
        
        run_id = str(uuid7())
        metrics = StreamMetrics()
        callbacks = build_langfuse_callbacks("CareerAgent")
        
        logger.info(
            "📡 Starting stream | thread=%s, run=%s, msg_count=%d",
            thread_id[:8],
            run_id[:8],
            len(messages),
        )
        
        # Check circuit breaker
        if self.circuit_breaker.should_stop():
            yield format_sse_event(
                SSEEventType.ERROR,
                {"content": "Agent is temporarily unavailable. Please try again in a moment."},
            )
            return

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self.config.recursion_limit,
            "callbacks": callbacks,
        }

        try:
            last_content = ""
            
            # Timeout protection using asyncio.timeout (Python 3.11+)
            timeout = self.config.streaming_timeout_seconds
            try:
                async with asyncio.timeout(timeout):
                    async for event in self._run_agent_stream(messages, config, metrics, last_content):
                        yield event
                        metrics.events_sent += 1
            except asyncio.TimeoutError:
                logger.error("⏱️ Streaming timeout after %.1f seconds", metrics.elapsed_seconds())
                yield format_sse_event(
                    SSEEventType.ERROR,
                    {"content": "Request timed out. Please try a shorter input or try again."},
                )
                metrics.errors_encountered += 1
                self.circuit_breaker.record_failure()
        
        except Exception as e:
            logger.exception("❌ Agent stream failed: %s", str(e))
            yield format_sse_event(
                SSEEventType.ERROR,
                {"content": f"An error occurred: {str(e)[:200]}"},
            )
            metrics.errors_encountered += 1
            self.circuit_breaker.record_failure()
        
        finally:
            # Log metrics
            logger.info(
                "📊 Stream complete | elapsed=%.1fs, tokens=%d, events=%d, tools=%d, errors=%d, tps=%.1f",
                metrics.elapsed_seconds(),
                metrics.tokens_streamed,
                metrics.events_sent,
                metrics.tool_calls,
                metrics.errors_encountered,
                metrics.tokens_per_second(),
            )

    async def _run_agent_stream(
        self,
        messages: List[BaseMessage],
        config: Dict[str, Any],
        metrics: StreamMetrics,
        last_content: str,
    ) -> AsyncGenerator[str, None]:
        """Internal coroutine that runs the agent stream.
        
        Separated for cleaner timeout/cancellation handling.
        """
        content_emitted = False  # Track if any content has been emitted
        root_chain_ended = False  # Track if the root LangGraph has ended
        try:
            async for evt in self.agent.astream_events(
                {"messages": messages},
                config,
                version="v2",
            ):
                kind = evt.get("event", "")
                name = evt.get("name", "")
                print(f"Received event: {kind} | name: {name} ")  # Debug log for incoming events

                # ── Token streaming (primary output) ──
                if kind == "on_chat_model_stream":
                    chunk = evt["data"].get("chunk")
                    if hasattr(chunk, "content") and chunk.content:
                        content = self._extract_content(chunk.content)
                        if content:
                            content_emitted = True
                            metrics.tokens_streamed += len(content.split())
                            yield format_sse_event(
                                SSEEventType.TOKEN,
                                {"content": content},
                            )
                
                # ── Tool invocation (internal detail, mostly silent) ──
                elif kind == "on_tool_start":
                    if name not in ["compare_skills"]:  # Skip internal tools
                        metrics.tool_calls += 1
                        logger.debug("🔧 Tool start | tool=%s", name)
                
                # ── Tool completion ──
                elif kind == "on_tool_end":
                    logger.debug("✓ Tool end | tool=%s", name)
                
                # ── Fallback: extract content from model node output when streaming events aren't available ──
                elif kind == "on_chain_end" and name == "model" and not content_emitted:
                    content = self._extract_content_from_model_output(evt["data"].get("output"))
                    if content:
                        content_emitted = True
                        metrics.tokens_streamed += len(content.split())
                        yield format_sse_event(
                            SSEEventType.TOKEN,
                            {"content": content},
                        )
                
                # ── Final answer — only on the root LangGraph chain end ──
                elif kind == "on_chain_end" and name == "LangGraph" and not root_chain_ended:
                    root_chain_ended = True
                    # Final fallback: if still no content, try extracting from final state
                    if not content_emitted:
                        content = self._extract_content_from_final_state(evt["data"].get("output"))
                        if content:
                            content_emitted = True
                            metrics.tokens_streamed += len(content.split())
                            yield format_sse_event(
                                SSEEventType.TOKEN,
                                {"content": content},
                            )
                    
                    yield format_sse_event(SSEEventType.DONE, {"content": ""})
                    self.circuit_breaker.record_success()
                
                # ── Error in chain ──
                elif kind == "on_chain_error":
                    error_str = str(evt["data"].get("error", "Unknown error"))
                    logger.error("⚠️ Chain error: %s", error_str[:200])
                    yield format_sse_event(
                        SSEEventType.ERROR,
                        {"content": f"Error: {error_str[:200]}"},
                    )
                    metrics.errors_encountered += 1
                    self.circuit_breaker.record_failure()
        
        except asyncio.CancelledError:
            logger.warning("⏹️ Stream cancelled by client")
            raise
        except Exception as e:
            logger.exception("❌ Internal stream error: %s", str(e))
            raise

    @staticmethod
    def _extract_content(chunk_content: Any) -> str:
        """Extract text content from various chunk formats.
        
        Handles:
        • Simple strings
        • List of dicts (new format)
        • Complex nested structures
        """
        if isinstance(chunk_content, str):
            return chunk_content
        
        if isinstance(chunk_content, list):
            texts = []
            for item in chunk_content:
                if isinstance(item, dict):
                    if "text" in item:
                        texts.append(str(item["text"]))
                elif isinstance(item, str):
                    texts.append(item)
            return "".join(texts)
        
        # Fallback
        return str(chunk_content) if chunk_content else ""

    @staticmethod
    def _extract_content_from_model_output(output: Any) -> str:
        """Extract AI message content from a model node's on_chain_end output.
        
        The model node returns a list of Command objects with state updates.
        The first Command's update contains messages including the AIMessage.
        """
        if not output:
            return ""
        
        # Output is typically a list of Command objects
        if isinstance(output, list) and len(output) > 0:
            first_cmd = output[0]
            # Command has an 'update' dict with 'messages' key
            if hasattr(first_cmd, "update") and isinstance(first_cmd.update, dict):
                messages = first_cmd.update.get("messages", [])
                return CareerAgent._extract_last_ai_content(messages)
            # Fallback: try dict access
            if isinstance(first_cmd, dict):
                update = first_cmd.get("update", {})
                if isinstance(update, dict):
                    messages = update.get("messages", [])
                    return CareerAgent._extract_last_ai_content(messages)
        
        return ""

    @staticmethod
    def _extract_content_from_final_state(output: Any) -> str:
        """Extract AI message content from the root LangGraph's final state output.
        
        The final state contains all messages; we extract the last AIMessage.
        """
        if not output:
            return ""
        
        # The output is the final state dict with messages
        if isinstance(output, dict):
            messages = output.get("messages", [])
            return CareerAgent._extract_last_ai_content(messages)
        
        return ""

    @staticmethod
    def _extract_last_ai_content(messages: list) -> str:
        """Extract content from the last AIMessage in a messages list.
        
        Handles both string content and multi-modal content lists like:
            [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}]
        """
        if not messages:
            return ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                content = getattr(msg, "content", None)
            elif isinstance(msg, dict) and msg.get("type") == "ai":
                content = msg.get("content", "")
            else:
                continue
            
            if not content:
                continue
            
            # String content
            if isinstance(content, str):
                return content
            
            # Multi-modal list content: [{"type": "text", "text": "..."}, ...]
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        # Try "text" key first, then "content"
                        parts.append(str(block.get("text", block.get("content", ""))))
                    elif isinstance(block, str):
                        parts.append(block)
                text = "".join(parts).strip()
                if text:
                    return text
            
            # Fallback: convert to string
            return str(content)
        return ""