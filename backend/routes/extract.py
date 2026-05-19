"""
routes/extract.py

POST /api/extract-keywords

Accepts a raw job description string, sends it to Claude for structured
keyword extraction, then cross-references results against base_resume.json
to flag gaps. Returns a fully-typed response the frontend can render
directly into KeywordSelector.jsx.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.claude_service import extract_keywords as claude_extract_keywords

router = APIRouter()

# ── Path to resume data ──────────────────────────────────────────────────────
BASE_RESUME_PATH = Path(__file__).resolve().parents[1] / "data" / "base_resume.json"


# ── Request / Response Models ────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    job_description: str


class Keyword(BaseModel):
    keyword: str
    category: str          # "hard_skill" | "soft_skill" | "role_signal"
    ats_weight: int        # 1 (low) – 10 (high)
    present_in_resume: bool
    context_snippet: str   # short phrase from JD that surfaced this keyword


class ExtractResponse(BaseModel):
    keywords: list[Keyword]
    role_level: str        # e.g. "Senior", "Staff", "IC", "Lead"
    gaps: list[str]        # keywords NOT found in resume (convenience field)
    raw_jd_word_count: int


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_base_resume() -> dict:
    """Load base_resume.json. Raises 500 if missing or malformed."""
    if not BASE_RESUME_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="base_resume.json not found. Run the resume ingestion step first."
        )
    try:
        return json.loads(BASE_RESUME_PATH.read_text())
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"base_resume.json is malformed: {e}")


def flatten_resume_keywords(resume: dict) -> set[str]:
    """
    Pull every keyword string out of base_resume.json into a flat lowercase set
    so we can do O(1) gap-checking against Claude's extracted keywords.

    Reads from:
      - skills.*  (all skill category lists)
      - experience[].bullets[].keywords[]
      - projects[].keywords[]
    """
    keywords: set[str] = set()

    # Skills block: {"languages": [...], "ai_ml": [...], ...}
    for skill_list in resume.get("skills", {}).values():
        if isinstance(skill_list, list):
            keywords.update(k.lower() for k in skill_list)

    # Experience bullets
    for job in resume.get("experience", []):
        for bullet in job.get("bullets", []):
            keywords.update(k.lower() for k in bullet.get("keywords", []))

    # Projects
    for project in resume.get("projects", []):
        keywords.update(k.lower() for k in project.get("keywords", []))

    return keywords


# ── Route ────────────────────────────────────────────────────────────────────

@router.post("/api/extract-keywords", response_model=ExtractResponse)
def extract_keywords_route(request: ExtractRequest) -> ExtractResponse:
    jd = request.job_description.strip()

    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")

    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    # 1. Load resume and flatten keywords for gap analysis
    resume = load_base_resume()
    resume_keywords = flatten_resume_keywords(resume)

    # 2. Call claude_service — handles prompting, API call, and JSON parsing
    try:
        kw_result = claude_extract_keywords(jd)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 3. Map KeywordExtractionResult into route-level Keyword objects,
    #    cross-referencing each term against the flattened resume keywords.
    #
    #    claude_service categorizes into: hard_skills, soft_skills,
    #    tools_and_technologies, job_titles, certifications, priority_keywords.
    #    We flatten all into a single list with category + ats_weight assigned here.

    CATEGORY_MAP = {
        "hard_skills":           ("hard_skill",  8),
        "tools_and_technologies":("hard_skill",  7),
        "soft_skills":           ("soft_skill",  4),
        "job_titles":            ("role_signal", 6),
        "certifications":        ("hard_skill",  5),
    }

    priority_set = {kw.lower() for kw in kw_result.priority_keywords}

    keywords: list[Keyword] = []
    gaps: list[str] = []
    seen: set[str] = set()   # deduplicate across categories

    for field, (category, base_weight) in CATEGORY_MAP.items():
        for kw in getattr(kw_result, field, []):
            kw_lower = kw.lower()
            if kw_lower in seen:
                continue
            seen.add(kw_lower)

            in_resume = kw_lower in resume_keywords
            ats_weight = 10 if kw_lower in priority_set else base_weight

            keywords.append(Keyword(
                keyword=kw,
                category=category,
                ats_weight=ats_weight,
                present_in_resume=in_resume,
                context_snippet="",   # claude_service v1 doesn't return snippets
            ))

            if not in_resume:
                gaps.append(kw)

    # 4. Sort: gaps first, then by ats_weight descending
    keywords.sort(key=lambda k: (k.present_in_resume, -k.ats_weight))

    # Infer role_level from job_titles field (first entry, or Unknown)
    role_level = kw_result.job_titles[0] if kw_result.job_titles else "Unknown"

    return ExtractResponse(
        keywords=keywords,
        role_level=role_level,
        gaps=gaps,
        raw_jd_word_count=len(jd.split()),
    )