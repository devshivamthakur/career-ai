"""
Chat API – single SSE‑streaming endpoint for the unified CareerAI agent.
Accepts messages + optional file, streams tool calls + tokens via SSE.

Session management:
  - Each chat session is stored as a JSON file in backend/chat_sessions/
  - The last 7 messages + a summary of older messages are sent as context
  - Sessions can be created, read, and deleted
"""

import json
import logging
import os
import re
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

from app.agents.unified_agent import CareerAgent
from app.services.chat_session import (
    create_session,
    get_session,
    save_message,
    get_context_messages,
    delete_session,
    ensure_session,
    has_resume_file,
    save_resume_file,
    get_resume_context,
    save_resume_file_in_storage,
)
from app.utils.helpers import sanitise_user_input


# ── Greeting / casual-chat pre-check ────────────────────────────
# Prevents unnecessary tool calls for simple messages like "hi", "hello", etc.
# The agent is designed for career-related tasks; casual chat bypasses the agent.

_GREETING_RESPONSES: list[str] = [
    "👋 Hi! I'm **CareerAI**, your personal career assistant. I help with resume tailoring, cover letters, interview prep, and career advice. How can I help you today?",
    "Hello! 👋 I'm CareerAI. I can help you tailor your resume, write cover letters, prepare for interviews, or analyse your skills for a specific role. What would you like help with?",
    "Hi there! 👋 I'm CareerAI — ready to help you land your dream job. Just upload your resume (PDF) and share a job description, and I'll handle the rest!",
]

_GREETING_PATTERNS: list[re.Pattern] = [
    re.compile(r'^(hi|hello|hey|sup|yo|howdy|greetings)[\s!.,;:?]*$', re.IGNORECASE),
    re.compile(r'^(good\s+(morning|afternoon|evening))[\s!.,;:?]*$', re.IGNORECASE),
    re.compile(r'^how\s+are\s+you[\s!.,;:?]*$', re.IGNORECASE),
    re.compile(r"^what'?s?\s+up[\s!.,;:?]*$", re.IGNORECASE),
    re.compile(r'^nice\s+to\s+meet\s+you[\s!.,;:?]*$', re.IGNORECASE),
    re.compile(r'^(ok|okay|thanks|thank\s+you|ty|thx)[\s!.,;:?]*$', re.IGNORECASE),
    re.compile(r'^can\s+you\s+help\s+me[\s!.,;:?]*$', re.IGNORECASE),
]

# Career-related keywords — if message contains any of these, DO NOT short-circuit
_CAREER_KEYWORDS: list[str] = [
    "resume", "cv", "curriculum", "cover letter", "job", "career", "interview",
    "application", "role", "position", "skill", "ats", "hire", "recruit",
    "employ", "work", "experience", "project", "portfolio", "linkedin",
    "job description", "jd", "qualification", "salary", "offer", "promotion",
]


def _is_casual_chat(message: str) -> bool:
    """Return True if message is a greeting/simple chat that doesn't need the agent."""
    msg = message.strip().lower()

    # If the message contains career-related keywords, always route to agent
    for kw in _CAREER_KEYWORDS:
        if kw in msg:
            return False

    # Check greeting patterns
    for pattern in _GREETING_PATTERNS:
        if pattern.match(msg):
            return True

    # Very short messages that are clearly just acknowledgments
    if msg in {"ok", "okay", "thanks", "thank you", "ty", "thx", "np", "sure", "yes", "no", "yep", "nope"}:
        return True

    return False


def _pick_greeting_response() -> str:
    """Pick a random greeting response."""
    import random
    return random.choice(_GREETING_RESPONSES)


# ── Resume extraction helpers ────────────────────────────────────
# Three methods are used (in priority order):
#   1. Visible markers:  ---BEGIN RESUME--- / ---END RESUME---
#   2. HTML markers:     <!--RESUME--> / <!--/RESUME-->
#   3. Heuristic:        Auto-detect resume content from structure

# ── Marker patterns ──────────────────────────────────────────

VISIBLE_MARKER_PATTERN = re.compile(
    r'---BEGIN\s*RESUME---\s*(.*?)\s*---END\s*RESUME---',
    re.DOTALL | re.IGNORECASE,
)
HTML_MARKER_PATTERN = re.compile(
    r'<!--RESUME-->(.*?)<!--/RESUME-->',
    re.DOTALL,
)

# ── Resume section heuristics ────────────────────────────────
# Common resume section headings (case-insensitive)
RESUME_SECTION_KEYWORDS = [
    "professional summary",
    "summary of qualifications",
    "summary",
    "profile",
    "career objective",
    "objective",
    "work experience",
    "experience",
    "professional experience",
    "employment history",
    "relevant experience",
    "technical skills",
    "skills",
    "core competencies",
    "education",
    "academic background",
    "projects",
    "key projects",
    "project experience",
    "certifications",
    "licenses",
    "certifications & licenses",
    "publications",
    "patents",
    "awards",
    "honors",
    "leadership",
    "volunteer experience",
    "languages",
    "interests",
    "additional information",
    "technical expertise",
    "tools & technologies",
]

_RESUME_TRIGGER_KEYWORDS = [
    "rewrite", "tailor", "optimize", "ats", "resume", "cv", "curriculum",
    "job description", "jd", "cover letter", "application",
]


def _contains_resume_sections(text: str) -> Optional[list[str]]:
    """Check if text contains common resume section headings.

    Returns list of matched sections if 3+ found, else None.
    """
    text_lower = text.lower()
    found = []
    for kw in RESUME_SECTION_KEYWORDS:
        # Look for keyword as a heading: preceded by ##, **, or at start of line
        pattern = re.compile(
            r'(?:^|\n)(?:#{1,3}\s+|\*{1,2}\s*)?'
            + re.escape(kw)
            + r'\s*(?::|\n)',
            re.IGNORECASE | re.MULTILINE,
        )
        if pattern.search(text_lower) or f"\n{kw}\n" in text_lower or f"**{kw}**" in text_lower:
            found.append(kw)
    return found if len(found) >= 3 else None


def _is_likely_resume_request(message: str) -> bool:
    """Check if user message is asking for resume-related work."""
    msg_lower = message.lower()
    match_count = sum(1 for kw in _RESUME_TRIGGER_KEYWORDS if kw in msg_lower)
    return match_count >= 2


def _extract_resume_block(text: str) -> Optional[str]:
    """Extract the likely resume block from text using heuristics.

    Strategy: find the first and last resume section heading,
    and extract everything between them (inclusive).
    """
    lines = text.split("\n")
    # Build a list of (line_index, keyword) for lines that match resume sections
    section_matches: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        line_lower = line.strip().lower().rstrip(":")
        # Check if line looks like a heading with a resume keyword
        stripped = line.strip()
        heading_text = ""
        if stripped.startswith("##") or stripped.startswith("###"):
            heading_text = stripped.lstrip("#").strip().lower().rstrip(":")
        elif stripped.startswith("**") and stripped.endswith("**"):
            heading_text = stripped.strip("*").strip().lower().rstrip(":")
        elif stripped.isupper() and len(stripped.split()) <= 5:
            heading_text = stripped.lower().rstrip(":")

        if heading_text:
            for kw in RESUME_SECTION_KEYWORDS:
                if heading_text == kw or heading_text.startswith(kw + " ") or heading_text.startswith(kw + ":"):
                    section_matches.append((i, kw))
                    break

    if len(section_matches) < 3:
        return None

    # Extract from first section heading to either the last section's end
    # (or end of content if the last section goes to the end)
    first_idx = section_matches[0][0]
    last_idx = section_matches[-1][0]

    # Look ahead from last section to find where content ends
    # (next empty line after the last section's last content bullet)
    end_idx = len(lines)
    for i in range(last_idx + 1, len(lines)):
        stripped = lines[i].strip()
        # If we encounter a non-resume heading or long gap, stop
        if i > last_idx + 30:  # Safety: don't go beyond 30 lines after last section
            end_idx = i
            break

    extracted = "\n".join(lines[first_idx:end_idx]).strip()
    if len(extracted) < 300:
        return None
    return extracted


def extract_resume_from_content(content: str, user_message: str = "") -> Optional[str]:
    """Extract resume content from assistant response.

    Uses three methods in priority order:
    1. Visible markers:  ---BEGIN RESUME--- / ---END RESUME---
    2. HTML markers:     <!--RESUME--> / <!--/RESUME-->
    3. Heuristics:       Auto-detect if content looks resume-like

    Args:
        content: The full assistant response text.
        user_message: The user's message (for trigger detection).

    Returns:
        Extracted resume text, or None if no resume detected.
    """
    # ── Method 1: Visible markers ──
    match = VISIBLE_MARKER_PATTERN.search(content)
    if match:
        extracted = match.group(1).strip()
        if len(extracted) >= 200:
            logger.info("Resume extracted via visible markers (%d chars)", len(extracted))
            return extracted

    # ── Method 2: HTML comment markers ──
    match = HTML_MARKER_PATTERN.search(content)
    if match:
        extracted = match.group(1).strip()
        if len(extracted) >= 200:
            logger.info("Resume extracted via HTML markers (%d chars)", len(extracted))
            return extracted

    # ── Method 3: Heuristic detection ──
    # Only run heuristics if the user's message seems resume-related
    # OR if we find strong resume signals in the content
    sections = _contains_resume_sections(content)
    is_resume_request = _is_likely_resume_request(user_message) if user_message else False

    if sections and (is_resume_request or len(content) >= 500):
        logger.info("Resume content detected via heuristics (sections: %s)", sections)
        extracted = _extract_resume_block(content)
        if extracted:
            logger.info("Resume block extracted via heuristics (%d chars)", len(extracted))
            return extracted
        # Fallback: return the whole content if it seems resume-like
        if len(content) >= 300 and is_resume_request:
            logger.info("Using full content as resume (%d chars)", len(content))
            return content

    return None


def strip_resume_markers(content: str) -> str:
    """Remove all marker types from content for clean storage/display."""
    cleaned = VISIBLE_MARKER_PATTERN.sub("", content)
    cleaned = HTML_MARKER_PATTERN.sub("", cleaned)
    return cleaned.strip()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Singleton agent ────────────────────────────────────────────

_agent: Optional[CareerAgent] = None


def _get_agent() -> CareerAgent:
    global _agent
    if _agent is None:
        try:
            _agent = CareerAgent()
            logger.info("CareerAgent initialized for chat routes")
        except Exception as e:
            logger.exception("Failed to init CareerAgent")
            raise RuntimeError(f"Agent init failed: {e}") from e
    return _agent


# ── Session Management Endpoints ──────────────────────────────


@router.post("/session")
async def create_chat_session():
    """Create a new chat session. Returns the session ID."""
    session_id = create_session()
    return {"session_id": session_id, "messages": [], "created_at": None}


@router.get("/session/{session_id}")
async def get_chat_session(session_id: str):
    """Get a session's messages and metadata."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session["id"],
        "messages": session.get("messages", []),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@router.delete("/session/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session and all its messages."""
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


# ── SSE Streaming endpoint ─────────────────────────────────────


@router.post("/stream")
async def chat_stream(
    request: Request,
    message: str = Form(..., description="The user's chat message"),
    session_id: str = Form(..., description="Session ID for context persistence"),
    file: Optional[UploadFile] = File(None, description="Optional PDF file (resume)"),
):
    """
    Chat with the CareerAI agent via SSE streaming.

    - `message`: plain text message from the user
    - `session_id`: session identifier for context persistence
    - `file`: optional PDF resume file
    - Receives SSE events: `token`, `tool_start`, `tool_end`, `tool_call`, `done`, `error`
    """
    agent = _get_agent()

    # Ensure session exists (create if not)
    ensure_session(session_id)

    # ── Input sanitisation ────────────────────────────────────
    # Strip known prompt injection / jailbreak patterns from user input
    # BEFORE it enters any prompt template or session storage.
    message = sanitise_user_input(message)

    # ── File upload handling (one per session) ───────────────
    # If a file is uploaded, extract text immediately and store in session.
    # This eliminates redundant tool calls and avoids middleware-limit errors.
    temp_path = None
    if file and file.filename:

        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        try:
            pdf_bytes = await file.read()
            if len(pdf_bytes) > 10 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

            # Extract text immediately so the agent never needs to call extract_resume_text
            from app.services.pdf_service import PDFParsingService
            resume_text = PDFParsingService.extract_text_from_pdf_bytes(pdf_bytes)

            if not resume_text or len(resume_text.strip()) < 50:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "We couldn't extract enough text from your PDF. "
                        "The file may be scanned/image-based (not selectable text). "
                        "Please try a PDF with selectable text, or copy-paste your "
                        "resume content directly into the chat."
                    ),
                )

            #save the pdf in storage folder to use in future if needed
            temp_path = save_resume_file_in_storage(pdf_bytes)
            # # Save to session — this marks the session as having a resume
            # save_resume_file(session_id, file.filename, resume_text)

            # Warm the in-memory tool cache so even if the agent calls the tool,
            # it returns instantly without hitting middleware limits.
            from app.agents.tools import _warm_tool_cache
            _warm_tool_cache("extract_resume_text", resume_text)

            final_message = (
                f"[Resume file uploaded: {temp_path}]\n"
                f"[Resume text extracted successfully ({len(resume_text)} chars). "
                f"The text is already provided in the context below — "
                f"you do NOT need to call extract_resume_text.]\n\n"
                f"═══════════════ RESUME TEXT ════════════════\n"
                f"{resume_text}\n"
                f"═════════════ END RESUME TEXT ══════════════\n\n"
                f"═══════════════ USER MESSAGE ═══════════════\n"
                f"{message}\n"
                f"═════════════ END USER MESSAGE ═════════════"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("File upload / extraction error")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process resume PDF: {str(e)[:200]}",
            )
    else:
            #update the final message to include the user message only if no file is uploaded
            #ask for agent check for history if the session has a resume file, if yes then include the resume context in the final message
            final_message = (
            f"═══════════════ USER MESSAGE ═══════════════\n"
            f"{message}\n"
            f"═════════════ END USER MESSAGE ═════════════"
            )

    # Save the original user message (without system instruction prefix) to session
    # so chat history stays clean when reloaded on page refresh.

    # Build context messages for the LLM (summary + last N + new message)
    # Use final_message here so the LLM receives the system instructions.
    context_messages = get_context_messages(session_id, final_message, temp_path if file else None)
    save_message(session_id, "user", message, filename=temp_path if file else None)

    async def event_stream():
        full_assistant_content = ""
        # Store user's original message for trigger detection
        user_original_message = message
        try:
            # ── Greeting / casual-chat pre-check ──
            # Short-circuit the agent entirely to avoid unnecessary tool calls
            if not file and _is_casual_chat(message) and len(context_messages) == 1:
                greeting = _pick_greeting_response()
                # Emit greeting as a single token event, then done
                yield f"event: token\ndata: {json.dumps({'content': greeting})}\n\n"
                yield f"event: done\ndata: {json.dumps({'content': ''})}\n\n"
                return
            
            # Convert context dicts to LangChain message objects
            lc_messages: list[BaseMessage] = []
            for ctx_msg in context_messages:
                if ctx_msg["role"] == "user":
                    # Use multi-part content blocks — accepts plain text only (no custom dict keys).
                    # When a file is associated, append it as a second text block.
                    parts = [{"type": "text", "text": ctx_msg["content"]}]
                    if ctx_msg.get("resumefile"):
                        parts.append({
                            "type": "text",
                            "text": f"[resume file: {ctx_msg['resumefile']}]"
                        })
                    lc_messages.append(HumanMessage(content=parts))
                elif ctx_msg["role"] == "assistant":
                    lc_messages.append(AIMessage(content=ctx_msg["content"]))
                elif ctx_msg["role"] == "system":
                    lc_messages.append(SystemMessage(content=ctx_msg["content"]))
            print("LC MESSAGES:", lc_messages)        
            async for sse_line in agent.stream_sse(lc_messages, thread_id=session_id):
                if await request.is_disconnected():
                    logger.warning("Client disconnected")
                    break
                yield sse_line

                # Accumulate assistant content for persistence
                if sse_line.startswith("event: token\n"):
                    try:
                        data_line = sse_line.split("data: ")[1].strip()
                        parsed = json.loads(data_line)
                        full_assistant_content += parsed.get("content", "")
                    except (IndexError, json.JSONDecodeError):
                        pass

            # ── After the agent stream completes, check for resume content ──
            logger.debug("Agent stream finished. Full content length: %d", len(full_assistant_content))
            # For debugging, log the full raw output from the agent
            # In production, you might want to limit this or use a higher log level
            if len(full_assistant_content) > 0:
                logger.debug("ASSISTANT RAW OUTPUT:\n---\n%s\n---", full_assistant_content)

            resume_content = extract_resume_from_content(
                full_assistant_content,
                user_message=user_original_message,
            )
            if resume_content:
                logger.info(
                    "Resume content DETECTED, emitting resume_ready event (%d chars)",
                    len(resume_content),
                )
                yield (
                    "event: resume_ready\n"
                    f"data: {json.dumps({'content': resume_content})}\n\n"
                )
            else:
                logger.warning(
                    "Resume content NOT DETECTED in assistant response. No download will be offered."
                )

        except Exception as e:
            logger.exception("Stream error")
            yield f"event: error\ndata: {json.dumps({'content': f'Stream error: {str(e)}'})}\n\n"
        finally:
            # Save assistant response to session (with markers stripped)
            clean_content = strip_resume_markers(full_assistant_content) if full_assistant_content.strip() else ""
            if clean_content:
                save_message(session_id, "assistant", clean_content)
            

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status")
async def chat_status():
    """Health check for the chat agent."""
    try:
        agent = _get_agent()
        return {"status": "operational", "tools": [t.name for t in agent.agent.tools]}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
