"""
routes/cover_letter.py

POST /api/generate-cover-letter

Accepts the tailored resume payload plus JD/company/role context already
held in frontend App state, and returns a generated cover letter.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services.cover_letter_service import generate_cover_letter, CoverLetterResult
from routes.generate import RESUME_STORE

router = APIRouter()


class CoverLetterRequest(BaseModel):
    tailored_resume: dict | None = None
    session_id: str | None = None
    job_description: str
    company: str = ""
    job_title: str = ""
    selected_keywords: list[str] = Field(default_factory=list)
    candidate_name: str = Field(default="", max_length=200)


@router.post("/api/generate-cover-letter", response_model=CoverLetterResult)
def generate_cover_letter_route(request: CoverLetterRequest) -> CoverLetterResult:
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

    try:
        return generate_cover_letter(
            tailored_resume=resume,
            job_description=jd,
            company=request.company.strip(),
            job_title=request.job_title.strip(),
            selected_keywords=request.selected_keywords,
            candidate_name=candidate_name,
        )
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {e}")
