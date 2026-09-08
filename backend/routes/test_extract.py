from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from models import MasterResumeRecord
from routes import extract as extract_module
from routes.extract import ExtractRequest, extract_keywords_route, flatten_resume_keywords
from routes.master_resumes import MasterResumeSaveRequest, create_master_resume
from services.claude_service import KeywordExtractionResult


def test_flatten_resume_keywords_supports_list_based_skills_and_tags():
    resume = {
        "skills": [
            {"category": "Languages", "items": ["Python", "SQL"]},
            {"category": "Empty", "items": []},
        ],
        "experience": [{"bullets": [{"text": "Built APIs", "tags": ["FastAPI"]}]}],
        "projects": [{"bullets": [{"text": "Deployed app", "tags": ["Docker"]}]}],
    }

    assert flatten_resume_keywords(resume) == {
        "python",
        "sql",
        "fastapi",
        "docker",
    }


def test_flatten_resume_keywords_supports_legacy_dict_skills_and_keywords():
    resume = {
        "skills": {"languages": ["Python"], "backend": ["FastAPI"]},
        "experience": [{"bullets": [{"keywords": ["REST"]}]}],
        "projects": [{"bullets": [{"keywords": ["Docker"]}]}],
    }

    assert flatten_resume_keywords(resume) == {
        "python",
        "fastapi",
        "rest",
        "docker",
    }


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_extract_keywords_route_matches_array_shaped_master_resume_skills(monkeypatch):
    monkeypatch.setattr(
        extract_module,
        "claude_extract_keywords",
        lambda jd: KeywordExtractionResult(
            hard_skills=["Python", "Microsoft Office (Word, Excel, Outlook)"],
            soft_skills=[],
            tools_and_technologies=[],
            job_titles=[],
            certifications=[],
            priority_keywords=[],
            raw_response="",
        ),
    )

    with _session() as db:
        record = MasterResumeRecord(
            name="Jamie Rivera",
            target_role="Operations Coordinator",
            resume_data={
                "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
                "targetRole": "Operations Coordinator",
                "summary": "",
                "skills": [
                    {
                        "key": "tools",
                        "category": "Tools",
                        "items": ["Microsoft Office (Word, Excel, Outlook)", "Python"],
                    },
                ],
                "experience": [],
                "education": [],
                "projects": [],
                "certifications": [],
            },
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        response = extract_keywords_route(
            ExtractRequest(job_description="Looking for Python and Excel skills.", master_resume_id=record.id),
            db,
        )

    by_keyword = {kw.keyword: kw.present_in_resume for kw in response.keywords}
    assert by_keyword["Python"] is True
    assert by_keyword["Microsoft Office (Word, Excel, Outlook)"] is True


def test_extract_keywords_route_matches_skill_in_user_named_builder_category(monkeypatch):
    monkeypatch.setattr(
        extract_module,
        "claude_extract_keywords",
        lambda jd: KeywordExtractionResult(
            hard_skills=["Venipuncture"],
            soft_skills=[],
            tools_and_technologies=[],
            job_titles=[],
            certifications=[],
            priority_keywords=[],
            raw_response="",
        ),
    )

    with _session() as db:
        record = MasterResumeRecord(
            name="Jamie Rivera",
            target_role="Phlebotomist",
            resume_data={
                "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
                "skills": [{
                    "key": "clinical_skills",
                    "category": "Clinical Skills",
                    "items": ["Venipuncture"],
                }],
            },
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        response = extract_keywords_route(
            ExtractRequest(
                job_description="Looking for venipuncture experience.",
                master_resume_id=record.id,
            ),
            db,
        )

    assert response.keywords[0].keyword == "Venipuncture"
    assert response.keywords[0].present_in_resume is True


def test_extract_keywords_route_matches_skill_saved_as_a_raw_comma_string(monkeypatch):
    """Regression: a master resume saved with items as a raw comma string
    (e.g. a legacy record, or a non-browser client posting directly) must
    have its skills split server-side so gap-matching finds them, instead of
    reporting a present skill as missing."""
    monkeypatch.setattr(
        extract_module,
        "claude_extract_keywords",
        lambda jd: KeywordExtractionResult(
            hard_skills=["React", "Vite"],
            soft_skills=[],
            tools_and_technologies=[],
            job_titles=[],
            certifications=[],
            priority_keywords=[],
            raw_response="",
        ),
    )

    save_request = MasterResumeSaveRequest.model_validate({
        "resume": {
            "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
            "targetRole": "Frontend Engineer",
            "summary": "",
            "experience": [],
            "education": [],
            "skills": [
                {"key": "tools", "category": "Tools", "items": "React, TypeScript, Vite"},
            ],
            "projects": [],
            "certifications": [],
        }
    })

    with _session() as db:
        created = create_master_resume(save_request, db)
        response = extract_keywords_route(
            ExtractRequest(
                job_description="Looking for React and Vite skills.",
                master_resume_id=created.id,
            ),
            db,
        )

    by_keyword = {kw.keyword: kw.present_in_resume for kw in response.keywords}
    assert by_keyword["React"] is True
    assert by_keyword["Vite"] is True
