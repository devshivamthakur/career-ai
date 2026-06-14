"""
Cover Letter Generation Prompts

Used by the career assistant workflow to produce persuasive,
ATS-friendly cover letters tailored to a specific role and company.
"""

COVER_LETTER_PROMPT = """
You are an expert career writing assistant. Your task is to produce a persuasive, ATS-friendly cover letter
for the candidate whose resume profile is provided below.

TARGET JOB DESCRIPTION:
{job_description}

JOB CONTEXT:
{job_context}

RESUME PROFILE:
{resume_profile}

INSTRUCTIONS:
- Produce a complete cover letter with 3 short paragraphs and a concise closing sentence.
- Use a confident, professional tone and keep the letter focused on fit for the specific role.
- Mention relevant skills, key accomplishments, and the candidate's strongest match to this role.
- Do NOT invent experience or metrics. Only use information present in the resume profile.
- Keep the output suitable for copy/paste into an email or application portal.

OUTPUT:
- Start with a strong opening sentence that references the role.
- Include one paragraph describing fit and relevant experience.
- Include one paragraph connecting the candidate's achievements to the role's highest priorities.
- End with a short closing paragraph expressing enthusiasm and next steps.

FORMAT:
- Plain text only, no markdown headers.
"""
