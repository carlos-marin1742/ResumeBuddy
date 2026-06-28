"""
routes/regenerate.py

POST /api/regenerate-section
  Regenerates a specific section (summary, experience bullets, or project bullets)
  with optional user feedback, then re-scores the resume.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from routes.generate import RESUME_STORE
from services.claude_service import (
    ATSScoreResult,
    TailoredBullet,
    regenerate_bullets,
    regenerate_summary,
    score_resume,
)

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────────────────

class RegenerateRequest(BaseModel):
    session_id: str
    section: str                    # "summary" | "experience" | "project"
    target: str | None = None       # company name / project name; None for summary
    feedback: str = ""
    job_description: str
    selected_keywords: list[str] = []


class ATSPreview(BaseModel):
    overall_score: int
    keyword_coverage: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]


class BulletPreview(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str]


class RegenerateResponse(BaseModel):
    section: str
    summary: str | None = None
    bullets: list[BulletPreview] | None = None
    ats: ATSPreview


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post("/api/regenerate-section", response_model=RegenerateResponse)
def regenerate_section(request: RegenerateRequest) -> RegenerateResponse:
    stored = RESUME_STORE.get(request.session_id)
    if not stored:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please regenerate your resume.",
        )

    new_summary: str | None = None
    new_bullets: list[BulletPreview] | None = None

    # ── Summary ───────────────────────────────────────────────────────────────
    if request.section == "summary":
        raw_summary = stored.get("summary", "")
        original_summary = (
            raw_summary.get("default", "") if isinstance(raw_summary, dict) else raw_summary
        )
        current_tailored = stored.get("tailored_summary", "")

        new_summary = regenerate_summary(
            original_summary=original_summary,
            current_tailored_summary=current_tailored,
            job_description=request.job_description,
            selected_keywords=request.selected_keywords,
            user_feedback=request.feedback,
        )
        stored["tailored_summary"] = new_summary
        RESUME_STORE[request.session_id] = stored

    # ── Experience bullets ────────────────────────────────────────────────────
    elif request.section == "experience":
        if not request.target:
            raise HTTPException(
                status_code=422, detail="target (company name) is required for experience regeneration."
            )

        exp = next(
            (e for e in stored.get("experience", []) if e["company"] == request.target), None
        )
        if not exp:
            raise HTTPException(
                status_code=404, detail=f"Experience '{request.target}' not found in session."
            )

        original_bullets = [b.get("original", b.get("text", "")) for b in exp.get("bullets", [])]
        current_tailored = [b.get("text", "") for b in exp.get("bullets", [])]

        regen: list[TailoredBullet] = regenerate_bullets(
            section_type="experience",
            target_name=request.target,
            target_title=exp.get("title", ""),
            original_bullets=original_bullets,
            current_tailored_bullets=current_tailored,
            job_description=request.job_description,
            selected_keywords=request.selected_keywords,
            user_feedback=request.feedback,
        )

        for e in stored["experience"]:
            if e["company"] == request.target:
                e["bullets"] = [
                    {"original": b.original, "text": b.tailored, "keywords_injected": b.keywords_injected}
                    for b in regen
                ]
                break
        RESUME_STORE[request.session_id] = stored

        new_bullets = [
            BulletPreview(original=b.original, tailored=b.tailored, keywords_injected=b.keywords_injected)
            for b in regen
        ]

    # ── Project bullets ───────────────────────────────────────────────────────
    elif request.section == "project":
        if not request.target:
            raise HTTPException(
                status_code=422, detail="target (project name) is required for project regeneration."
            )

        proj = next(
            (p for p in stored.get("projects", []) if p["name"] == request.target), None
        )
        if not proj:
            raise HTTPException(
                status_code=404, detail=f"Project '{request.target}' not found in session."
            )

        original_bullets = [b.get("original", b.get("text", "")) for b in proj.get("bullets", [])]
        current_tailored = [b.get("text", "") for b in proj.get("bullets", [])]

        regen = regenerate_bullets(
            section_type="project",
            target_name=request.target,
            target_title="",
            original_bullets=original_bullets,
            current_tailored_bullets=current_tailored,
            job_description=request.job_description,
            selected_keywords=request.selected_keywords,
            user_feedback=request.feedback,
        )

        for p in stored["projects"]:
            if p["name"] == request.target:
                p["bullets"] = [
                    {"original": b.original, "text": b.tailored, "keywords_injected": b.keywords_injected}
                    for b in regen
                ]
                break
        RESUME_STORE[request.session_id] = stored

        new_bullets = [
            BulletPreview(original=b.original, tailored=b.tailored, keywords_injected=b.keywords_injected)
            for b in regen
        ]

    else:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid section '{request.section}'. Must be 'summary', 'experience', or 'project'.",
        )

    # ── Re-score ──────────────────────────────────────────────────────────────
    ats_result: ATSScoreResult = score_resume(
        tailored_resume=stored,
        job_description=request.job_description,
        selected_keywords=request.selected_keywords,
    )

    return RegenerateResponse(
        section=request.section,
        summary=new_summary,
        bullets=new_bullets,
        ats=ATSPreview(
            overall_score=ats_result.overall_score,
            keyword_coverage=ats_result.keyword_coverage,
            matched_keywords=ats_result.matched_keywords,
            missing_keywords=ats_result.missing_keywords,
            suggestions=ats_result.suggestions,
        ),
    )
