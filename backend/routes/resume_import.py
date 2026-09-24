"""Routes for temporary, in-memory resume extraction."""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services.resume_parser import extract_docx_text, extract_pdf_text, parse_resume_text
from services.input_validation import validate_untrusted_value


router = APIRouter()
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
SUPPORTED_CONTENT_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}


class ResumeImportResponse(BaseModel):
    filename: str = Field(max_length=255)
    draft: dict
    warnings: list[str]


@router.post("/api/resumes/parse", response_model=ResumeImportResponse)
async def parse_resume(file: UploadFile = File(...)) -> ResumeImportResponse:
    """Parse a PDF or DOCX into a reviewable draft without storing the source."""
    filename = Path(file.filename or "").name
    if not filename or len(filename) > 255:
        raise HTTPException(status_code=422, detail="Upload filename is invalid.")
    try:
        validate_untrusted_value(filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")
    # Some legitimate clients (and direct server-side integrations) omit a
    # content type; when supplied, it must agree with the extension.  Magic
    # bytes and structural parsing below remain the authoritative checks.
    if file.content_type and file.content_type not in SUPPORTED_CONTENT_TYPES[extension]:
        raise HTTPException(status_code=415, detail="The upload content type does not match its extension.")

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
