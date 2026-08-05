"""
Chat API v1 — thin HTTP layer.

Handles HTTP/Session concerns only; all business logic lives in
``app.services.chat_service`` (detection, extraction, prompt building)
and ``app.services.chat_session`` (session store).
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.tools import _warm_tool_cache
from app.agents.unified_agent import CareerAgent
from app.api.v1.deps import get_career_agent
from app.services.chat_service import (
    build_user_prompt,
    extract_resume_from_content,
    is_casual_chat,
    pick_greeting_response,
    strip_resume_markers,
    to_langchain_messages,
)
from app.services.chat_session import (
    create_session,
    delete_session,
    ensure_session,
    get_context_messages,
    get_resume_context,
    get_session,
    save_message,
    save_resume_file,
    save_resume_file_in_storage,
)
from app.services.pdf_service import PDFExtractionError, PDFPageLimitExceeded, PDFParsingService
from app.utils.constants import MAX_CHAT_MESSAGE_LENGTH
from app.utils.helpers import sanitise_user_input

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ═══════════════════════════════════════════════════════════════════
# Session management
# ═══════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════
# SSE streaming
# ═══════════════════════════════════════════════════════════════════


@router.post("/stream")
async def chat_stream(
    request: Request,
    message: str = Form(
        ...,
        min_length=1,
        max_length=MAX_CHAT_MESSAGE_LENGTH,
        description="The user's chat message",
    ),
    session_id: str = Form(..., description="Session ID for context persistence"),
    file: Optional[UploadFile] = File(None, description="Optional PDF file (resume)"),
    agent: CareerAgent = Depends(get_career_agent),
):
    """
    Chat with the CareerAI agent via SSE streaming.

    - `message`: plain text message from the user
    - `session_id`: session identifier for context persistence
    - `file`: optional PDF resume file
    - Receives SSE events: `token`, `tool_start`, `tool_end`, `tool_call`, `done`, `error`
    """
    ensure_session(session_id)

    # ── Input sanitisation (secondary injection defence) ──────────
    message = sanitise_user_input(message)

    # ── File upload handling (one per session) ────────────────────
    temp_path = None
    resume_text = None
    if file and file.filename:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")

        try:
            pdf_bytes = await file.read()
            if len(pdf_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

            try:
                resume_text = PDFParsingService.extract_text_from_pdf_bytes(pdf_bytes)
            except PDFPageLimitExceeded as exc:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Your resume PDF has too many pages (max allowed: 2). "
                        "Please upload a shorter resume (up to 2 pages) and try again."
                    ),
                ) from exc
            except PDFExtractionError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "We couldn't read your PDF. The file may be encrypted, "
                        "corrupted, or scanned/image-based (no selectable text). "
                        "Please try another PDF or copy-paste your resume content "
                        "directly into the chat."
                    ),
                ) from exc

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

            temp_path = save_resume_file_in_storage(pdf_bytes)
            # Persist the extracted text on the session so later turns (without
            # a file attachment) still get the resume content in context.
            save_resume_file(session_id, file.filename, resume_text)
            # Warm the in-memory tool cache so extract_resume_text returns instantly
            _warm_tool_cache("extract_resume_text", resume_text)

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("File upload / extraction error")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process resume PDF: {str(exc)[:200]}",
            )

    # ── Build context & persist the user message ──────────────────
    # If this turn carries a fresh upload use its text; otherwise re-inject the
    # resume stored on the session (from the earlier upload) so the LLM always
    # has the resume content in context and never needs to re-extract.
    resume_ctx = resume_text if resume_text else get_resume_context(session_id)
    final_message = build_user_prompt(message, resume_ctx)
    context_messages = get_context_messages(
        session_id, final_message, temp_path if file else None
    )
    save_message(session_id, "user", message, filename=temp_path if file else None)

    async def event_stream():
        # Accumulate token chunks in a list then join once — avoids O(n²)
        # string concatenation for long streams.
        content_parts: list[str] = []
        user_original_message = message
        try:
            # Greeting short-circuit: casual chats skip the agent entirely
            if not file and is_casual_chat(message) and len(context_messages) == 1:
                yield f"event: token\ndata: {json.dumps({'content': pick_greeting_response()})}\n\n"
                yield f"event: done\ndata: {json.dumps({'content': ''})}\n\n"
                return

            lc_messages = to_langchain_messages(context_messages)
            async for sse_line in agent.stream_sse(lc_messages, thread_id=session_id):
                if await request.is_disconnected():
                    logger.warning("Client disconnected")
                    break
                yield sse_line

                if sse_line.startswith("event: token\n"):
                    try:
                        data_line = sse_line.split("data: ")[1].strip()
                        parsed = json.loads(data_line)
                        token_text = parsed.get("content", "")
                        if token_text:
                            content_parts.append(token_text)
                    except (IndexError, json.JSONDecodeError):
                        pass

            full_assistant_content = "".join(content_parts)

            # After the stream: extract and emit the resume download payload
            if len(full_assistant_content) > 0:
                logger.debug("ASSISTANT RAW OUTPUT:\n---\n%s\n---", full_assistant_content)

            resume_content = extract_resume_from_content(
                full_assistant_content, user_message=user_original_message
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

        except Exception as exc:
            logger.exception("Stream error")
            yield f"event: error\ndata: {json.dumps({'content': f'Stream error: {str(exc)}'})}\n\n"
        finally:
            # Persist the assistant response with markers stripped
            clean_content = (
                strip_resume_markers(full_assistant_content)
                if full_assistant_content.strip()
                else ""
            )
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
async def chat_status(agent: CareerAgent = Depends(get_career_agent)):
    """Health check for the chat agent."""
    try:
        return {"status": "operational", "tools": [t.name for t in agent.agent.tools]}
    except Exception as exc:
        logger.warning("Chat status: agent tools unavailable: %s", exc)
        return {"status": "unavailable", "error": str(exc)}
