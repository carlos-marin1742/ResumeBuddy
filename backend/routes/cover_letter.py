"""
routes/cover_letter.py

POST /api/generate-cover-letter
POST /api/download-cover-letter

Accepts the tailored resume payload plus JD/company/role context already
held in frontend App state, and returns a generated cover letter.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session
from db import get_session
from models import TailoredResumeRecord
from services.cover_letter_service import generate_cover_letter, CoverLetterResult
from services.build_cover_letter_pdf import build_cover_letter_pdf, cover_letter_filename
from routes.generate import RESUME_STORE

router = APIRouter()
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


class CoverLetterRequest(BaseModel):
    tailored_resume: dict | None = None
    session_id: str | None = None
    job_description: str
    company: str = ""
    job_title: str = ""
    selected_keywords: list[str] = Field(default_factory=list)
    candidate_name: str = Field(default="", max_length=200)
    history_id: str | None = None


class CoverLetterDownloadRequest(BaseModel):
    letter: str = Field(max_length=20_000)
    candidate_name: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    job_title: str = Field(default="", max_length=200)
    history_id: str | None = None


def _cover_letter_display_name(request: CoverLetterDownloadRequest) -> str:
    return cover_letter_filename(
        request.candidate_name,
        request.company,
        request.job_title,
    )


def _store_cover_letter(db: Session, history_id: str | None, letter: str) -> None:
    if not history_id:
        return
    record = db.get(TailoredResumeRecord, history_id)
    if not record:
        raise HTTPException(status_code=404, detail="History record not found.")
    record.cover_letter = letter
    db.add(record)
    db.commit()


@router.post("/api/generate-cover-letter", response_model=CoverLetterResult)
def generate_cover_letter_route(
    request: CoverLetterRequest,
    db: Session = Depends(get_session),
) -> CoverLetterResult:
    jd = request.job_description.strip()

    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")

    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    stored_resume = RESUME_STORE.get(request.session_id) if request.session_id else None
    resume = request.tailored_resume or stored_resume
    if not resume:
        raise HTTPException(status_code=422, detail="No resume data available. Re-generate your resume and try again.")

    candidate_name = request.candidate_name.strip()
    if not candidate_name:
        candidate_name = resume.get("contact", {}).get("name", "").strip()
    if not candidate_name and stored_resume:
        candidate_name = stored_resume.get("contact", {}).get("name", "").strip()
    applicant_contact = (
        stored_resume.get("contact", {})
        if stored_resume
        else resume.get("contact", {})
    )

    try:
        result = generate_cover_letter(
            tailored_resume=resume,
            job_description=jd,
            company=request.company.strip(),
            job_title=request.job_title.strip(),
            selected_keywords=request.selected_keywords,
            candidate_name=candidate_name,
            applicant_contact=applicant_contact,
        )
        _store_cover_letter(db, request.history_id, result.letter)
        return result
    except HTTPException:
        raise
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {e}")


@router.post("/api/download-cover-letter")
def download_cover_letter(
    request: CoverLetterDownloadRequest,
    db: Session = Depends(get_session),
) -> FileResponse:
    letter = request.letter.strip()
    if not letter:
        raise HTTPException(status_code=422, detail="cover letter cannot be empty.")

    _store_cover_letter(db, request.history_id, letter)
    output_path = OUTPUTS_DIR / f"cover_letter_{uuid.uuid4().hex}.pdf"
    try:
        build_cover_letter_pdf(letter, output_path)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Cover letter PDF generation failed: {exc}")

    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=_cover_letter_display_name(request),
        headers={"Cache-Control": "no-store"},
    )
