"""Routes for temporary, in-memory resume extraction."""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from services.resume_parser import extract_docx_text, extract_pdf_text, parse_resume_text


router = APIRouter()
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


class ResumeImportResponse(BaseModel):
    filename: str
    draft: dict
    warnings: list[str]


@router.post("/api/resumes/parse", response_model=ResumeImportResponse)
async def parse_resume(file: UploadFile = File(...)) -> ResumeImportResponse:
    """Parse a PDF or DOCX into a reviewable draft without storing the source."""
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Resume files must be 5 MB or smaller.")
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded resume is empty.")

    if extension == ".pdf" and not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
    if extension == ".docx" and not content.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX.")

    try:
        text = extract_pdf_text(content) if extension == ".pdf" else extract_docx_text(content)
        draft, warnings = parse_resume_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ResumeImportResponse(filename=filename, draft=draft, warnings=warnings)
