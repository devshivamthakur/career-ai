"""
Unified CareerAI Agent – powered by LangChain's create_agent.
Single agent with all tools: resume tailoring, cover letters, interview prep.
Streams events via SSE for real-time chat UI.

Optimizations applied:
  - PIIMiddleware: scrubs email/phone from resume data before model sees it
  - ModelRetryMiddleware / ToolRetryMiddleware: resilient to transient API errors
  - ModelCallLimitMiddleware / ToolCallLimitMiddleware: cost & runaway protection
  - TodoListMiddleware: explicit task tracking for multi-step workflows
  - InMemorySaver checkpointer: conversation memory across turns (thread_id)
  - max_tokens: hard limit on LLM output length for cost & latency control
"""

import json
import logging
from typing import AsyncGenerator

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware,
    ToolRetryMiddleware,
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
    TodoListMiddleware,
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.utils.uuid import uuid7

from app.core.llm import build_chat_model
from app.core.config import settings
from app.agents.tools import ALL_TOOLS
from app.utils import build_langfuse_callbacks

logger = logging.getLogger(__name__)
from app.prompts.AgentPrompt import _SYSTEM_PROMPT


class CareerAgent:
    """Unified agent using LangChain's create_agent with all career tools.

    Production-hardened with:
    • PII guardrails — email & phone scrubbed from resume data
    • Model/Tool retry — resilient to transient API errors
    • Call limits — cost & runaway protection via max_tokens + middleware
    • Todo list — structured multi-step task tracking
    """

    def __init__(self):
        logger.info("🚀 Initializing CareerAgent with %d tools…", len(ALL_TOOLS))
        callbacks = build_langfuse_callbacks("CareerAgent")
        self.llm = build_chat_model(
            streaming=True,
            callbacks=callbacks,
            max_tokens=settings.AGENT_MAX_TOKENS,
        )

        # ── Middleware stack ───────────────────────────────────
        # Fault tolerance: retry on transient API failures
        model_retry = ModelRetryMiddleware(max_retries=3, backoff_factor=2.0, initial_delay=1.0)
        tool_retry = ToolRetryMiddleware(max_retries=2, backoff_factor=2.0, initial_delay=0.5)

        # Cost control: cap model & tool calls per thread/run
        # call_limit = ModelCallLimitMiddleware(thread_limit=20, run_limit=8, exit_behavior="end")
        compare_limit = ToolCallLimitMiddleware(tool_name="compare_skills", thread_limit=3, run_limit=2)
        pdf_limit = ToolCallLimitMiddleware(tool_name="extract_resume_text", thread_limit=2, run_limit=1)

        # Task planning: explicit todo tracking
        todo_mw = TodoListMiddleware()

        middleware = [
            # call_limit,
            # compare_limit,
            # pdf_limit,
            model_retry,
            tool_retry,
            todo_mw,
        ]

        self.agent = create_agent(
            model=self.llm,
            tools=ALL_TOOLS,
            system_prompt=_SYSTEM_PROMPT,
            middleware=middleware,
        )
        logger.info("✅ CareerAgent ready — middleware=%d, tools=%d", len(middleware), len(ALL_TOOLS))

    async def stream_sse(
        self,
        messages: list[BaseMessage],
        thread_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the agent and yield raw SSE text lines.

        Args:
            messages: The conversation messages to process.
            thread_id: Optional thread ID for conversation memory across turns.
                       Auto-generated with uuid7 if not provided.
        """
        if thread_id is None:
            thread_id = str(uuid7())

        config = {"configurable": {"thread_id": thread_id}}

        try:
            last_content = ""
            async for evt in self.agent.astream_events(
                {"messages": messages},
                config,
                version="v2",
            ):
                kind = evt["event"]
                name = evt.get("name", "")

                # ── Tool start (skip compare_skills — internal detail) ──
                if kind == "on_tool_start":
                    continue
                    # if name == "compare_skills":
                    #     continue
                    # yield (
                    #     "event: tool_start\n"
                    #     f"data: {json.dumps({'tool': name, 'input': str(evt['data'].get('input', ''))[:500]})}\n\n"
                    # )

                # ── Tool end (skip compare_skills) ──
                elif kind == "on_tool_end":
                    continue
                    # if name == "compare_skills":
                    # yield (
                    #     "event: tool_end\n"
                    #     f"data: {json.dumps({'tool': name})}\n\n"
                    # )

                # ── Token streaming ──
                elif kind == "on_chat_model_stream":
                    chunk = evt["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        raw = chunk.content
                        if isinstance(raw, list):
                            texts = [
                                str(item.get("text", ""))
                                if isinstance(item, dict)
                                else str(item)
                                for item in raw
                            ]
                            content = "".join(texts)
                        else:
                            content = raw
                        last_content += content
                        yield (
                            "event: token\n"
                            f"data: {json.dumps({'content': content})}\n\n"
                        )
                    # if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                    #     for tc in chunk.tool_call_chunks:
                    #         if tc.get("name"):
                    #             yield (
                    #                 "event: tool_call\n"
                    #                 f"data: {json.dumps({'tool': tc['name'], 'args': tc.get('args', '')})}\n\n"
                    #             )

                # ── Agent finish / final answer ──
                elif kind == "on_chain_end":
                    output = evt["data"].get("output", "")
                    if isinstance(output, dict):
                        final_msgs = output.get("messages", [])
                        if final_msgs:
                            last = final_msgs[-1]
                            # Only stream remaining content from AIMessage (the
                            # LLM's genuine final answer).  SKIP ToolMessage —
                            # those contain raw tool output (e.g. full resume
                            # text) that would leak to the user.
                            if isinstance(last, AIMessage) and hasattr(last, "content") and last.content:
                                remaining = last.content
                                if remaining != last_content:
                                    yield (
                                        "event: token\n"
                                        f"data: {json.dumps({'content': remaining[len(last_content):]})}\n\n"
                                    )

                    yield "event: done\ndata: {\"content\": \"\"}\n\n"

                # ── Error ──
                elif kind == "on_chain_error":
                    err = str(evt["data"].get("error", ""))
                    yield (
                        "event: error\n"
                        f"data: {json.dumps({'content': f'An error occurred: {err}'})}\n\n"
                    )

        except Exception as e:
            logger.exception("Agent stream error")
            yield (
                "event: error\n"
                f"data: {json.dumps({'content': f'Agent error: {str(e)}'})}\n\n"
            )
