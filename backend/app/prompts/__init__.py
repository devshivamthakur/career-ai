"""
Prompt templates for the CareerAI agent workflows.

Prompts are stored as Markdown (.md) files in this directory and loaded
at runtime by ``app.prompts.loader``.

Each file contains carefully engineered prompts for a specific domain:
- ``jd_parsing_prompts`` — Job description analysis and keyword extraction
- ``skills_prompts`` — Resume skill extraction and ATS comparison
- ``resume_prompts`` — Resume rewriting and polishing
- ``cover_letter_prompts`` — Cover letter generation
- ``interview_prompts`` — Interview preparation Q&A
- ``validation_prompts`` — Input validation (JD quality checks)
"""

from app.prompts.loader import (
    PARSE_JD_PROMPT,
    EXTRACT_SKILLS_PROMPT,
    COMPARE_SKILLS_PROMPT,
    EXTRACT_PROJECTS_PROMPT,
    REWRITE_RESUME_PROMPT,
    POLISH_RESUME_PROMPT,
    COVER_LETTER_PROMPT,
    INTERVIEW_PREP_PROMPT,
    VALIDATE_JD_PROMPT,
)

__all__ = [
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
