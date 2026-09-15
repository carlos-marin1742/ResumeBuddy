from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from models import MasterResumeRecord
from routes.master_resumes import (
    MasterResumeSaveRequest,
    SkillCategoryInput,
    create_master_resume,
    delete_master_resume,
    get_master_resume,
    list_master_resumes,
    seed_master_resume_dictionary,
    update_master_resume,
)
from services.master_resume_adapter import master_resume_to_profile
from services.skill_dictionary_service import profile_hash_for_resume

pytest_plugins = ("postgres_test_support",)


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
            "targetJobTitle": "Software Engineer",
            "summary": "Product leader.",
            "experience": [],
            "education": [],
            "skills": [
                {"key": "product", "category": "Product", "items": ["Roadmaps"]},
            ],
            "projects": [],
            "certifications": [],
        }
    })


def test_create_and_fetch_master_resume(postgres_session):
    db = postgres_session
    created = create_master_resume(_request(), db)
    record = db.get(MasterResumeRecord, created.id)

    assert record is not None
    record.created_at = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    record.updated_at = datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc)
    db.add(record)
    db.commit()
    db.expire_all()
    fetched = get_master_resume(created.id, db)

    assert created.resume["contact"]["name"] == "Jamie Rivera"
    assert fetched.resume == created.resume
    assert record.target_role == "Product Manager"
    assert record.created_at.tzinfo is not None
    assert record.updated_at.tzinfo is not None
    assert fetched.created_at == "2026-09-14T12:00:00+00:00"
    assert fetched.updated_at == "2026-09-14T13:00:00+00:00"
    assert created.resume["skills"] == [
        {"key": "product", "category": "Product", "items": ["Roadmaps"]},
    ]
    assert created.resume["targetJobTitle"] == "Software Engineer"


def test_master_resume_accepts_missing_target_job_title_for_existing_records():
    payload = _request().model_dump()
    del payload["resume"]["targetJobTitle"]

    request = MasterResumeSaveRequest.model_validate(payload)

    assert request.resume.targetJobTitle == ""


def test_list_master_resumes_uses_saved_title_for_profile_selection(postgres_session):
    db = postgres_session
    created = create_master_resume(_request(), db)
    record = db.get(MasterResumeRecord, created.id)
    assert record is not None
    record.updated_at = datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc)
    db.add(record)
    db.commit()
    db.expire_all()
    result = list_master_resumes(db)

    assert len(result.resumes) == 1
    assert result.resumes[0].id == created.id
    assert result.resumes[0].title == "Product Manager"
    assert result.resumes[0].name == "Jamie Rivera"
    assert result.resumes[0].updated_at == "2026-09-14T13:00:00+00:00"


def test_delete_master_resume_removes_record(postgres_session):
    db = postgres_session
    created = create_master_resume(_request(), db)
    result = delete_master_resume(created.id, db)
    remaining = list_master_resumes(db)

    assert result.deleted is True
    assert result.id == created.id
    assert remaining.resumes == []


def test_master_resume_accepts_legacy_plain_text_skills():
    payload = _request().model_dump()
    payload["resume"]["skills"] = "Roadmaps"

    request = MasterResumeSaveRequest.model_validate(payload)

    assert request.resume.skills == "Roadmaps"


def test_skill_group_accepts_array_items():
    payload = _request().model_dump()
    payload["resume"]["skills"] = [
        {"key": "product", "category": "Product", "items": ["Roadmaps", "Discovery"]},
    ]

    request = MasterResumeSaveRequest.model_validate(payload)

    assert request.resume.skills[0].items == ["Roadmaps", "Discovery"]


def test_skill_group_accepts_string_items_without_422():
    payload = _request().model_dump()
    payload["resume"]["skills"] = [
        {"key": "product", "category": "Product", "items": "Roadmaps"},
    ]

    request = MasterResumeSaveRequest.model_validate(payload)

    assert request.resume.skills[0].items == ["Roadmaps"]


def test_skill_category_validator_splits_a_comma_string_into_separate_items():
    group = SkillCategoryInput.model_validate({
        "category": "Frontend",
        "items": "React, TypeScript, Vite",
    })

    assert group.items == ["React", "TypeScript", "Vite"]


def test_skill_category_validator_keeps_a_parenthesised_comma_as_one_item():
    group = SkillCategoryInput.model_validate({
        "category": "Tools",
        "items": "Microsoft Office (Word, Excel, Outlook), Slack",
    })

    assert group.items == ["Microsoft Office (Word, Excel, Outlook)", "Slack"]


def test_skill_category_validator_splits_newline_value_on_lines_keeping_commas_literal():
    group = SkillCategoryInput.model_validate({
        "category": "Clinical",
        "items": "Phlebotomy, adult and pediatric\nVenipuncture",
    })

    assert group.items == ["Phlebotomy, adult and pediatric", "Venipuncture"]


def test_skill_category_validator_passes_an_array_payload_through_unchanged():
    group = SkillCategoryInput.model_validate({
        "category": "Frontend",
        "items": ["React", "TypeScript"],
    })

    assert group.items == ["React", "TypeScript"]


def test_skill_category_validator_yields_empty_list_for_blank_string():
    empty = SkillCategoryInput.model_validate({"category": "Frontend", "items": ""})
    whitespace = SkillCategoryInput.model_validate({"category": "Frontend", "items": ", "})

    assert empty.items == []
    assert whitespace.items == []


def test_master_resume_round_trips_a_raw_comma_string_into_separate_items(postgres_session):
    payload = _request().model_dump()
    payload["resume"]["skills"] = [
        {"key": "tools", "category": "Tools", "items": "React, TypeScript, Vite"},
    ]
    request = MasterResumeSaveRequest.model_validate(payload)

    db = postgres_session
    created = create_master_resume(request, db)
    fetched = get_master_resume(created.id, db)

    assert fetched.resume["skills"] == [
        {"key": "tools", "category": "Tools", "items": ["React", "TypeScript", "Vite"]},
    ]


def test_create_master_resume_persists_string_items_as_array(postgres_session):
    payload = _request().model_dump()
    payload["resume"]["skills"] = [
        {"key": "product", "category": "Product", "items": "Roadmaps"},
    ]
    request = MasterResumeSaveRequest.model_validate(payload)

    db = postgres_session
    created = create_master_resume(request, db)

    assert created.resume["skills"] == [
        {"key": "product", "category": "Product", "items": ["Roadmaps"]},
    ]


def test_master_resume_round_trips_key_and_array_items_through_put_and_get(postgres_session):
    db = postgres_session
    created = create_master_resume(_request(), db)
    update_request = _request("Jamie Rivera")
    update_request.resume.skills[0].items = ["Roadmaps", "Prioritization"]
    updated = update_master_resume(created.id, update_request, db)
    fetched = get_master_resume(created.id, db)

    assert updated.resume["skills"] == [
        {"key": "product", "category": "Product", "items": ["Roadmaps", "Prioritization"]},
    ]
    assert fetched.resume == updated.resume


def test_update_master_resume_preserves_record_identity(postgres_session):
    db = postgres_session
    created = create_master_resume(_request(), db)
    updated = update_master_resume(created.id, _request("Jamie R. Rivera"), db)

    assert updated.id == created.id
    assert updated.created_at == created.created_at
    assert updated.resume["contact"]["name"] == "Jamie R. Rivera"


def test_get_master_resume_rejects_unknown_id(postgres_session):
    with pytest.raises(HTTPException) as exc_info:
        get_master_resume("missing", postgres_session)

    assert exc_info.value.status_code == 404


def test_master_resume_requires_valid_contact_information():
    payload = _request().model_dump()
    payload["resume"]["contact"]["email"] = "not-an-email"

    with pytest.raises(ValidationError, match="valid email"):
        MasterResumeSaveRequest.model_validate(payload)


def test_master_resume_rejects_html_breakout_in_email():
    payload = _request().model_dump()
    payload["resume"]["contact"]["email"] = 'x"><script>alert(1)</script>@evil.test'

    with pytest.raises(ValidationError, match="valid email"):
        MasterResumeSaveRequest.model_validate(payload)


def test_seed_endpoint_unknown_id_404s(postgres_session):
    with pytest.raises(HTTPException) as exc_info:
        seed_master_resume_dictionary("missing", postgres_session)
    assert exc_info.value.status_code == 404


def test_seed_endpoint_skips_current_dictionary_without_calling_model(postgres_session, monkeypatch):
    created = create_master_resume(_request(), postgres_session)
    record = postgres_session.get(MasterResumeRecord, created.id)
    record.skill_dictionary = {
        "terms": {"roadmap": "product"},
        "profile_hash": profile_hash_for_resume(master_resume_to_profile(record.resume_data)),
        "seeded_at": "2026-09-15T00:00:00+00:00", "last_attempt_at": "2026-09-15T00:00:00+00:00",
        "last_attempt_failed": False,
    }
    postgres_session.commit()
    called = False
    def fail(*_):
        nonlocal called
        called = True
        raise AssertionError("model should not be called")
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", fail)

    assert seed_master_resume_dictionary(created.id, postgres_session).status == "skipped-unchanged"
    assert called is False


def test_seed_endpoint_backoff_and_failure_preserves_jsonb(postgres_session, monkeypatch):
    created = create_master_resume(_request(), postgres_session)
    record = postgres_session.get(MasterResumeRecord, created.id)
    record.skill_dictionary = {
        "terms": {"roadmap": "product"}, "profile_hash": "old", "seeded_at": "old",
        "last_attempt_at": datetime.now(timezone.utc).isoformat(), "last_attempt_failed": True,
    }
    postgres_session.commit()
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: (_ for _ in ()).throw(AssertionError()))
    assert seed_master_resume_dictionary(created.id, postgres_session).status == "skipped-backoff"

    record.skill_dictionary = {
        **record.skill_dictionary,
        "last_attempt_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }
    postgres_session.add(record); postgres_session.commit()
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: "bad json")
    assert seed_master_resume_dictionary(created.id, postgres_session).status == "failed"
    postgres_session.expire_all()
    stored = postgres_session.get(MasterResumeRecord, created.id).skill_dictionary
    assert stored["terms"] == {"roadmap": "product"}
    assert stored["last_attempt_failed"] is True


def test_seed_endpoint_success_persists_jsonb(postgres_session, monkeypatch):
    created = create_master_resume(_request(), postgres_session)
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: '{"terms":[{"term":"backlog","category":"product"}]}')
    response = seed_master_resume_dictionary(created.id, postgres_session)
    postgres_session.expire_all()
    assert response.status == "seeded"
    assert postgres_session.get(MasterResumeRecord, created.id).skill_dictionary["terms"] == {"backlog": "product"}
