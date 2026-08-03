from pydantic import BaseModel, Field, constr
from typing import Optional

from app.utils.constants import (
    MAX_COMPANY_LENGTH,
    MAX_JOB_DESCRIPTION_LENGTH,
    MAX_RESUME_TEXT_LENGTH,
    MAX_ROLE_LENGTH,
    MIN_JOB_DESCRIPTION_LENGTH,
)

# Pydantic model for the result of job description validation
class JDValidationResult(BaseModel):
    """Pydantic model for the result of job description validation."""
    is_valid: bool = Field(description="Whether the text is a valid job description.")
    reason: str=Field(description="Reason for the validation result.")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")

class SkillsComparisonResult(BaseModel):
    """Pydantic model for the result of skills comparison."""
    skills_comparison: str = Field(description="Detailed text comparison of skills")
    matched_skills: list[str] = Field(description="List of matched skills between resume and JD")
    missing_skills: list[str] = Field(description="List of skills required by JD but missing in resume")
    ats_score: int = Field(default=0, description="An ATS matching score between 0 and 100 representing how well the original resume matches the job description")


class ResumeExportRequest(BaseModel):
    resume_text: constr(strip_whitespace=True, min_length=50, max_length=100000)


# ── Career Cover Letter ─────────────────────────────────────

class CoverLetterRequest(BaseModel):
    job_description: str = Field(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH)
    company: str = Field(..., min_length=1, max_length=MAX_COMPANY_LENGTH)
    role: str = Field(..., min_length=1, max_length=MAX_ROLE_LENGTH)
    resume_text: Optional[str] = Field(default=None, max_length=MAX_RESUME_TEXT_LENGTH)


class CoverLetterResponse(BaseModel):
    cover_letter: str


# ── Career Interview Prep ───────────────────────────────────

class StarAnswer(BaseModel):
    situation: str
    task: str
    action: str
    result: str


class InterviewQuestion(BaseModel):
    question: str
    star_answer: StarAnswer


class InterviewPrepRequest(BaseModel):
    job_description: str = Field(..., min_length=MIN_JOB_DESCRIPTION_LENGTH, max_length=MAX_JOB_DESCRIPTION_LENGTH)
    role: str = Field(..., min_length=1, max_length=MAX_ROLE_LENGTH)
    company: Optional[str] = Field(default=None, max_length=MAX_COMPANY_LENGTH)
    resume_text: Optional[str] = Field(default=None, max_length=MAX_RESUME_TEXT_LENGTH)


class InterviewPrepResponse(BaseModel):
    questions: list[InterviewQuestion]


class InterviewQuestions(BaseModel):
    """Wrapper for structured LLM output of interview questions."""
    questions: list[InterviewQuestion]
