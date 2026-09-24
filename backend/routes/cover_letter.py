"""
routes/cover_letter.py

POST /api/generate-cover-letter
POST /api/download-cover-letter

Accepts the tailored resume payload plus JD/company/role context already
held in frontend App state, and returns a generated cover letter.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlmodel import Session, select
from db import get_session
from models import TailoredResumeRecord
from services.cover_letter_service import generate_cover_letter, CoverLetterResult
from services.build_cover_letter_pdf import build_cover_letter_pdf, cover_letter_filename
from routes.generate import get_owned_resume
from services.input_validation import StrictRequest, validate_identifier

router = APIRouter()
OUTPUTS_DIR = Path(__file__).resolve().parents[1] / "outputs"
OUTPUTS_DIR.mkdir(exist_ok=True)


class CoverLetterRequest(StrictRequest):
    tailored_resume: dict | None = None
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    job_description: str = Field(min_length=1, max_length=20_000)
    company: str = Field(default="", max_length=200)
    job_title: str = Field(default="", max_length=200)
    selected_keywords: list[str] = Field(default_factory=list, max_length=100)
    candidate_name: str = Field(default="", max_length=200)
    history_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("session_id", "history_id")
    @classmethod
    def validate_ids(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value is not None else value

    @model_validator(mode="after")
    def require_resume_source(self):
        if not self.session_id and not self.tailored_resume:
            raise ValueError("Provide a session_id or tailored_resume.")
        return self


class CoverLetterDownloadRequest(StrictRequest):
    letter: str = Field(min_length=1, max_length=20_000)
    candidate_name: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    job_title: str = Field(default="", max_length=200)
    history_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("history_id")
    @classmethod
    def validate_history_id(cls, value: str | None) -> str | None:
        return validate_identifier(value) if value is not None else value


def _cover_letter_display_name(request: CoverLetterDownloadRequest) -> str:
    return cover_letter_filename(
        request.candidate_name,
        request.company,
        request.job_title,
    )


def _get_owned_history_record(
    db: Session, history_id: str, user_id: str | None,
) -> TailoredResumeRecord:
    record = (
        db.exec(select(TailoredResumeRecord).where(
            TailoredResumeRecord.id == history_id,
            TailoredResumeRecord.user_id == user_id,
        )).first()
        if user_id is not None else db.get(TailoredResumeRecord, history_id)
    )
    if not record:
        raise HTTPException(status_code=404, detail="History record not found.")
    return record


def _store_cover_letter(db: Session, history_id: str | None, letter: str, user_id: str | None = None) -> None:
    if not history_id:
        return
    record = _get_owned_history_record(db, history_id, user_id)
    record.cover_letter = letter
    db.add(record)
    db.commit()


@router.post("/api/generate-cover-letter", response_model=CoverLetterResult)
def generate_cover_letter_route(
    request: CoverLetterRequest,
    db: Session = Depends(get_session),
    http_request: Request = None,
) -> CoverLetterResult:
    jd = request.job_description.strip()

    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")

    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    if request.history_id:
        _get_owned_history_record(db, request.history_id, http_request.state.user_id)

    stored_resume = (
        get_owned_resume(request.session_id, http_request.state.user_id)
        if request.session_id else None
    )
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
        _store_cover_letter(db, request.history_id, result.letter, http_request.state.user_id if http_request else None)
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
    http_request: Request = None,
) -> FileResponse:
    letter = request.letter.strip()
    if not letter:
        raise HTTPException(status_code=422, detail="cover letter cannot be empty.")

    _store_cover_letter(db, request.history_id, letter, http_request.state.user_id if http_request else None)
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
