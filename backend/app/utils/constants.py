"""
Application-wide constants for the CareerAI backend.

Centralized constants for file size limits, job description length constraints,
streaming configuration, and resume detection heuristics.
"""

# ── File & Input Limits ─────────────────────────────────────────
MAX_FILE_SIZE_MB = 10
MIN_JOB_DESCRIPTION_LENGTH = 50
MAX_JOB_DESCRIPTION_LENGTH = 5000

# ── Streaming ───────────────────────────────────────────────────
STREAM_DELAY = 0  # Artificial delay between SSE chunks (0 = disabled)

# ── Resume section headings (for heuristic detection) ───────────
RESUME_SECTION_KEYWORDS = [
    "professional summary",
    "summary of qualifications",
    "summary",
    "profile",
    "career objective",
    "objective",
    "work experience",
    "experience",
    "professional experience",
    "employment history",
    "relevant experience",
    "technical skills",
    "skills",
    "core competencies",
    "education",
    "academic background",
    "projects",
    "key projects",
    "project experience",
    "certifications",
    "licenses",
    "certifications & licenses",
    "publications",
    "patents",
    "awards",
    "honors",
    "leadership",
    "volunteer experience",
    "languages",
    "interests",
    "additional information",
    "technical expertise",
    "tools & technologies",
]

RESUME_TRIGGER_KEYWORDS = [
    "rewrite", "tailor", "optimize", "ats", "resume", "cv", "curriculum",
    "job description", "jd", "cover letter", "application",
]
