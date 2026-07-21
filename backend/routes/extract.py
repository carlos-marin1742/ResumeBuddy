"""
routes/extract.py

POST /api/extract-keywords

Accepts a raw job description string and resume_id, sends it to Claude for
structured keyword extraction, then cross-references results against the
selected resume JSON to flag gaps. Returns a fully-typed response the
frontend can render directly into KeywordSelector.jsx.
"""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.claude_service import extract_keywords as claude_extract_keywords

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


# ── Request / Response Models ────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    job_description: str
    resume_id: str = "base_resume"


class Keyword(BaseModel):
    keyword: str
    category: str          # "hard_skill" | "soft_skill" | "role_signal"
    ats_weight: int        # 1 (low) – 10 (high)
    present_in_resume: bool
    context_snippet: str


class ExtractResponse(BaseModel):
    keywords: list[Keyword]
    role_level: str
    gaps: list[str]
    raw_jd_word_count: int


# ── Helpers ──────────────────────────────────────────────────────────────────

def load_resume(resume_id: str) -> dict:
    path = DATA_DIR / f"{resume_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Resume '{resume_id}' not found.")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Resume file is malformed: {e}")


def flatten_resume_keywords(resume: dict) -> set[str]:
    """
    Pull every keyword string out of a resume JSON into a flat lowercase set
    for O(1) gap-checking against Claude's extracted keywords.
    """
    keywords: set[str] = set()

    skills = resume.get("skills", {})
    if isinstance(skills, dict):
        skill_lists = skills.values()
    elif isinstance(skills, list):
        # Current resume schema: [{"category": "Languages", "items": [...]}]
        skill_lists = (
            section.get("items", [])
            for section in skills
            if isinstance(section, dict)
        )
    else:
        skill_lists = []

    for skill_list in skill_lists:
        if isinstance(skill_list, list):
            keywords.update(
                skill.lower() for skill in skill_list if isinstance(skill, str)
            )

    for job in resume.get("experience", []):
        for bullet in job.get("bullets", []):
            if isinstance(bullet, dict):
                bullet_keywords = bullet.get("keywords", bullet.get("tags", []))
                keywords.update(
                    keyword.lower()
                    for keyword in bullet_keywords
                    if isinstance(keyword, str)
                )

    for project in resume.get("projects", []):
        for bullet in project.get("bullets", []):
            if isinstance(bullet, dict):
                bullet_keywords = bullet.get("keywords", bullet.get("tags", []))
                keywords.update(
                    keyword.lower()
                    for keyword in bullet_keywords
                    if isinstance(keyword, str)
                )

    return keywords


# ── Route ────────────────────────────────────────────────────────────────────

@router.post("/api/extract-keywords", response_model=ExtractResponse)
def extract_keywords_route(request: ExtractRequest) -> ExtractResponse:
    jd = request.job_description.strip()

    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")

    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    # Validate resume_id exists in data directory
    valid_ids = [f.stem for f in DATA_DIR.glob("*.json")]
    if request.resume_id not in valid_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown resume_id '{request.resume_id}'. Available: {valid_ids}"
        )

    # 1. Load resume and flatten keywords for gap analysis
    resume = load_resume(request.resume_id)
    resume_keywords = flatten_resume_keywords(resume)

    # 2. Call claude_service
    try:
        kw_result = claude_extract_keywords(jd)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 3. Map into Keyword objects, cross-referencing against resume keywords
    CATEGORY_MAP = {
        "hard_skills":            ("hard_skill",  8),
        "tools_and_technologies": ("hard_skill",  7),
        "soft_skills":            ("soft_skill",  4),
        "job_titles":             ("role_signal", 6),
        "certifications":         ("hard_skill",  5),
    }

    priority_set = {kw.lower() for kw in kw_result.priority_keywords}

    keywords: list[Keyword] = []
    gaps: list[str] = []
    seen: set[str] = set()

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
                context_snippet="",
            ))

            if not in_resume:
                gaps.append(kw)

    # 4. Sort: gaps first, then by ats_weight descending
    keywords.sort(key=lambda k: (k.present_in_resume, -k.ats_weight))

    role_level = kw_result.job_titles[0] if kw_result.job_titles else "Unknown"

    return ExtractResponse(
        keywords=keywords,
        role_level=role_level,
        gaps=gaps,
        raw_jd_word_count=len(jd.split()),
    )
