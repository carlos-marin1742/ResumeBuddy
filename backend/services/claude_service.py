"""
claude_service.py
-----------------
Core Anthropic API integration for the ATS resume builder.

Responsibilities:
  1. extract_keywords(job_description: str) -> KeywordExtractionResult
     Pulls structured keywords (hard skills, soft skills, titles, etc.) from a JD.

  2. tailor_resume(base_resume: dict, job_description: str, selected_keywords: list[str]) -> TailoredResume
     Rewrites bullets and generates a targeted summary against a specific JD.

  3. score_resume(tailored_resume: dict, job_description: str) -> ATSScoreResult
     Evaluates keyword coverage and ATS compatibility of the tailored output.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os
import re
from typing import Any

import anthropic
from pydantic import BaseModel
 

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class KeywordExtractionResult(BaseModel):
    hard_skills: list[str]
    soft_skills: list[str]
    tools_and_technologies: list[str]
    job_titles: list[str]
    certifications: list[str]
    priority_keywords: list[str]   # top ~10 must-haves for this role
    raw_response: str              # preserved for debugging


class TailoredBullet(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str]


class TailoredExperience(BaseModel):
    company: str
    title: str
    tailored_bullets: list[TailoredBullet]


class TailoredResume(BaseModel):
    summary: str
    experiences: list[TailoredExperience]
    skills_to_highlight: list[str]
    raw_response: str


class ATSScoreResult(BaseModel):
    overall_score: int             # 0–100
    keyword_coverage: float        # 0.0–1.0
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.Anthropic:
    """Return an Anthropic client, reading the key from the environment."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return anthropic.Anthropic(api_key=api_key)


MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048

# ---------------------------------------------------------------------------
# Helper: call the API and return the text content
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Thin wrapper around the Messages API. Returns the assistant text."""
    client = _get_client()
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _extract_json(text: str) -> Any:
    """
    Strip markdown fences and parse JSON.
    Handles both ```json ... ``` and raw JSON blobs.
    """
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# 1. Keyword extraction
# ---------------------------------------------------------------------------

_KEYWORD_EXTRACTION_SYSTEM = """\
You are an expert ATS (Applicant Tracking System) analyst and technical recruiter.
Your job is to analyze job descriptions and extract structured keyword data that
a candidate can use to tailor their resume for maximum ATS compatibility.

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation.
"""

_KEYWORD_EXTRACTION_SCHEMA = {
    "hard_skills": ["list of specific technical skills, e.g. Python, Kubernetes, SQL"],
    "soft_skills": ["list of soft skills mentioned explicitly, e.g. leadership, communication"],
    "tools_and_technologies": ["specific tools, frameworks, platforms, e.g. dbt, Terraform, React"],
    "job_titles": ["related job titles or seniority levels mentioned"],
    "certifications": ["certs or degrees the JD mentions or implies"],
    "priority_keywords": ["top 10 must-have keywords ranked by emphasis in the JD"],
}


def extract_keywords(job_description: str) -> KeywordExtractionResult:
    """
    Parse a job description and return structured keyword categories.

    Args:
        job_description: Raw text of the job description.

    Returns:
        KeywordExtractionResult with categorized and prioritized keywords.
    """
    user_prompt = f"""\
Analyze the following job description and extract keywords.

Return a JSON object that matches this schema exactly:
{json.dumps(_KEYWORD_EXTRACTION_SCHEMA, indent=2)}

JOB DESCRIPTION:
{job_description}
"""
    raw = _call_claude(_KEYWORD_EXTRACTION_SYSTEM, user_prompt)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON for keyword extraction: {exc}\n\nRaw:\n{raw}") from exc

    return KeywordExtractionResult(
        hard_skills=parsed.get("hard_skills", []),
        soft_skills=parsed.get("soft_skills", []),
        tools_and_technologies=parsed.get("tools_and_technologies", []),
        job_titles=parsed.get("job_titles", []),
        certifications=parsed.get("certifications", []),
        priority_keywords=parsed.get("priority_keywords", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# 2. Resume tailoring
# ---------------------------------------------------------------------------

_TAILORING_SYSTEM = """\
You are an expert resume writer with deep experience tailoring resumes across technical, clinical, and administrative roles.
You rewrite resume bullets to emphasize relevance to a specific job description while:
  - Preserving all factual accuracy (never invent metrics or experiences)
  - Keeping bullets concise (1–2 lines, action-verb first)
  - Naturally weaving in the provided keywords
  - Maintaining strong impact framing (STAR-adjacent: action → scale → result)
  - Never using em-dashes (—) or en-dashes (–) anywhere in the output; use commas, colons, or rephrase instead

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation.
"""

def tailor_resume(
    base_resume: dict,
    job_description: str,
    selected_keywords: list[str],
) -> TailoredResume:
    """
    Generate a tailored version of the resume for a specific job.

    Args:
        base_resume:       The parsed base_resume.json as a Python dict.
        job_description:   Full text of the target job description.
        selected_keywords: Keywords the user confirmed they want to target
                           (typically from extract_keywords → user selection in the UI).

    Returns:
        TailoredResume with a new summary, rewritten bullets, and highlighted skills.
    """
    # Slim the payload — send only the fields Claude needs
    resume_payload = {
        "summary": base_resume.get("summary", ""),
        "skills": base_resume.get("skills", {}),
        "experience": [
            {
                "company": exp.get("company"),
                "title": exp.get("title"),
                "bullets": [b.get("text") for b in exp.get("bullets", [])],
            }
            for exp in base_resume.get("experience", [])
        ],
    }

    response_schema = {
        "summary": "A 2–3 sentence targeted professional summary for this specific role",
        "experiences": [
            {
                "company": "string",
                "title": "string",
                "tailored_bullets": [
                    {
                        "original": "exact original bullet text",
                        "tailored": "rewritten bullet",
                        "keywords_injected": ["keyword1", "keyword2"],
                    }
                ],
            }
        ],
        "skills_to_highlight": ["skills from the candidate's profile most relevant to this JD"],
    }

    user_prompt = f"""\
Tailor the following resume for the job description below.

KEYWORDS TO INCORPORATE (selected by the candidate):
{json.dumps(selected_keywords, indent=2)}

BASE RESUME DATA:
{json.dumps(resume_payload, indent=2)}

JOB DESCRIPTION:
{job_description}

Return a JSON object matching this schema exactly:
{json.dumps(response_schema, indent=2)}

Rules:
- Only rewrite bullets where adding keywords genuinely improves relevance.
- Never fabricate metrics, technologies, or experiences.
- Never add credentials, licenses, or certifications the candidate does not already have in their profile (e.g. do not add RN, MD, PMP, or any license not listed in the certifications section).
- Preserve the candidate's voice — do not over-polish into generic corporate speak.
- Every tailored bullet must start with a strong past-tense action verb.
- Use exactly 4 bullets for the first two roles and exactly 3 bullets for the third (oldest) role.
- Never use fewer bullets than specified — a short resume wastes space.
"""
    raw = _call_claude(_TAILORING_SYSTEM, user_prompt, max_tokens=4096)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON for resume tailoring: {exc}\n\nRaw:\n{raw}") from exc

    experiences = [
        TailoredExperience(
            company=exp["company"],
            title=exp["title"],
            tailored_bullets=[
                TailoredBullet(**b) for b in exp.get("tailored_bullets", [])
            ],
        )
        for exp in parsed.get("experiences", [])
    ]

    return TailoredResume(
        summary=parsed.get("summary", ""),
        experiences=experiences,
        skills_to_highlight=parsed.get("skills_to_highlight", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# 3. ATS scoring
# ---------------------------------------------------------------------------

_SCORING_SYSTEM = """\
You are an ATS (Applicant Tracking System) simulation engine.
Evaluate how well a resume matches a job description from an ATS perspective.
Be honest and critical — this feedback helps the candidate improve.

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation.
"""

_SCORING_SCHEMA = {
    "overall_score": "integer 0–100 representing overall ATS match quality",
    "keyword_coverage": "float 0.0–1.0 representing fraction of priority keywords present",
    "matched_keywords": ["keywords from the JD found in the resume"],
    "missing_keywords": ["important keywords from the JD absent from the resume"],
    "suggestions": ["2–5 specific, actionable improvements"],
}


def score_resume(tailored_resume: dict, job_description: str) -> ATSScoreResult:
    """
    Score a tailored resume against a job description for ATS compatibility.

    Args:
        tailored_resume: The assembled resume dict (post-tailoring, pre-docx).
        job_description: The target job description.

    Returns:
        ATSScoreResult with score, coverage stats, and improvement suggestions.
    """
    user_prompt = f"""\
Score the following resume against the job description for ATS compatibility.

RESUME:
{json.dumps(tailored_resume, indent=2)}

JOB DESCRIPTION:
{job_description}

Return a JSON object matching this schema exactly:
{json.dumps(_SCORING_SCHEMA, indent=2)}
"""
    raw = _call_claude(_SCORING_SYSTEM, user_prompt)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON for ATS scoring: {exc}\n\nRaw:\n{raw}") from exc

    return ATSScoreResult(
        overall_score=parsed.get("overall_score", 0),
        keyword_coverage=parsed.get("keyword_coverage", 0.0),
        matched_keywords=parsed.get("matched_keywords", []),
        missing_keywords=parsed.get("missing_keywords", []),
        suggestions=parsed.get("suggestions", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# Quick smoke test (run directly: python claude_service.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_jd = """\
    We are looking for a Senior ML Engineer to join our AI Platform team.
    You will design and deploy large-scale machine learning pipelines using Python,
    PyTorch, and Kubernetes. Experience with MLflow, dbt, and AWS SageMaker is a plus.
    Strong communication skills and the ability to lead cross-functional initiatives required.
    """

    print("--- Keyword Extraction ---")
    kw_result = extract_keywords(sample_jd)
    print(json.dumps(kw_result.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- Resume Tailoring (stub) ---")
    stub_resume = {
        "summary": "Software engineer with 5 years of experience in ML systems.",
        "skills": {"languages": ["Python", "SQL"], "ai_ml": ["PyTorch", "scikit-learn"]},
        "experience": [
            {
                "company": "Acme Corp",
                "title": "ML Engineer",
                "bullets": [
                    {"text": "Built training pipelines that reduced model iteration time by 40%."},
                    {"text": "Collaborated with product teams to ship recommendation features."},
                ],
            }
        ],
    }
    tailored = tailor_resume(stub_resume, sample_jd, kw_result.priority_keywords)
    print(json.dumps(tailored.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- ATS Score ---")
    score = score_resume(tailored.model_dump(exclude={"raw_response"}), sample_jd)
    print(json.dumps(score.model_dump(exclude={"raw_response"}), indent=2))