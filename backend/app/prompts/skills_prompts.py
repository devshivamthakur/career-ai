"""
Resume Skills Extraction and ATS Comparison Prompts

Used by the resume tailoring and career assistant workflows to extract
structured skill profiles from resumes and compare them against
job description requirements.
"""

EXTRACT_SKILLS_PROMPT = """
You are a professional resume parser and career intelligence engine. Extract a complete, structured
profile from the resume below. This profile will be used to compare against a job description and
drive targeted resume rewriting.

─────────────────────────────────────────────
RESUME TEXT:
{resume_text}
─────────────────────────────────────────────

EXTRACTION REQUIREMENTS — Produce a JSON object with the following schema:

{{
  "contact": {{
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "portfolio": ""
  }},

  "summary": "The candidate's professional summary or objective, verbatim or synthesized.",

  "total_years_experience": 0,

  "work_experience": [
    {{
      "title": "",
      "company": "",
      "duration": "",
      "years": 0.0,
      "responsibilities": [],
      "achievements": [],
      "technologies_used": [],
      "inferred_soft_skills": []
    }}
  ],

  "skills": {{
    "programming_languages": [],
    "frameworks_and_libraries": [],
    "databases": [],
    "cloud_and_devops": [],
    "ai_ml": [],
    "tools": [],
    "methodologies": [],
    "other": []
  }},

  "education": [
    {{
      "degree": "",
      "field": "",
      "institution": "",
      "year": "",
      "gpa": "",
      "honors": []
    }}
  ],

  "certifications": [
    {{
      "name": "",
      "issuer": "",
      "year": ""
    }}
  ],

  "projects": [
    {{
      "name": "",
      "description": "",
      "technologies": [],
      "impact": ""
    }}
  ],

  "languages": [],

  "publications_or_talks": [],

  "key_metrics_and_achievements": [
    "List all quantifiable results found anywhere in the resume — e.g., '40% latency reduction', 'led team of 8', '$2M cost saved'"
  ],

  "inferred_strengths": [
    "Top 5 strengths inferred from the overall resume pattern"
  ]
}}

INSTRUCTIONS:
- Extract verbatim where possible; synthesize only when necessary.
- For years of experience per role, calculate based on date ranges. Estimate if ranges are ambiguous.
- Capture ALL technologies — even those mentioned in passing.
- Flag missing but expected fields (e.g., no summary, no metrics) in a separate "gaps" array.
- Return only valid JSON. No markdown, no preamble, no explanation.
"""

COMPARE_SKILLS_PROMPT = """
You are an elite ATS resume strategist and hiring intelligence expert.

Your task is to deeply compare a candidate profile against a target job description
and generate a structured ATS-focused skill analysis in JSON format.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOB REQUIREMENTS ANALYSIS:
{job_requirements}

CANDIDATE PROFILE:
{user_profile}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JSON OUTPUT SCHEMA:
You MUST output a single, valid JSON object with the following schema.
Do NOT include markdown formatting (e.g., ```json) or any other text outside the JSON object.
{output_format}


IMPORTANT RULES:
- Be highly specific and actionable in your analysis.
- Never hallucinate skills; base all analysis on the provided profile.
- Return an empty list `[]` for `matched_skills` or `missing_skills` if none are found.
- Think like both an ATS system and a senior recruiter.
- Use concise but detailed professional analysis.
- Avoid generic feedback. The entire output must be a single JSON object.
"""

EXTRACT_PROJECTS_PROMPT = """
You are a resume intelligence analyst. Extract the candidate's most relevant projects from the resume text below.
Return a JSON array of up to 4 objects with keys: name, role, technologies, challenge, action, impact.
If a project is not explicitly named, summarize the work in a short project description.

RESUME TEXT:
{resume_text}

OUTPUT MUST BE VALID JSON ONLY.

"""
