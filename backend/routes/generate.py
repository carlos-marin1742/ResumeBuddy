"""
routes/generate.py

POST /api/generate-resume
    Accepts a job description + user-confirmed keywords, tailors the resume
    via Claude, builds a PDF, scores the result, and returns a JSON preview
    alongside a download URL.

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
from services.build_resume_pdf import build_pdf
import traceback

router = APIRouter()

# ── Directory where generated files are written ───────────────────────────────
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


# ── Request / Response Models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    profile: str = "base_resume"        # filename without .json e.g. base_resume, base_resume_clinical
    job_description: str
    selected_keywords: list[str] = Field(default_factory=list)
    resume_id: str = "base_resume"        # filename without .json e.g. base_resume, base_resume_clinical
    summary_variant: str | None = None


class BulletPreview(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str]


class ExperiencePreview(BaseModel):
    company: str
    title: str
    bullets: list[BulletPreview]


class ProjectPreview(BaseModel):
    name: str
    bullets: list[BulletPreview]


class ATSPreview(BaseModel):
    overall_score: int
    keyword_coverage: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]

class ExtractRequest(BaseModel):
    job_description: str
    resume_id: str = "base_resume"        # filename without .json e.g. base_resume, base_resume_clinical

class GenerateResponse(BaseModel):
    summary: str
    experiences: list[ExperiencePreview]
    projects: list[ProjectPreview]
    skills_to_highlight: list[str]
    skills_added: dict[str, list[str]]
    ats: ATSPreview
    pdf_url: str
    generated_at: str
    resume_id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_resume(resume_id: str) -> dict:
    """Load a resume JSON by filename (without .json extension)."""
    path = DATA_DIR / f"{resume_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Resume '{resume_id}' not found.")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Resume file is malformed: {exc}")


def _apply_summary_variant(base_resume: dict, variant_key: str | None) -> dict:
    if not variant_key:
        return base_resume
    variants = base_resume.get("summary", {}).get("variants", {})
    if variant_key in variants:
        resume = dict(base_resume)
        resume["summary"] = dict(resume["summary"])
        resume["summary"]["default"] = variants[variant_key]
    return base_resume


def _build_tailored_resume_dict(base_resume: dict, tailored: TailoredResume) -> dict:
    output = dict(base_resume)
    output["tailored_summary"] = tailored.summary

    # ── Merge tailored experience bullets ─────────────────────────────────────
    tailored_exp_map = {exp.company: exp for exp in tailored.experiences}
    updated_experience = []
    for exp in base_resume.get("experience", []):
        tailored_exp = tailored_exp_map.get(exp["company"])
        if tailored_exp:
            updated_bullets = [
                {
                    "original": b.original,
                    "text": b.tailored,
                    "keywords_injected": b.keywords_injected,
                }
                for b in tailored_exp.tailored_bullets
            ]
            updated_experience.append({**exp, "bullets": updated_bullets})
        else:
            updated_experience.append(exp)
    output["experience"] = updated_experience

    # ── Merge tailored project bullets ────────────────────────────────────────
    if tailored.projects:
        tailored_proj_map = {proj.name: proj for proj in tailored.projects}
        updated_projects = []
        for proj in base_resume.get("projects", []):
            tailored_proj = tailored_proj_map.get(proj["name"])
            if tailored_proj:
                updated_bullets = [
                    {
                        "original": b.original,
                        "text": b.tailored,
                        "keywords_injected": b.keywords_injected,
                    }
                    for b in tailored_proj.tailored_bullets
                ]
                updated_projects.append({**proj, "bullets": updated_bullets})
            else:
                updated_projects.append(proj)
        output["projects"] = updated_projects

    # ── Merge new skills suggested by Claude ──────────────────────────────────
    if tailored.skills_to_add:
        skills = {k: list(v) for k, v in output.get("skills", {}).items()}
        for category, new_skills in tailored.skills_to_add.items():
            if category in skills:
                existing_lower = {s.lower() for s in skills[category]}
                added_count = 0
                for skill in new_skills:
                    if added_count >= 3:  # max 3 new skills per category
                        break
                    if skill.lower() not in existing_lower:
                        skills[category].append(skill)
                        existing_lower.add(skill.lower())
                        added_count += 1
        output["skills"] = skills

    # ── Filter skills within categories to JD-relevant subset ─────────────────
    if tailored.skills_to_show:
        skills = {k: list(v) for k, v in output.get("skills", {}).items()}
        for category in list(skills.keys()):
            # If Claude didn't include this category in skills_to_show, drop it entirely
            if category not in tailored.skills_to_show:
                del skills[category]
        output["skills"] = skills

    # ── Filter skills_order to only show relevant categories ──────────────────
    if tailored.skills_to_show:
        current_order = output.get("ats_config", {}).get("skills_order", [])
        filtered_order = [cat for cat in current_order if cat in tailored.skills_to_show]
        if filtered_order:
            output["ats_config"] = {
                **output.get("ats_config", {}),
                "skills_order": filtered_order,
            }

    output["skills_to_highlight"] = tailored.skills_to_highlight
    return output


def _unique_filename(prefix: str, extension: str) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:6]
    return f"{prefix}_{ts}_{short_id}.{extension}"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/generate-resume", response_model=GenerateResponse)
def generate_resume(request: GenerateRequest) -> GenerateResponse:
    print(f"=== DEBUG: Incoming resume_id: '{request.resume_id}', profile: '{request.profile}' ===")

    jd = request.job_description.strip()
    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")
    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    # Step 1: Load base resume by filename
    resume_id_to_load = request.resume_id
    if resume_id_to_load == "base_resume" and request.profile != "base_resume":
        resume_id_to_load = request.profile
    base_resume = _load_resume(resume_id_to_load)
    base_resume = _apply_summary_variant(base_resume, request.summary_variant)

    # Step 2: Tailor via Claude
    try:
        tailored: TailoredResume = tailor_resume(
            base_resume=base_resume,
            job_description=jd,
            selected_keywords=request.selected_keywords,
        )
    except ValueError as exc:
        print("\n!!! CRITICAL ROUTE ERROR !!!")
        print(f"Error details: {exc}\n")
        raise HTTPException(status_code=502, detail=f"Tailoring failed: {exc}")

    # Step 3: Merge tailored content + new skills into full resume dict
    full_tailored_dict = _build_tailored_resume_dict(base_resume, tailored)

    # Step 4: ATS scoring
    try:
        ats_result: ATSScoreResult = score_resume(
            tailored_resume=full_tailored_dict,
            job_description=jd,
            selected_keywords = request.selected_keywords
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"ATS scoring failed: {exc}")

    # Step 5: Build PDF
    resume_id = uuid.uuid4().hex[:8]
    pdf_filename = _unique_filename("resume", "pdf")
    pdf_path = OUTPUTS_DIR / pdf_filename

    try:
        build_pdf(resume_data=full_tailored_dict, output_path=pdf_path)
    except Exception as exc:
        #raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")
        #implemented for testing
        print("!!! CRITICAL ROUTE ERROR !!!")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Tailoring failed: {exc}")
        #Delete after testing

    # Step 6: Assemble response
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

    project_preview = [
        ProjectPreview(
            name=proj.name,
            bullets=[
                BulletPreview(
                    original=b.original,
                    tailored=b.tailored,
                    keywords_injected=b.keywords_injected,
                )
                for b in proj.tailored_bullets
            ],
        )
        for proj in tailored.projects
    ]

    return GenerateResponse(
        summary=tailored.summary,
        experiences=experience_preview,
        projects=project_preview,
        skills_to_highlight=tailored.skills_to_highlight,
        skills_added=tailored.skills_to_add if tailored.skills_to_add else {}, # Safe fallback
        ats=ATSPreview(
            overall_score=ats_result.overall_score,
            keyword_coverage=ats_result.keyword_coverage,
            matched_keywords=ats_result.matched_keywords,
            missing_keywords=ats_result.missing_keywords,
            suggestions=ats_result.suggestions,
        ),
        pdf_url=f"/api/download/{pdf_filename}",
        generated_at=datetime.utcnow().isoformat() + "Z",
        resume_id=resume_id,
    )


@router.get("/api/download/{filename}")
def download_resume(filename: str) -> FileResponse:
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = OUTPUTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or has expired.")

    suffix = file_path.suffix.lower()
    media_type_map = {
        ".pdf":  "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    return FileResponse(
        path=file_path,
        media_type=media_type_map.get(suffix, "application/octet-stream"),
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )