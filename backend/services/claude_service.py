"""
claude_service.py
-----------------
AI service layer for the ATS resume builder.

Responsibilities:
  1. extract_keywords(job_description: str) -> KeywordExtractionResult
     Pulls structured keywords from a JD using Groq (free tier, fast).

  2. tailor_resume(base_resume: dict, job_description: str, selected_keywords: list[str]) -> TailoredResume
     Rewrites bullets and generates a targeted summary using Claude Haiku.

  3. score_resume(tailored_resume: dict, job_description: str, selected_keywords: list[str]) -> ATSScoreResult
     Heuristic ATS scoring — no API call, fast and deterministic.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os
import re
import string
from typing import Any

import anthropic
from groq import Groq
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
    priority_keywords: list[str]
    raw_response: str


class TailoredBullet(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str] = []


class TailoredExperience(BaseModel):
    company: str
    title: str
    tailored_bullets: list[TailoredBullet]


class TailoredProject(BaseModel):
    name: str
    tailored_bullets: list[TailoredBullet]


class TailoredResume(BaseModel):
    summary: str
    experiences: list[TailoredExperience]
    projects: list[TailoredProject] = []
    skills_to_highlight: list[str]
    skills_to_add: dict[str, list[str]] = {}
    skills_to_show: list[str] = []
    skills_to_filter: dict[str, list[str]] = {}
    raw_response: str


class ATSScoreResult(BaseModel):
    overall_score: int
    keyword_coverage: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return anthropic.Anthropic(api_key=api_key)


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return Groq(api_key=api_key)


CLAUDE_MODEL      = "claude-haiku-4-5-20251001"
GROQ_MODEL        = "llama-3.3-70b-versatile"
CLAUDE_MAX_TOKENS = 4096
GROQ_MAX_TOKENS   = 2048


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int = CLAUDE_MAX_TOKENS) -> str:
    client = _get_anthropic_client()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _call_groq(system: str, user: str, max_tokens: int = GROQ_MAX_TOKENS) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> Any:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(cleaned)


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy keyword matching."""
    return text.lower().translate(str.maketrans("", "", string.punctuation))


# ---------------------------------------------------------------------------
# 1. Keyword extraction — Groq (free tier)
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
    user_prompt = f"""\
Analyze the following job description and extract keywords.

Return a JSON object that matches this schema exactly:
{json.dumps(_KEYWORD_EXTRACTION_SCHEMA, indent=2)}

JOB DESCRIPTION:
{job_description}
"""
    raw = _call_groq(_KEYWORD_EXTRACTION_SYSTEM, user_prompt)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Groq returned non-JSON for keyword extraction: {exc}\n\nRaw:\n{raw}") from exc

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
# 2. Resume tailoring — Claude Haiku
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
        "projects": [
            {
                "name": proj.get("name"),
                "bullets": [b.get("text") for b in proj.get("bullets", [])],
            }
            for proj in base_resume.get("projects", [])
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
        "projects": [
            {
                "name": "string",
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
        "skills_to_add": {
            "category_name": ["new skill 1", "new skill 2", "new skill 3"]
        },
        "skills_to_show": ["category_key1", "category_key2", "category_key3"],
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
- If the resume has projects, use exactly 3 bullets for the experience role. If the resume has no projects, use exactly 5 bullets for the first two roles and exactly 4 bullets for the third (oldest) role.
- If the resume has projects, use exactly 3 bullets for the experience role and never fabricate bullets to reach a higher count.
- Keep the same number of bullets per project as in the original — do not add or remove project bullets.
- Never remove quantified metrics (percentages, numbers, counts) from any bullet regardless of character limit.
- For project bullets: only append keywords to the END of the original bullet text where natural. Never rewrite, restructure, or remove any part of the original. If a keyword cannot be appended naturally, leave the bullet unchanged.
- Never use fewer bullets than specified — a short resume wastes space.
- Keep every bullet to a maximum of 165 characters. For project bullets where the original is already near the limit, skip the keyword append rather than truncating.
- If selected_keywords include skills not present in the candidate's skills section, add them to skills_to_add if they are closely related to existing skills in the profile (e.g. TypeScript if JavaScript is present, Tailwind if CSS is present).
- Set skills_to_show to the skill category keys most relevant to this JD. For AI/ML roles include ai_ml. For pure backend/fullstack roles omit ai_ml. Always include languages, backend, frontend, databases_cloud, and tools unless irrelevant. Use the exact category key names from the skills object.
"""
    raw = _call_claude(_TAILORING_SYSTEM, user_prompt, max_tokens=CLAUDE_MAX_TOKENS)

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

    projects = [
        TailoredProject(
            name=proj["name"],
            tailored_bullets=[
                TailoredBullet(**b) for b in proj.get("tailored_bullets", [])
            ],
        )
        for proj in parsed.get("projects", [])
    ]

    return TailoredResume(
        summary=parsed.get("summary", ""),
        experiences=experiences,
        projects=projects,
        skills_to_highlight=parsed.get("skills_to_highlight", []),
        skills_to_add=parsed.get("skills_to_add", {}),
        skills_to_show=parsed.get("skills_to_show", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# 3. ATS scoring — heuristic (no API call)
# ---------------------------------------------------------------------------

def score_resume(
    tailored_resume: dict,
    job_description: str,
    selected_keywords: list[str] | None = None,
) -> ATSScoreResult:
    """
    Heuristic ATS scoring — fast, free, deterministic.

    Strategy:
    - Flatten all resume text into a searchable corpus
    - Check each selected keyword against the corpus
    - Score = matched / total * 100
    - Generate actionable suggestions based on gap patterns
    """
    selected_keywords = selected_keywords or []

    # ── Build resume text corpus ──────────────────────────────────────────
    corpus_parts = []

    # Summary
    corpus_parts.append(tailored_resume.get("tailored_summary", ""))

    # Skills
    for skill_list in tailored_resume.get("skills", {}).values():
        if isinstance(skill_list, list):
            corpus_parts.extend(skill_list)

    # Experience bullets
    for exp in tailored_resume.get("experience", []):
        corpus_parts.append(exp.get("title", ""))
        for bullet in exp.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    # Projects
    for proj in tailored_resume.get("projects", []):
        corpus_parts.append(proj.get("name", ""))
        for bullet in proj.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    # Certifications
    for cert in tailored_resume.get("certifications", []):
        corpus_parts.append(cert.get("name", ""))
        corpus_parts.append(cert.get("issuer", ""))

    corpus = _normalize(" ".join(corpus_parts))

    # ── Match keywords ────────────────────────────────────────────────────
    matched = []
    missing = []

    for kw in selected_keywords:
        kw_normalized = _normalize(kw)
        # Check if all words in the keyword appear in the corpus
        kw_words = kw_normalized.split()
        if all(word in corpus for word in kw_words):
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(selected_keywords)
    coverage = len(matched) / total if total > 0 else 0.0

    # ── Score calculation ─────────────────────────────────────────────────
    # Base score from keyword coverage (70% weight)
    # Bonus points for having summary, multiple experiences, certifications (30% weight)
    base_score = coverage * 70

    bonus = 0
    if tailored_resume.get("tailored_summary"):
        bonus += 10
    if len(tailored_resume.get("experience", [])) >= 2:
        bonus += 10
    if tailored_resume.get("certifications"):
        bonus += 10

    overall_score = min(100, int(base_score + bonus))

    # ── Generate suggestions ──────────────────────────────────────────────
    suggestions = []

    if missing:
        top_missing = missing[:3]
        suggestions.append(
            f"Add these missing keywords to your resume: {', '.join(top_missing)}."
        )

    if coverage < 0.6:
        suggestions.append(
            "Keyword coverage is below 60%. Select more relevant keywords and regenerate."
        )

    if not tailored_resume.get("tailored_summary"):
        suggestions.append("Add a targeted summary section to improve ATS matching.")

    skill_count = sum(
        len(v) for v in tailored_resume.get("skills", {}).values()
        if isinstance(v, list)
    )
    if skill_count < 10:
        suggestions.append(
            "Expand your skills section — more relevant skills improve ATS keyword density."
        )

    if len(missing) > len(matched):
        suggestions.append(
            "More than half your target keywords are missing. Consider selecting fewer, "
            "more relevant keywords or tailoring to a closer-match role."
        )

    # Always give at least one suggestion
    if not suggestions:
        suggestions.append(
            "Strong keyword match. Review the missing keywords above and add any you genuinely have."
        )

    return ATSScoreResult(
        overall_score=overall_score,
        keyword_coverage=round(coverage, 2),
        matched_keywords=matched,
        missing_keywords=missing,
        suggestions=suggestions[:5],
        raw_response="heuristic",
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

    print("--- Keyword Extraction (Groq) ---")
    kw_result = extract_keywords(sample_jd)
    print(json.dumps(kw_result.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- Resume Tailoring (Claude Haiku) ---")
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
        "projects": [],
    }
    tailored = tailor_resume(stub_resume, sample_jd, kw_result.priority_keywords)
    print(json.dumps(tailored.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- ATS Score (Heuristic) ---")
    score = score_resume(
        tailored.model_dump(exclude={"raw_response"}),
        sample_jd,
        kw_result.priority_keywords,
    )
    print(json.dumps(score.model_dump(exclude={"raw_response"}), indent=2))