"""
Chat Service — business logic for the unified CareerAI chat agent.

Extracted from the legacy ``chat_routes.py`` so the HTTP layer stays thin.
Responsibilities:
  - Greeting / casual-chat detection (short-circuit path)
  - Resume content extraction (markers + structural heuristics)
  - User prompt building (file + resume context blocks)
  - LangChain message conversion
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.utils.constants import RESUME_SECTION_KEYWORDS, RESUME_TRIGGER_KEYWORDS

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
# Casual-chat detection
# ═══════════════════════════════════════════════════════════════════

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

# Career-related keywords — if a message contains any, route to the agent
_CAREER_KEYWORDS: list[str] = [
    "resume", "cv", "curriculum", "cover letter", "job", "career", "interview",
    "application", "role", "position", "skill", "ats", "hire", "recruit",
    "employ", "work", "experience", "project", "portfolio", "linkedin",
    "job description", "jd", "qualification", "salary", "offer", "promotion",
]

_ACKNOWLEDGMENTS = {
    "ok", "okay", "thanks", "thank you", "ty", "thx", "np", "sure", "yes", "no", "yep", "nope",
}


def is_casual_chat(message: str) -> bool:
    """Return True if the message is a greeting/simple chat that doesn't need the agent."""
    msg = message.strip().lower()

    for kw in _CAREER_KEYWORDS:
        if kw in msg:
            return False

    for pattern in _GREETING_PATTERNS:
        if pattern.match(msg):
            return True

    return msg in _ACKNOWLEDGMENTS


def pick_greeting_response() -> str:
    """Pick a random greeting response."""
    return random.choice(_GREETING_RESPONSES)


# ═══════════════════════════════════════════════════════════════════
# Resume content extraction
# ═══════════════════════════════════════════════════════════════════
# Priority order:
#   1. Visible markers  ---BEGIN RESUME--- / ---END RESUME---
#   2. HTML markers     <!--RESUME--> / <!--/RESUME-->
#   3. Heuristics       structural resume-section detection

VISIBLE_MARKER_PATTERN = re.compile(
    r'---BEGIN\s*RESUME---\s*(.*?)\s*---END\s*RESUME---',
    re.DOTALL | re.IGNORECASE,
)
HTML_MARKER_PATTERN = re.compile(
    r'<!--RESUME-->(.*?)<!--/RESUME-->',
    re.DOTALL,
)

HTML_BEGIN_MARKER_RE = re.compile(r"^<!--\s*RESUME\s*-->$", re.IGNORECASE)
HTML_END_MARKER_RE = re.compile(r"^<!--\s*/\s*RESUME\s*-->$", re.IGNORECASE)


def _marker_keyword(line: str) -> str:
    """Collapse a marker line to its alphanumeric uppercase core.

    ``---BEGIN RESUME---``, ``**BEGIN RESUME**`` and ``### BEGIN RESUME ###``
    all collapse to ``BEGINRESUME``.
    """
    return re.sub(r"[^A-Z0-9]", "", line.strip().upper())


def normalize_resume_markers(text: str) -> str:
    """Rewrite any style of BEGIN/END RESUME marker line to the canonical
    ``---BEGIN RESUME---`` / ``---END RESUME---`` form.

    LLMs occasionally decorate the markers (bold ``**BEGIN RESUME**``, heading
    hashes, ``<!-- RESUME -->``, etc.). Canonicalizing first lets the existing
    extraction/stripping patterns work regardless of the decoration style.
    """
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        keyword = _marker_keyword(stripped)
        if keyword == "BEGINRESUME" or HTML_BEGIN_MARKER_RE.match(stripped):
            lines.append("---BEGIN RESUME---")
        elif keyword == "ENDRESUME" or HTML_END_MARKER_RE.match(stripped):
            lines.append("---END RESUME---")
        else:
            lines.append(line)
    return "\n".join(lines)


def _contains_resume_sections(text: str) -> Optional[list[str]]:
    """Return matched resume section headings if 3+ are found, else None."""
    text_lower = text.lower()
    found: list[str] = []
    for kw in RESUME_SECTION_KEYWORDS:
        pattern = re.compile(
            r'(?:^|\n)(?:#{1,3}\s+|\*{1,2}\s*)?'
            + re.escape(kw)
            + r'\s*(?::|\n)',
            re.IGNORECASE | re.MULTILINE,
        )
        if (
            pattern.search(text_lower)
            or f"\n{kw}\n" in text_lower
            or f"**{kw}**" in text_lower
        ):
            found.append(kw)
    return found if len(found) >= 3 else None


def _is_likely_resume_request(message: str) -> bool:
    """Return True if the user message asks for resume-related work."""
    msg_lower = message.lower()
    return sum(1 for kw in RESUME_TRIGGER_KEYWORDS if kw in msg_lower) >= 2


def _extract_resume_block(text: str) -> Optional[str]:
    """Extract the block between the first and last resume section headings."""
    lines = text.split("\n")
    section_matches: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
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
                if (
                    heading_text == kw
                    or heading_text.startswith(kw + " ")
                    or heading_text.startswith(kw + ":")
                ):
                    section_matches.append((i, kw))
                    break

    if len(section_matches) < 3:
        return None

    first_idx = section_matches[0][0]
    last_idx = section_matches[-1][0]

    end_idx = len(lines)
    for i in range(last_idx + 1, len(lines)):
        if i > last_idx + 30:  # safety: cap at 30 lines past the last section
            end_idx = i
            break

    extracted = "\n".join(lines[first_idx:end_idx]).strip()
    return extracted if len(extracted) >= 300 else None


def extract_resume_from_content(
    content: str,
    user_message: str = "",
) -> Optional[str]:
    """Extract the likely resume block from an assistant response.

    Uses visible markers, then HTML markers, then structural heuristics.
    Returns ``None`` when no resume content is detected.
    """
    content = normalize_resume_markers(content)
    match = VISIBLE_MARKER_PATTERN.search(content)
    if match:
        extracted = match.group(1).strip()
        if len(extracted) >= 200:
            logger.info("Resume extracted via visible markers (%d chars)", len(extracted))
            return extracted

    match = HTML_MARKER_PATTERN.search(content)
    if match:
        extracted = match.group(1).strip()
        if len(extracted) >= 200:
            logger.info("Resume extracted via HTML markers (%d chars)", len(extracted))
            return extracted

    sections = _contains_resume_sections(content)
    is_resume_request = _is_likely_resume_request(user_message) if user_message else False

    if sections and (is_resume_request or len(content) >= 500):
        logger.info("Resume content detected via heuristics (sections: %s)", sections)
        extracted = _extract_resume_block(content)
        if extracted:
            logger.info("Resume block extracted via heuristics (%d chars)", len(extracted))
            return extracted
        if len(content) >= 300 and is_resume_request:
            logger.info("Using full content as resume (%d chars)", len(content))
            return content

    return None


def strip_resume_markers(content: str) -> str:
    """Remove all marker types from content for clean storage/display."""
    content = normalize_resume_markers(content)
    cleaned = VISIBLE_MARKER_PATTERN.sub("", content)
    cleaned = HTML_MARKER_PATTERN.sub("", cleaned)
    return cleaned.strip()


# ═══════════════════════════════════════════════════════════════════
# Prompt building & message conversion
# ═══════════════════════════════════════════════════════════════════

def build_user_prompt(message: str, resume_text: Optional[str] = None) -> str:
    """Wrap a raw user message in the delimiter-based context block."""
    if resume_text:
        return (
            f"[Resume file uploaded]\n"
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
    return (
        f"═══════════════ USER MESSAGE ═══════════════\n"
        f"{message}\n"
        f"═════════════ END USER MESSAGE ═════════════"
    )


def to_langchain_messages(context_messages: list[dict]) -> list[BaseMessage]:
    """Convert stored context dicts into LangChain message objects.

    User messages with an associated resume file get a second text block
    referencing the file path.
    """
    lc_messages: list[BaseMessage] = []
    for ctx_msg in context_messages:
        role = ctx_msg["role"]
        content = ctx_msg["content"]

        if role == "user":
            parts: list[dict] = [{"type": "text", "text": content}]
            if ctx_msg.get("resumefile"):
                parts.append({"type": "text", "text": f"[resume file: {ctx_msg['resumefile']}]"})
            lc_messages.append(HumanMessage(content=parts))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        elif role == "system":
            lc_messages.append(SystemMessage(content=content))

    return lc_messages


def serialize_sse_data(data: dict) -> str:
    """Serialize a dict for an SSE ``data:`` line."""
    return json.dumps(data, ensure_ascii=False)
