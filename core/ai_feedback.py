"""
Qualitative AI feedback using the Groq API (free tier, OpenAI-compatible).

This is purely additive — it never raises exceptions that would break
the analysis pipeline. If the API key is missing, the call times out,
or anything goes wrong, it returns an empty string and the rest of the
analysis (score, keywords, formatting) proceeds completely unaffected.
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

MAX_RESUME_CHARS = 6000   # keep prompt size reasonable
MAX_JD_CHARS = 3000

# Groq's currently recommended fast/free-tier model.
# See https://console.groq.com/docs/models for the latest list if this
# model is ever deprecated.
GROQ_MODEL = "llama-3.3-70b-versatile"


def generate_ai_feedback(resume_text: str, job_description: str, job_title: str, company_name: str) -> str:
    """
    Sends the resume + JD to Groq's hosted LLM and asks for qualitative
    feedback. Returns an empty string on any failure — never raises.
    """
    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        logger.info("GROQ_API_KEY not set — skipping AI feedback.")
        return ''

    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        resume_snippet = resume_text[:MAX_RESUME_CHARS]
        jd_snippet = job_description[:MAX_JD_CHARS]

        prompt = f"""You are a professional resume reviewer. Below is a candidate's resume text and a job description they're applying for.

Job Title: {job_title}
Company: {company_name}

Job Description:
{jd_snippet}

Resume Text:
{resume_snippet}

Give concise, actionable feedback (max 200 words) covering:
1. The candidate's strongest alignment with this role
2. The biggest gap or risk a hiring manager might flag
3. One specific, concrete suggestion to improve fit

Write in plain, encouraging but honest language. Do not repeat the job description back. Do not use markdown headers — just clear paragraphs or a short bulleted list."""

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.4,
        )

        feedback_text = response.choices[0].message.content.strip()
        return feedback_text

    except Exception as exc:
        logger.warning("AI feedback generation failed: %s", exc)
        return ''
    