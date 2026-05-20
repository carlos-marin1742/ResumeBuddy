"""
routes/generate.py

POST /api/generate-resume
    Accepts a job description + user-confirmed keywords, tailors the resume
    via Claude, builds a .docx (and optionally a .pdf), scores the result,
    and returns a JSON preview alongside download URL(s).

GET  /api/download/{filename}
    Serves a previously generated resume file from the outputs directory.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.claude_service import tailor_resume, score_resume, TailoredResume, ATSScoreResult
from services.resume_builder import build_docx  # you'll implement this next

router = APIRouter()

# ── Directory where generated files are written ──────────────────────────────
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

BASE_RESUME_PATH = Path(__file__).resolve().parents[1] / "data" / "base_resume.json"


# ── Request / Response Models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    job_description: str
    selected_keywords: list[str] = Field(default_factory=list)
    # Optional: override which summary variant to use.
    # If omitted, claude_service selects based on JD context.
    summary_variant: str | None = None


class BulletPreview(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str]


class ExperiencePreview(BaseModel):
    company: str
    title: str
    bullets: list[BulletPreview]


class ATSPreview(BaseModel):
    overall_score: int
    keyword_coverage: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]


class GenerateResponse(BaseModel):
    # Tailored content for ResumePreview.jsx
    summary: str
    experiences: list[ExperiencePreview]
    skills_to_highlight: list[str]

    # ATS scoring
    ats: ATSPreview

    # Download links
    docx_url: str
    pdf_url: str | None = None   # populated only if PDF conversion is enabled

    # Metadata
    generated_at: str
    resume_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_base_resume() -> dict:
    if not BASE_RESUME_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="base_resume.json not found.",
        )
    try:
        return json.loads(BASE_RESUME_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"base_resume.json is malformed: {exc}")


def _apply_summary_variant(base_resume: dict, variant_key: str | None) -> dict:
    """
    If the caller specified a summary variant (e.g. 'ai_focused'), swap
    base_resume['summary']['default'] so claude_service sees it as the
    canonical summary to rewrite from.
    """
    if not variant_key:
        return base_resume

    variants = base_resume.get("summary", {}).get("variants", {})
    if variant_key in variants:
        # Shallow-copy to avoid mutating the loaded dict
        resume = dict(base_resume)
        resume["summary"] = dict(resume["summary"])
        resume["summary"]["default"] = variants[variant_key]

    return base_resume


def _build_tailored_resume_dict(
    base_resume: dict,
    tailored: TailoredResume,
) -> dict:
    """
    Merge Claude's tailored content back into the full base_resume structure
    so resume_builder.py has everything it needs (contact, education,
    certifications, projects, etc.) alongside the tailored bullets/summary.
    """
    # Start from a copy of the full resume so static sections pass through
    output = dict(base_resume)

    # Override summary
    output["tailored_summary"] = tailored.summary

    # Override experience bullets
    tailored_exp_map = {
        exp.company: exp for exp in tailored.experiences
    }

    updated_experience = []
    for exp in base_resume.get("experience", []):
        tailored_exp = tailored_exp_map.get(exp["company"])
        if tailored_exp:
            updated_bullets = [
                {
                    "original": b.original,
                    "text": b.tailored,          # resume_builder reads "text"
                    "keywords_injected": b.keywords_injected,
                }
                for b in tailored_exp.tailored_bullets
            ]
            updated_experience.append({**exp, "bullets": updated_bullets})
        else:
            updated_experience.append(exp)

    output["experience"] = updated_experience
    output["skills_to_highlight"] = tailored.skills_to_highlight

    return output


def _unique_filename(prefix: str, extension: str) -> str:
    """Generate a timestamped unique filename, e.g. resume_20260518_a3f2.docx"""
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}_{short_id}.{extension}"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/generate-resume", response_model=GenerateResponse)
def generate_resume(request: GenerateRequest) -> GenerateResponse:

    # ── Validate input ────────────────────────────────────────────────────────
    jd = request.job_description.strip()
    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")
    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    # ── Load base resume ──────────────────────────────────────────────────────
    base_resume = _load_base_resume()
    base_resume = _apply_summary_variant(base_resume, request.summary_variant)

    # ── Step 1: Tailor resume content via Claude ──────────────────────────────
    try:
        tailored: TailoredResume = tailor_resume(
            base_resume=base_resume,
            job_description=jd,
            selected_keywords=request.selected_keywords,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Tailoring failed: {exc}")

    # ── Step 2: Merge tailored content into full resume dict ──────────────────
    full_tailored_dict = _build_tailored_resume_dict(base_resume, tailored)

    # ── Step 3: ATS scoring ───────────────────────────────────────────────────
    try:
        ats_result: ATSScoreResult = score_resume(
            tailored_resume=full_tailored_dict,
            job_description=jd,
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"ATS scoring failed: {exc}")

    # ── Step 4: Build .docx ───────────────────────────────────────────────────
    resume_id = uuid.uuid4().hex[:8]
    docx_filename = _unique_filename("resume", "docx")
    docx_path = OUTPUTS_DIR / docx_filename

    try:
        build_docx(resume_data=full_tailored_dict, output_path=docx_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document generation failed: {exc}")

    # ── Assemble response ─────────────────────────────────────────────────────
    experience_preview = [
        ExperiencePreview(
            company=exp.company,
            title=exp.title,
            bullets=[
                BulletPreview(
                    original=b.original,
                    tailored=b.tailored,
                    keywords_injected=b.keywords_injected,
                )
                for b in exp.tailored_bullets
            ],
        )
        for exp in tailored.experiences
    ]

    return GenerateResponse(
        summary=tailored.summary,
        experiences=experience_preview,
        skills_to_highlight=tailored.skills_to_highlight,
        ats=ATSPreview(
            overall_score=ats_result.overall_score,
            keyword_coverage=ats_result.keyword_coverage,
            matched_keywords=ats_result.matched_keywords,
            missing_keywords=ats_result.missing_keywords,
            suggestions=ats_result.suggestions,
        ),
        docx_url=f"/api/download/{docx_filename}",
        pdf_url=None,   # wire up after resume_builder supports PDF export
        generated_at=datetime.utcnow().isoformat() + "Z",
        resume_id=resume_id,
    )


@router.get("/api/download/{filename}")
def download_resume(filename: str) -> FileResponse:
    """
    Serve a generated resume file by name.
    Filename is validated to prevent path traversal.
    """
    # Security: reject any path separators or traversal attempts
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = OUTPUTS_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or has expired.")

    # Determine media type
    suffix = file_path.suffix.lower()
    media_type_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf":  "application/pdf",
    }
    media_type = media_type_map.get(suffix, "application/octet-stream")

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,                    # sets Content-Disposition header
        headers={"Cache-Control": "no-store"},
    )