"""
Agent Tools – Each tool is a self-contained function the agent can call.
Tools gather/transform data and may use LLM calls for analysis tasks.
"""

import json
import logging
import re
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from app.services.pdf_service import PDFParsingService
from app.core.llm import build_chat_model
from app.prompts.skills_prompts import COMPARE_SKILLS_PROMPT
from langchain_core.output_parsers import PydanticOutputParser

from app.schemas.resume_schemas import SkillsComparisonResult

logger = logging.getLogger(__name__)


# ── Pydantic schemas for structured tool args ──────────────────


class ExtractResumeTextInput(BaseModel):
    pdf_path: str = Field(description="Absolute path to the PDF resume file")


class CompareSkillsInput(BaseModel):
    job_requirements: str = Field(description="Parsed job description / requirements")
    user_profile: str = Field(description="Extracted resume profile and skills")


# ── Tool implementations ───────────────────────────────────────
# NOTE: Most tools gather / transform structured data without LLM calls.
# compare_skills is an exception — it uses an LLM for deep semantic analysis.


@tool("extract_resume_text", args_schema=ExtractResumeTextInput)
def extract_resume_text(pdf_path: str) -> str:
    """Extract raw text content from a PDF resume file."""
    logger.info("📄 Extracting resume text from %s", pdf_path)
    try:
        text = PDFParsingService.extract_text_from_pdf(pdf_path)
        if not text or len(text.strip()) < 50:
            return "Error: Could not extract sufficient text from PDF."
        return text
    except Exception as e:
        logger.exception("PDF extraction failed")
        return f"Error extracting PDF: {str(e)}"


@tool("parse_job_description")
def parse_job_description(job_description: str) -> str:
    """Clean and normalise a raw job description into plain text (remove HTML, excess whitespace, etc.)."""
    logger.info("🔍 Cleaning job description…")
    # Basic cleaning — no LLM involved
    text = re.sub(r"<[^>]+>", " ", job_description)  # strip HTML
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    text = text.strip()
    return text if text else "Empty job description provided."


@tool("extract_resume_skills")
def extract_resume_skills(resume_text: str) -> str:
    """Extract skills, experience and project mentions from resume text using pattern matching (no LLM)."""
    logger.info("📋 Extracting resume profile…")
    sections = re.split(r"\n(?=[A-Z][A-Za-z\s/]+:|\b(?:Education|Experience|Skills|Projects|Certifications)\b)", resume_text)
    # Return all non-empty sections for the model to process
    result_parts = []
    for i, section in enumerate(sections):
        section = section.strip()
        if section:
            result_parts.append(f"Section {i}: {section[:2000]}")
    return "\n\n".join(result_parts) if result_parts else resume_text[:5000]


@tool("extract_projects")
def extract_projects(resume_text: str) -> str:
    """Extract project-related sections from resume text using simple heuristics (no LLM)."""
    logger.info("📁 Extracting projects from resume…")
    # Simple heuristic: look for lines containing "project" or common project indicators
    lines = resume_text.split("\n")
    project_lines = []
    in_project_block = False
    for line in lines:
        lower = line.lower()
        if re.search(r"\b(project|built|developed|created|designed|implemented|led)\b", lower):
            in_project_block = True
        if in_project_block:
            project_lines.append(line)
            # Stop after collecting a reasonable amount
            if len(project_lines) >= 100:
                break
    if project_lines:
        return "\n".join(project_lines)
    # Fallback: return first portion of resume
    return resume_text[:3000]


@tool("compare_skills", args_schema=CompareSkillsInput)
def compare_skills(job_requirements: str, user_profile: str) -> str:
    """Use an LLM to deeply compare a candidate profile against a job description. Returns structured ATS analysis including matched/missing skills, score, and tailored recommendations."""
    logger.info("⚖️  Comparing skills via LLM…")
    try:
        from app.core.config import settings as app_settings
        llm = build_chat_model(streaming=False, max_tokens=app_settings.AGENT_MAX_TOKENS)
        skillscomparison_parser = PydanticOutputParser(pydantic_object=SkillsComparisonResult)
        prompt = COMPARE_SKILLS_PROMPT.format(
            job_requirements=job_requirements,
            user_profile=user_profile,
            output_format=skillscomparison_parser.get_format_instructions()
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content if hasattr(response, "content") else str(response)
        # Validate it's parseable JSON
        try:
            parsed = json.loads(content)
            raw_score = parsed.get("ats_score", "N/A")
            if isinstance(raw_score, dict):
                ats_score = raw_score.get("score", "N/A")
            else:
                ats_score = raw_score
            matched = parsed.get("matched_skills", [])
            missing = parsed.get("missing_skills", [])
            comparison = parsed.get("skills_comparison") or parsed.get("comparison_details", {})
            # Present analysis data cleanly — the LLM agent will paraphrase this.
            # DO NOT include raw JSON or internal labels that could leak.
            return (
                f"## Skills Comparison Result (LLM-powered)\n\n"
                f"**ATS Score:** {ats_score}/100\n\n"
                f"**Matched Skills ({len(matched)}):** {', '.join(matched[:30])}\n\n"
                f"**Missing Skills ({len(missing)}):** {', '.join(missing[:30])}\n\n"
                f"**Detailed Analysis:**\n{comparison}\n"
            )
        except (json.JSONDecodeError, TypeError):
            # If JSON parsing fails, return the raw LLM response
            return f"Skills Comparison (LLM-powered):\n{content}"
    except Exception as e:
        logger.exception("LLM-based skills comparison failed, falling back to keyword analysis")
        # Fallback to keyword-based comparison
        jd_words = set(re.findall(r"[a-zA-Z+#.]+", job_requirements.lower()))
        resume_words = set(re.findall(r"[a-zA-Z+#.]+", user_profile.lower()))
        jd_tech = {w for w in jd_words if len(w) > 2}
        resume_tech = {w for w in resume_words if len(w) > 2}
        matched = jd_tech & resume_tech
        missing = jd_tech - resume_tech
        score = int((len(matched) / max(len(jd_tech), 1)) * 100) if jd_tech else 50
        score = max(0, min(100, score))
        return (
            f"## Skills Comparison Result (keyword-based fallback)\n\n"
            f"**ATS Score (estimate):** {score}/100\n\n"
            f"**Matched Keywords ({len(matched)}):** {', '.join(sorted(matched)[:30])}\n\n"
            f"**Missing Keywords ({len(missing)}):** {', '.join(sorted(missing)[:30])}\n"
        )


# ── Master list of all tools ───────────────────────────────────
# Data-gathering and analysis tools. The agent model handles all
# rewriting, polishing, cover letters, interview prep.

ALL_TOOLS = [
    extract_resume_text,
    parse_job_description,
    extract_resume_skills,
    extract_projects,
    compare_skills,
]
