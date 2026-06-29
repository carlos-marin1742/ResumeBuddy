"""
routes/preview.py

POST /api/preview-html
    Accepts session_id + optional resume_data (for edits) + spacing overrides.
    Returns rendered HTML string with page boundary indicator.
    No Playwright — instant response.

POST /api/download-custom
    Accepts session_id + optional resume_data (for edits) + spacing overrides.
    Runs Playwright with exact values, returns PDF file.
    Page boundary indicator is NOT included in PDF output.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from services.build_resume_pdf import _render_html, build_pdf_with_overrides
from routes.generate import RESUME_STORE, _pdf_storage_name, _pdf_display_name

router = APIRouter()

OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# ── Models ────────────────────────────────────────────────────────────────────

class SpacingOverrides(BaseModel):
    font_size: float       = 8.5
    margin: float          = 0.4
    side_margin: float     = 0.5
    entry_spacing: float   = 5.0
    section_spacing: float = 6.0


class PreviewRequest(BaseModel):
    session_id: str
    overrides: SpacingOverrides = SpacingOverrides()
    resume_data: dict | None = None


class DownloadRequest(BaseModel):
    session_id: str
    overrides: SpacingOverrides = SpacingOverrides()
    resume_data: dict | None = None
    company: str = ""
    job_title: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_resume(session_id: str, resume_data_patch: dict | None) -> dict:
    """
    Get the resume dict for rendering.
    If resume_data_patch is provided, merge edited text over stored session data.
    """
    stored = RESUME_STORE.get(session_id)
    if not stored:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Please regenerate your resume."
        )

    if not resume_data_patch:
        return stored

    merged = dict(stored)

    if "tailored_summary" in resume_data_patch:
        merged["tailored_summary"] = resume_data_patch["tailored_summary"]

    if "experience" in resume_data_patch:
        patch_exp_map = {e["company"]: e for e in resume_data_patch["experience"]}
        updated_experience = []
        for exp in stored.get("experience", []):
            patch = patch_exp_map.get(exp["company"])
            if patch:
                updated_bullets = []
                for i, orig_bullet in enumerate(exp.get("bullets", [])):
                    if i < len(patch["bullets"]):
                        updated_bullets.append({
                            **orig_bullet,
                            "text": patch["bullets"][i]["text"],
                        })
                    else:
                        updated_bullets.append(orig_bullet)
                updated_experience.append({**exp, "bullets": updated_bullets})
            else:
                updated_experience.append(exp)
        merged["experience"] = updated_experience

    if "projects" in resume_data_patch:
        patch_proj_map = {p["name"]: p for p in resume_data_patch["projects"]}
        updated_projects = []
        for proj in stored.get("projects", []):
            patch = patch_proj_map.get(proj["name"])
            if patch:
                updated_bullets = []
                for i, orig_bullet in enumerate(proj.get("bullets", [])):
                    if i < len(patch["bullets"]):
                        updated_bullets.append({
                            **orig_bullet,
                            "text": patch["bullets"][i]["text"],
                        })
                    else:
                        updated_bullets.append(orig_bullet)
                updated_projects.append({**proj, "bullets": updated_bullets})
            else:
                updated_projects.append(proj)
        merged["projects"] = updated_projects

    return merged


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/preview-html", response_class=HTMLResponse)
def preview_html(request: PreviewRequest) -> str:
    resume = _resolve_resume(request.session_id, request.resume_data)
    # show_boundary=True — red page break line visible in iframe preview only
    html = _render_html(
        resume,
        overrides=request.overrides.model_dump(),
        show_boundary=True,
    )
    return HTMLResponse(content=html)


@router.post("/api/download-custom")
def download_custom(request: DownloadRequest) -> FileResponse:
    resume = _resolve_resume(request.session_id, request.resume_data)

    person_name = resume.get("contact", {}).get("name", "")
    storage_name = _pdf_storage_name(person_name, request.company, request.job_title)
    output_path  = OUTPUTS_DIR / storage_name
    display_name = _pdf_display_name(storage_name)

    # show_boundary is always False in build_pdf_with_overrides —
    # red line never appears in the downloaded PDF
    build_pdf_with_overrides(
        resume_data=resume,
        output_path=output_path,
        overrides=request.overrides.model_dump(),
    )

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=display_name,
        headers={"Cache-Control": "no-store"},
    )