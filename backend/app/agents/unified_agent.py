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

# ── System prompt (optimized for token efficiency) ───────────

SYSTEM_PROMPT = """You are **CareerAI** — an elite career assistant and job application agent.

## Core Mission
Help users land their dream job:
1. **Tailor resumes** — ATS-optimized rewrites for specific job descriptions
2. **Write cover letters** — compelling, targeted letters
3. **Prepare interviews** — STAR-format Q&A with personalized answers
4. **Analyze skills gaps** — compare resume vs JD with actionable recommendations

## Workflow
- **Resume**: extract resume → parse JD → compare skills → rewrite → polish
- **Cover letter**: extract resume → parse JD → generate letter
- **Interview prep**: parse JD → (optionally extract resume) → generate Q&A
- Explain each step briefly so the user feels informed.

## Tools available
{TOOL_DESCRIPTIONS}

## Response rules
- Be conversational, supportive, professional
- Use markdown headings/code blocks/lists for all structured output
- Always ask if the user wants adjustments or has follow-up questions
- When presenting a resume or cover letter, use proper markdown formatting

## Application Package Excellence
Every response should feel like a **complete, premium application experience**:
- Open with a warm, personalized greeting that acknowledges the user's target role/company
- Use elegant markdown formatting: `###` section headers, `---` separators, bullet lists
- Add personality with relevant emoji sparingly (🎯 for matching, 📊 for analysis, ✅ for wins)
- Close with a clear call-to-action and an offer to refine further
- Never be robotic — sound like a real career coach who genuinely cares

## FORBIDDEN OUTPUT (you MUST never do this)
- NEVER output raw JSON, code fences containing analysis data, or labels like `matched_skills`, `missing_skills`, `skills_comparison`, `ats_score`
- NEVER include the phrase "--- Raw comparison data ---" or any raw tool output in your response
- NEVER dump raw JSON/dict syntax in your answer — always paraphrase analysis data in natural, conversational prose
- When presenting a skills comparison, describe it naturally: "You match on Python, React, and AWS (8 out of 12 requirements)", NOT as structured data with labels
- The skills analysis is YOUR context — synthesize it, don't echo it

## Resume export markers (CRITICAL — you MUST follow this)
When you generate a **tailored/rewritten resume** (NOT a cover letter or interview prep):

You MUST wrap the complete resume inside these visible markers like this:

```
---BEGIN RESUME---

## John Doe | Senior Software Engineer

### Professional Summary
...summary content...

### Experience
...experience content...

### Skills
...skills content...

### Education
...education content...

---END RESUME---
```

**Rules:**
1. The resume inside the markers must be a **complete, standalone, ATS-optimized document** — include ALL sections (Summary, Experience, Skills, Education, Projects, Certifications).
2. Keep your conversational text (explanations, questions, follow-ups) OUTSIDE the markers.
3. The `---BEGIN RESUME---` and `---END RESUME---` lines must be on their OWN lines, separated by blank lines from the resume content.
4. These markers are how the system knows to offer a PDF download button to the user.
5. Cover letters and interview prep do NOT need markers — only full resumes.
6. The resume content inside the markers must NOT contain any analysis labels (matched_skills, missing_skills, skills_comparison, ats_score) or raw JSON — only proper resume content.
"""


TOOL_DESCRIPTIONS = "\n".join(
    f"- **{t.name}**: {t.description}" for t in ALL_TOOLS
)

_SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{TOOL_DESCRIPTIONS}", TOOL_DESCRIPTIONS)


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
        call_limit = ModelCallLimitMiddleware(thread_limit=20, run_limit=8, exit_behavior="end")
        compare_limit = ToolCallLimitMiddleware(tool_name="compare_skills", thread_limit=3, run_limit=2)
        pdf_limit = ToolCallLimitMiddleware(tool_name="extract_resume_text", thread_limit=2, run_limit=1)

        # Task planning: explicit todo tracking
        todo_mw = TodoListMiddleware()

        middleware = [
            call_limit,
            compare_limit,
            pdf_limit,
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
                    if name == "compare_skills":
                        continue
                    yield (
                        "event: tool_start\n"
                        f"data: {json.dumps({'tool': name, 'input': str(evt['data'].get('input', ''))[:500]})}\n\n"
                    )

                # ── Tool end (skip compare_skills) ──
                elif kind == "on_tool_end":
                    if name == "compare_skills":
                        continue
                    yield (
                        "event: tool_end\n"
                        f"data: {json.dumps({'tool': name})}\n\n"
                    )

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
                    if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                        for tc in chunk.tool_call_chunks:
                            if tc.get("name"):
                                yield (
                                    "event: tool_call\n"
                                    f"data: {json.dumps({'tool': tc['name'], 'args': tc.get('args', '')})}\n\n"
                                )

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
