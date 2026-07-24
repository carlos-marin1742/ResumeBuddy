from sqlalchemy.pool import StaticPool
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session, SQLModel, create_engine

from models import MasterResumeRecord
from routes.master_resumes import (
    MasterResumeSaveRequest,
    create_master_resume,
    get_master_resume,
    update_master_resume,
)


def _request(name: str = "Jamie Rivera") -> MasterResumeSaveRequest:
    return MasterResumeSaveRequest.model_validate({
        "resume": {
            "contact": {
                "name": name,
                "email": "jamie@example.com",
                "phone": "",
                "location": "Chicago, IL",
                "linkedin": "",
                "portfolio": "",
            },
            "targetRole": "Product Manager",
            "summary": "Product leader.",
            "experience": [],
            "education": [],
            "skills": "Roadmaps",
            "projects": [],
            "certifications": [],
        }
    })


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_create_and_fetch_master_resume():
    with _session() as db:
        created = create_master_resume(_request(), db)
        fetched = get_master_resume(created.id, db)
        record = db.get(MasterResumeRecord, created.id)

    assert created.resume["contact"]["name"] == "Jamie Rivera"
    assert fetched.resume == created.resume
    assert record is not None
    assert record.target_role == "Product Manager"


def test_update_master_resume_preserves_record_identity():
    with _session() as db:
        created = create_master_resume(_request(), db)
        updated = update_master_resume(created.id, _request("Jamie R. Rivera"), db)

    assert updated.id == created.id
    assert updated.created_at == created.created_at
    assert updated.resume["contact"]["name"] == "Jamie R. Rivera"


def test_get_master_resume_rejects_unknown_id():
    with _session() as db:
        with pytest.raises(HTTPException) as exc_info:
            get_master_resume("missing", db)

    assert exc_info.value.status_code == 404


def test_master_resume_requires_valid_contact_information():
    payload = _request().model_dump()
    payload["resume"]["contact"]["email"] = "not-an-email"

    with pytest.raises(ValidationError, match="valid email"):
        MasterResumeSaveRequest.model_validate(payload)
