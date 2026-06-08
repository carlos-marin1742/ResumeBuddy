"""
routes/preview.py

POST /api/preview-html
    Accepts a session_id and spacing overrides, returns rendered HTML string.
    No Playwright — instant response for live preview.

POST /api/download-custom
    Accepts a session_id and spacing overrides, runs Playwright with exact
    values (bypasses auto-fit loop), returns PDF file.
"""

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from services.build_resume_pdf import _render_html, build_pdf_with_overrides
from routes.generate import RESUME_STORE

router = APIRouter()

OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


# ── Models ────────────────────────────────────────────────────────────────────

class SpacingOverrides(BaseModel):
    font_size: float = 8.5       # pt — range 7.5–10
    margin: float = 0.4          # inches — range 0.3–0.6
    entry_spacing: float = 5.0   # pt — range 0–15
    section_spacing: float = 6.0 # pt — range 0–15


class PreviewRequest(BaseModel):
    session_id: str
    overrides: SpacingOverrides = SpacingOverrides()


class DownloadRequest(BaseModel):
    session_id: str
    overrides: SpacingOverrides = SpacingOverrides()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/api/preview-html", response_class=HTMLResponse)
def preview_html(request: PreviewRequest) -> str:
    resume_data = RESUME_STORE.get(request.session_id)
    if not resume_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please regenerate your resume."
        )
    html = _render_html(resume_data, overrides=request.overrides.model_dump())
    return HTMLResponse(content=html)


@router.post("/api/download-custom")
def download_custom(request: DownloadRequest) -> FileResponse:
    resume_data = RESUME_STORE.get(request.session_id)
    if not resume_data:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please regenerate your resume."
        )

    filename = f"resume_custom_{uuid.uuid4().hex[:8]}.pdf"
    output_path = OUTPUTS_DIR / filename

    build_pdf_with_overrides(
        resume_data=resume_data,
        output_path=output_path,
        overrides=request.overrides.model_dump(),
    )

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )