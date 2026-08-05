"""
Agent Tools – Each tool is a self-contained function the agent can call.
Tools gather/transform data and may use LLM calls for analysis tasks.
"""

import json
import logging
import os
import re
from pydantic import BaseModel, Field

from langchain_core.messages import HumanMessage

from app.services.pdf_service import PDFParsingService
from app.core.llm import build_chat_model
from app.prompts.loader import COMPARE_SKILLS_PROMPT
from langchain_core.output_parsers import PydanticOutputParser

from app.schemas.resume_schemas import SkillsComparisonResult

logger = logging.getLogger(__name__)

# ── In-memory cache for tool results ──────────────────────────
# Prevents redundant calls (PDF parsing is expensive, tool limits are tight).
_tool_cache: dict[str, str] = {}


def _warm_tool_cache(tool_name: str, result: str) -> None:
    """Pre-populate the in-memory tool cache with a known result.
    
    Used by the route handler after extracting resume text at upload time,
    so the agent's tool call returns instantly without hitting middleware limits.
    Creates a sentinel key so any invocation of the tool (regardless of pdf_path)
    returns the cached result directly.
    """
    _tool_cache[f"prewarm:{tool_name}"] = result
    logger.info("🔥 Pre-warmed %s cache (%d chars)", tool_name, len(result))


# ── Pydantic schemas for structured tool args ──────────────────


class ExtractResumeTextInput(BaseModel):
    pdf_path: str = Field(description="Absolute path to the PDF resume file")


class CompareSkillsInput(BaseModel):
    job_requirements: str = Field(description="Parsed job description / requirements")
    user_profile: str = Field(description="Extracted resume profile and skills")


# ── Tool implementations ───────────────────────────────────────
# NOTE: Most tools gather / transform structured data without LLM calls.
# compare_skills is an exception — it uses an LLM for deep semantic analysis.


def _resolve_storage_path(pdf_path: str) -> str:
    """Resolve a PDF path that may be relative (e.g. ``storage/resume_x.pdf``).

    Files are saved under ``app/storage/`` at upload time, but the LLM often
    passes the relative ``storage/...`` string from the message marker. If the
    path is not absolute and doesn't exist as-is, fall back to the app
    package directory so the file is always found regardless of the server's
    working directory (important under gunicorn workers).
    """
    if os.path.isabs(pdf_path) or os.path.exists(pdf_path):
        return pdf_path

    # tools.py lives at app/agents/tools.py → package root is two levels up
    app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(app_root, pdf_path)
    if os.path.exists(candidate):
        logger.info("Resolved PDF path %s → %s", pdf_path, candidate)
        return candidate

    return pdf_path


def extract_resume_text(pdf_path: str) -> str:
    """Extract raw text content from a PDF resume file. 
    CRITICAL: Only call this tool when you can see a `[File saved to: ...]` or `[Resume file uploaded: ...]` marker in the conversation. 
    If there is no such marker, do NOT call this tool — ask the user to upload their resume PDF first. 
    If you already have the resume text in context (from a previous turn or the current message), 
    you do NOT need to call this tool.
    """

    # Serve from the prewarm cache first — the route extracts the text at
    # upload time, so any invocation (any worker, any path) returns instantly.
    cached = _tool_cache.get("prewarm:extract_resume_text")
    if cached:
        logger.info("⚡ extract_resume_text served from prewarm cache (%d chars)", len(cached))
        return cached

    resolved_path = _resolve_storage_path(pdf_path)
    logger.info("📄 Extracting resume text from %s (cache miss)", resolved_path)
    try:
        text = PDFParsingService.extract_text_from_pdf(resolved_path)
        if not text or len(text.strip()) < 50:
            return "Error: Could not extract sufficient text from PDF."
        return text
    except Exception as e:
        logger.exception("PDF extraction failed")
        return f"Error extracting PDF: {str(e)}"


def parse_job_description(job_description: str) -> str:
    """Clean and normalise a raw job description into plain text (remove HTML, excess whitespace, etc.). Call this tool AT MOST ONCE per job description — if you already have a parsed/cleaned version from a previous call, do NOT call it again. Do NOT call this tool if the job description is already clean plain text."""
    logger.info("🔍 Cleaning job description…")
    # Basic cleaning — no LLM involved
    text = re.sub(r"<[^>]+>", " ", job_description)  # strip HTML
    text = re.sub(r"\s+", " ", text)  # collapse whitespace
    text = text.strip()
    return text if text else "Empty job description provided."


def extract_resume_skills(resume_text: str) -> str:
    """Extract skills, experience and project mentions from resume text using pattern matching (no LLM). Call this tool AT MOST ONCE per resume — if you have already called it and have the extracted profile, do NOT call it again. This tool is OPTIONAL — only use it if you need a distilled skill profile for analysis."""
    logger.info("📋 Extracting resume profile…")
    sections = re.split(r"\n(?=[A-Z][A-Za-z\s/]+:|\b(?:Education|Experience|Skills|Projects|Certifications)\b)", resume_text)
    # Return all non-empty sections for the model to process
    result_parts = []
    for i, section in enumerate(sections):
        section = section.strip()
        if section:
            result_parts.append(f"Section {i}: {section[:2000]}")
    return "\n\n".join(result_parts) if result_parts else resume_text[:5000]


def extract_projects(resume_text: str) -> str:
    """Extract project-related sections from resume text using simple heuristics (no LLM). Call this tool AT MOST ONCE per resume. Only use if you need specific project details for interview prep or cover letters. Skip this tool for simple resume rewrites."""
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


def compare_skills(job_requirements: str, user_profile: str) -> str:
    """Use an LLM to deeply compare a candidate profile against a job description. Returns structured ATS analysis including matched/missing skills, score, and tailored recommendations. CRITICAL: Call this tool AT MOST ONCE per comparison. Only call it when you have BOTH an extracted/parsed job description AND a resume profile. NEVER call this tool multiple times with the same inputs."""
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
