"""Persistence routes for user-reviewed master resumes."""

from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session

from db import get_session
from models import MasterResumeRecord


router = APIRouter()
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(default="", max_length=50)
    location: str = Field(default="", max_length=120)
    linkedin: str = Field(default="", max_length=500)
    portfolio: str = Field(default="", max_length=500)

    @field_validator("name", "email", mode="before")
    @classmethod
    def strip_required_fields(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("Enter a valid email address.")
        return value

    @field_validator("linkedin", "portfolio")
    @classmethod
    def validate_optional_url(cls, value: str) -> str:
        if value and not value.lower().startswith(("http://", "https://")):
            raise ValueError("Links must start with http:// or https://.")
        return value


class ExperienceInput(BaseModel):
    company: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=120)
    startDate: str = Field(default="", max_length=7)
    endDate: str = Field(default="", max_length=7)
    highlights: str = Field(default="", max_length=10000)


class EducationInput(BaseModel):
    institution: str = Field(default="", max_length=250)
    degree: str = Field(default="", max_length=200)
    field: str = Field(default="", max_length=200)
    graduationDate: str = Field(default="", max_length=7)


class ProjectLinkInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    url: str = Field(min_length=8, max_length=500)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("Project links must start with http:// or https://.")
        return value


class ProjectInput(BaseModel):
    name: str = Field(default="", max_length=250)
    technologies: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=10000)
    links: list[ProjectLinkInput] = Field(default_factory=list, max_length=20)


class CertificationInput(BaseModel):
    name: str = Field(default="", max_length=250)
    issuer: str = Field(default="", max_length=250)
    date: str = Field(default="", max_length=7)


class SkillCategoryInput(BaseModel):
    category: str = Field(default="", max_length=100)
    items: str = Field(default="", max_length=5000)


class MasterResumeInput(BaseModel):
    contact: ContactInput
    targetRole: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=10000)
    experience: list[ExperienceInput] = Field(default_factory=list, max_length=50)
    education: list[EducationInput] = Field(default_factory=list, max_length=20)
    # Keep accepting the original string shape for previously saved drafts.
    skills: list[SkillCategoryInput] | str = Field(default_factory=list)
    projects: list[ProjectInput] = Field(default_factory=list, max_length=50)
    certifications: list[CertificationInput] = Field(default_factory=list, max_length=50)


class MasterResumeSaveRequest(BaseModel):
    resume: MasterResumeInput


class MasterResumeResponse(BaseModel):
    id: str
    created_at: str
    updated_at: str
    resume: dict


def _isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _to_response(record: MasterResumeRecord) -> MasterResumeResponse:
    return MasterResumeResponse(
        id=record.id,
        created_at=_isoformat(record.created_at),
        updated_at=_isoformat(record.updated_at),
        resume=record.resume_data,
    )


@router.post(
    "/api/master-resumes",
    response_model=MasterResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_master_resume(
    request: MasterResumeSaveRequest,
    db: Session = Depends(get_session),
) -> MasterResumeResponse:
    resume_data = request.resume.model_dump()
    record = MasterResumeRecord(
        name=request.resume.contact.name,
        target_role=request.resume.targetRole,
        resume_data=resume_data,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.put("/api/master-resumes/{record_id}", response_model=MasterResumeResponse)
def update_master_resume(
    record_id: str,
    request: MasterResumeSaveRequest,
    db: Session = Depends(get_session),
) -> MasterResumeResponse:
    record = db.get(MasterResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Master resume not found.")
    record.name = request.resume.contact.name
    record.target_role = request.resume.targetRole
    record.resume_data = request.resume.model_dump()
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.get("/api/master-resumes/{record_id}", response_model=MasterResumeResponse)
def get_master_resume(
    record_id: str,
    db: Session = Depends(get_session),
) -> MasterResumeResponse:
    record = db.get(MasterResumeRecord, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Master resume not found.")
    return _to_response(record)
