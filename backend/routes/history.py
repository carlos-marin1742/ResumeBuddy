"""
routes/history.py

GET    /api/history              — list all records (optional ?profile= filter)
GET    /api/history/{id}         — single record detail
DELETE /api/history/{id}         — remove a record
GET    /api/download-history/{id} — re-serve the cached PDF for a record
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models import TailoredResumeRecord
from routes.generate import _store_resume

router = APIRouter()


# ── Response Models ───────────────────────────────────────────────────────────

class HistoryItem(BaseModel):
    id: str
    created_at: str          # ISO string
    company: str
    job_title: str
    profile: str
    ats_overall_score: int | None
    ats_keyword_coverage: float | None
    selected_keywords: list[str]
    matched_keywords: list[str]
    extracted_keywords_count: int
    job_description: str
    pdf_path: str | None


class HistoryListResponse(BaseModel):
    records: list[HistoryItem]
    total: int


class DeleteResponse(BaseModel):
    deleted: bool
    id: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_item(record: TailoredResumeRecord) -> HistoryItem:
    tailored = record.tailored_resume or {}
    return HistoryItem(
        id=record.id,
        created_at=record.created_at.isoformat(),
        company=record.company,
        job_title=record.job_title,
        profile=record.profile,
        ats_overall_score=record.ats_overall_score,
        ats_keyword_coverage=record.ats_keyword_coverage,
        selected_keywords=record.selected_keywords or [],
        matched_keywords=tailored.get("_ats_matched_keywords", []),
        extracted_keywords_count=tailored.get("_extracted_keywords_count", 0),
        job_description=record.job_description or "",
        pdf_path=record.pdf_path,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/history", response_model=HistoryListResponse)
def list_history(
    profile: str | None = None,
    db: Session = Depends(get_session),
) -> HistoryListResponse:
    """
    Return all records, newest first.
    Optionally filter by ?profile=base_resume (or base_resume_cl, base_resume_ad).
    """
    query = select(TailoredResumeRecord).order_by(TailoredResumeRecord.created_at.desc())
    records = db.exec(query).all()

    if profile:
        records = [r for r in records if r.profile == profile]

    return HistoryListResponse(
        records=[_to_item(r) for r in records],
        total=len(records),
    )


@router.get("/api/history/{record_id}", response_model=HistoryItem)
def get_history_record(
    record_id: str,
    db: Session = Depends(get_session),
) -> HistoryItem:
    record = db.get(TailoredResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    return _to_item(record)


@router.delete("/api/history/{record_id}", response_model=DeleteResponse)
def delete_history_record(
    record_id: str,
    db: Session = Depends(get_session),
) -> DeleteResponse:
    record = db.get(TailoredResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    db.delete(record)
    db.commit()
    return DeleteResponse(deleted=True, id=record_id)


@router.post("/api/history/{record_id}/restore")
def restore_session(
    record_id: str,
    db: Session = Depends(get_session),
) -> dict:
    """
    Load a history record's tailored_resume into RESUME_STORE and return a
    fresh session_id. Lets the frontend reuse PDFPreview for history records.
    """
    record = db.get(TailoredResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    if not record.tailored_resume:
        raise HTTPException(status_code=422, detail="No resume data stored for this record.")
    session_id = uuid.uuid4().hex
    _store_resume(session_id, record.tailored_resume)
    return {"session_id": session_id}


@router.get("/api/download-history/{record_id}")
def download_history_pdf(
    record_id: str,
    db: Session = Depends(get_session),
) -> FileResponse:
    """
    Re-serve the cached PDF for a history record.
    Returns 404 if the record doesn't exist or the PDF file has been cleaned up.
    """
    record = db.get(TailoredResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found.")
    if not record.pdf_path:
        raise HTTPException(status_code=404, detail="No PDF cached for this record.")

    pdf_path = Path(record.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(
            status_code=410,
            detail="PDF has been cleaned up from disk. Re-generate to get a fresh copy.",
        )

    person_name  = record.tailored_resume.get("contact", {}).get("name", "") if record.tailored_resume else ""
    display_name = f"{person_name}-{record.company}-{record.job_title} Resume.pdf" if person_name else f"{record.company}-{record.job_title} Resume.pdf"

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=display_name,
        headers={"Cache-Control": "no-store"},
    )