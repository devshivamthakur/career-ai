"""
Prompt templates for the CareerAI agent workflows.

Each module contains carefully engineered prompts for a specific domain:
- ``jd_parsing_prompts`` — Job description analysis and keyword extraction
- ``skills_prompts`` — Resume skill extraction and ATS comparison
- ``resume_prompts`` — Resume rewriting and polishing
- ``cover_letter_prompts`` — Cover letter generation
- ``interview_prompts`` — Interview preparation Q&A
- ``validation_prompts`` — Input validation (JD quality checks)
"""

from app.prompts.jd_parsing_prompts import PARSE_JD_PROMPT
from app.prompts.skills_prompts import (
    EXTRACT_SKILLS_PROMPT,
    COMPARE_SKILLS_PROMPT,
    EXTRACT_PROJECTS_PROMPT,
)
from app.prompts.resume_prompts import REWRITE_RESUME_PROMPT, POLISH_RESUME_PROMPT
from app.prompts.cover_letter_prompts import COVER_LETTER_PROMPT
from app.prompts.interview_prompts import INTERVIEW_PREP_PROMPT
from app.prompts.validation_prompts import VALIDATE_JD_PROMPT

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
