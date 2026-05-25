from pydantic import BaseModel, Field
from typing import TypedDict as TypeDict

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
    ats_score: int = Field(description="An ATS matching score between 0 and 100 representing how well the original resume matches the job description")

# Define the state schema for the graph
class ResumeTailorState(TypeDict):
    """State object for the resume tailoring workflow."""
    cv_text: str
    job_description: str
    jd_analysis: str = ""
    cv_analysis: str = ""
    skills_comparison: str = ""
    matched_skills: list[str] = []
    missing_skills: list[str] = []
    ats_score: int = 0
    tailored_resume: str = ""
    final_resume: str = ""
    error: str = None


class ResumeExportRequest(BaseModel):
    resume_text: str
