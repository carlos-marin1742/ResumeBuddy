"""
routes/cover_letter.py

POST /api/generate-cover-letter

Accepts the tailored resume payload plus JD/company/role context already
held in frontend App state, and returns a generated cover letter.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.cover_letter_service import generate_cover_letter, CoverLetterResult

router = APIRouter()


class CoverLetterRequest(BaseModel):
    tailored_resume: dict          # TailoredResume shape from /api/generate-resume
    job_description: str
    company: str = ""
    job_title: str = ""
    selected_keywords: list[str] = []


@router.post("/api/generate-cover-letter", response_model=CoverLetterResult)
def generate_cover_letter_route(request: CoverLetterRequest) -> CoverLetterResult:
    jd = request.job_description.strip()

    if not jd:
        raise HTTPException(status_code=422, detail="job_description cannot be empty.")

    if len(jd) > 20_000:
        raise HTTPException(status_code=422, detail="job_description exceeds 20,000 character limit.")

    try:
        return generate_cover_letter(
            tailored_resume=request.tailored_resume,
            job_description=jd,
            company=request.company.strip(),
            job_title=request.job_title.strip(),
            selected_keywords=request.selected_keywords,
        )
    except EnvironmentError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cover letter generation failed: {e}")