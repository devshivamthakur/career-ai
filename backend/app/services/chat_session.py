"""
JSON file-based chat session store.

Structures:
  sessions/<session_id>.json
    {
      "id": "session_xxx",
      "created_at": "ISO timestamp",
      "updated_at": "ISO timestamp",
      "messages": [
        {"role": "user"|"assistant", "content": "...", "timestamp": "ISO"}
      ],
      "summary": "AI-generated summary of older messages (for context window)"
    }

When a session has more than 7 messages, the oldest messages get rolled up
into a summary and only the last 7 messages + summary are sent to the LLM.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────
SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_sessions")
MAX_CONTEXT_MESSAGES = 7  # last N messages to keep in full


def _ensure_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")


# ── CRUD ──────────────────────────────────────────────────


def create_session() -> str:
    """Create a new session with a generated ID and return it."""
    return create_session_with_id(f"session_{uuid.uuid4().hex[:12]}")


def create_session_with_id(session_id: str) -> str:
    """Create a new session with the given ID. Returns the ID."""
    _ensure_dir()
    data = {
        "id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": [],
        "summary": "",
    }
    with open(_session_path(session_id), "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Created session %s", session_id)
    return session_id


def ensure_session(session_id: str) -> dict:
    """Get or create a session. Returns the session data."""
    session = get_session(session_id)
    if session is None:
        create_session_with_id(session_id)
        session = get_session(session_id)
    return session


def get_session(session_id: str) -> Optional[dict]:
    """Load a session by ID. Returns None if not found."""
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_message(session_id: str, role: str, content: str):
    """Append a message to the session."""
    session = get_session(session_id)
    if session is None:
        logger.warning("Session %s not found, creating new", session_id)
        session = {
            "id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
            "summary": "",
        }

    session["messages"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    session["updated_at"] = datetime.now(timezone.utc).isoformat()

    # If we exceed MAX_CONTEXT_MESSAGES + some buffer, roll up the oldest
    if len(session["messages"]) > MAX_CONTEXT_MESSAGES + 3:
        _rollup_summary(session)

    _persist(session)


def _persist(session: dict):
    _ensure_dir()
    with open(_session_path(session["id"]), "w") as f:
        json.dump(session, f, indent=2)


def _rollup_summary(session: dict):
    """Summarize messages that fall outside the context window."""
    messages = session["messages"]
    # Keep the last MAX_CONTEXT_MESSAGES
    to_summarize = messages[:-MAX_CONTEXT_MESSAGES]
    session["messages"] = messages[-MAX_CONTEXT_MESSAGES:]

    # Build a concise summary from the older messages
    old_text = "\n".join(
        f"{m['role']}: {m['content'][:500]}" for m in to_summarize
    )
    # Simple truncation-based summarisation (replaced by AI summarization later)
    if len(old_text) > 2000:
        old_text = old_text[:2000] + "..."

    previous_summary = session.get("summary", "")
    if previous_summary:
        session["summary"] = f"{previous_summary}\n---\n{old_text}"
    else:
        session["summary"] = old_text

    logger.info(
        "Rolled up %d messages for session %s. Summary length: %d",
        len(to_summarize),
        session["id"],
        len(session["summary"]),
    )


def get_context_messages(session_id: str, new_message: str) -> list[dict]:
    """
    Build the message list for the LLM:
      - Summary of older conversation (if any)
      - Last MAX_CONTEXT_MESSAGES messages
      - The new user message
    Returns a list of dicts with 'role' and 'content'.
    """
    session = get_session(session_id)
    if session is None:
        return [{"role": "user", "content": new_message}]

    context = []

    # 1. Summary of older conversation — sent as 'user' role (not 'system') to
    #    avoid treating potentially injection-containing summaries as authoritative
    #    system instructions.
    if session.get("summary"):
        context.append({
            "role": "user",
            "content": f"[Previous conversation summary]:\n{session['summary']}",
        })

    # 2. Last N messages (most recent first preserved order)
    for msg in session["messages"]:
        context.append({"role": msg["role"], "content": msg["content"]})

    # 3. The new user message
    context.append({"role": "user", "content": new_message})

    return context


def delete_session(session_id: str) -> bool:
    """Delete a session file. Returns True if deleted."""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)
        logger.info("Deleted session %s", session_id)
        return True
    return False
