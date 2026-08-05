"""
Markdown prompt loader.

Reads .md files from this directory and exposes prompt strings as module-level
constants. Each .md file may contain one or more prompts separated by `---`
horizontal rules. Single-prompt files export a single constant; multi-prompt
files export multiple constants derived from the markdown headings.
"""

from __future__ import annotations

import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load_md(filename: str) -> str:
    """Read a .md file from the prompts directory."""
    path = _PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _split_prompts(text: str) -> list[str]:
    """Split markdown content by `---` horizontal rules into individual prompts."""
    parts = re.split(r"\n---\n", text)
    return [p.strip() for p in parts if p.strip()]


def _extract_heading(text: str) -> str | None:
    """Extract the first markdown heading from a prompt block."""
    match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# AgentPrompt.md — single prompt
# ---------------------------------------------------------------------------
_AGENT_PROMPT_MD = _load_md("AgentPrompt.md")
_SYSTEM_PROMPT = _AGENT_PROMPT_MD

# ---------------------------------------------------------------------------
# jd_parsing_prompts.md — single prompt
# ---------------------------------------------------------------------------
_PARSE_JD_PROMPT = _load_md("jd_parsing_prompts.md")

# ---------------------------------------------------------------------------
# skills_prompts.md — multiple prompts (first part is file header, skip it)
# ---------------------------------------------------------------------------
_SKILLS_PROMPTS = _split_prompts(_load_md("skills_prompts.md"))
# Skip the file header (index 0), prompts start at index 1
_EXTRACT_SKILLS_PROMPT = _SKILLS_PROMPTS[1] if len(_SKILLS_PROMPTS) > 1 else ""
_COMPARE_SKILLS_PROMPT = _SKILLS_PROMPTS[2] if len(_SKILLS_PROMPTS) > 2 else ""
_EXTRACT_PROJECTS_PROMPT = _SKILLS_PROMPTS[3] if len(_SKILLS_PROMPTS) > 3 else ""

# ---------------------------------------------------------------------------
# resume_prompts.md — multiple prompts (first part is file header, skip it)
# ---------------------------------------------------------------------------
_RESUME_PROMPTS = _split_prompts(_load_md("resume_prompts.md"))
# Skip the file header (index 0), prompts start at index 1
_REWRITE_RESUME_PROMPT = _RESUME_PROMPTS[1] if len(_RESUME_PROMPTS) > 1 else ""
_POLISH_RESUME_PROMPT = _RESUME_PROMPTS[2] if len(_RESUME_PROMPTS) > 2 else ""

# ---------------------------------------------------------------------------
# cover_letter_prompts.md — single prompt
# ---------------------------------------------------------------------------
_COVER_LETTER_PROMPT = _load_md("cover_letter_prompts.md")

# ---------------------------------------------------------------------------
# interview_prompts.md — single prompt
# ---------------------------------------------------------------------------
_INTERVIEW_PREP_PROMPT = _load_md("interview_prompts.md")

# ---------------------------------------------------------------------------
# validation_prompts.md — single prompt
# ---------------------------------------------------------------------------
_VALIDATE_JD_PROMPT = _load_md("validation_prompts.md")

__all__ = [
    "_SYSTEM_PROMPT",
    "PARSE_JD_PROMPT",
    "EXTRACT_SKILLS_PROMPT",
    "COMPARE_SKILLS_PROMPT",
    "EXTRACT_PROJECTS_PROMPT",
    "REWRITE_RESUME_PROMPT",
    "POLISH_RESUME_PROMPT",
    "COVER_LETTER_PROMPT",
    "INTERVIEW_PREP_PROMPT",
    "VALIDATE_JD_PROMPT",
]

# Aliases for backward compatibility
PARSE_JD_PROMPT = _PARSE_JD_PROMPT
EXTRACT_SKILLS_PROMPT = _EXTRACT_SKILLS_PROMPT
COMPARE_SKILLS_PROMPT = _COMPARE_SKILLS_PROMPT
EXTRACT_PROJECTS_PROMPT = _EXTRACT_PROJECTS_PROMPT
REWRITE_RESUME_PROMPT = _REWRITE_RESUME_PROMPT
POLISH_RESUME_PROMPT = _POLISH_RESUME_PROMPT
COVER_LETTER_PROMPT = _COVER_LETTER_PROMPT
INTERVIEW_PREP_PROMPT = _INTERVIEW_PREP_PROMPT
VALIDATE_JD_PROMPT = _VALIDATE_JD_PROMPT
