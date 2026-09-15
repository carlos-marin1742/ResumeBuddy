"""PostgreSQL coverage for tailored-resume persistence through route helpers."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import select

from models import MasterResumeRecord, TailoredResumeRecord
from routes.cover_letter import _store_cover_letter
from routes.generate import GenerateRequest, _persist_generation
from routes.history import (
    delete_history_record,
    download_history_cover_letter,
    get_history_record,
    list_history,
    restore_session,
)


pytest_plugins = ("postgres_test_support",)

TECH_FIXTURE = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "tech_fixture.json"


def _resume() -> dict:
    return json.loads(TECH_FIXTURE.read_text(encoding="utf-8"))


def _persist(
    db,
    *,
    company: str = "Example Co",
    profile: str = "tech_fixture",
    resume: dict | None = None,
    ats_score: dict | None = None,
) -> TailoredResumeRecord:
    return _persist_generation(
        db,
        request=GenerateRequest(
            job_description="Build reliable APIs for a distributed platform.",
            selected_keywords=["FastAPI", "PostgreSQL", "JSONB"],
            resume_id=profile,
            company=f" {company} ",
            job_title=" Platform Engineer ",
        ),
        final_resume=resume if resume is not None else _resume(),
        ats_score=ats_score,
        pdf_path="outputs/example-platform-engineer.pdf",
    )


def test_generation_persistence_round_trips_every_intended_field(postgres_session):
    resume = _resume()
    record = _persist(
        postgres_session,
        resume=resume,
        ats_score={"overall_score": 91, "keyword_coverage": 0.75},
    )
    expected_created_at = datetime(2026, 9, 14, 7, 0, tzinfo=timezone(timedelta(hours=-5)))
    record.created_at = expected_created_at
    postgres_session.add(record)
    postgres_session.commit()
    postgres_session.expire_all()
    stored = postgres_session.get(TailoredResumeRecord, record.id)

    assert stored is not None
    assert stored.company == "Example Co"
    assert stored.job_title == "Platform Engineer"
    assert stored.profile == "tech_fixture"
    assert stored.job_description == "Build reliable APIs for a distributed platform."
    assert stored.selected_keywords == ["FastAPI", "PostgreSQL", "JSONB"]
    assert stored.tailored_resume == resume
    assert stored.ats_overall_score == 91
    assert stored.ats_keyword_coverage == 0.75
    assert stored.pdf_path == "outputs/example-platform-engineer.pdf"
    assert stored.cover_letter is None
    assert stored.created_at is not None
    assert stored.created_at.tzinfo is not None
    assert stored.created_at == expected_created_at


def test_generation_persistence_keeps_null_ats_scores(postgres_session):
    record = _persist(postgres_session)
    postgres_session.expire_all()
    stored = postgres_session.get(TailoredResumeRecord, record.id)

    assert stored is not None
    assert stored.ats_overall_score is None
    assert stored.ats_keyword_coverage is None


def test_history_lists_newest_first_and_filters_profile(postgres_session):
    oldest = _persist(postgres_session, company="Oldest", profile="tech_fixture")
    middle = _persist(postgres_session, company="Middle", profile="clinical_fixture")
    newest = _persist(postgres_session, company="Newest", profile="tech_fixture")
    oldest.created_at = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    middle.created_at = datetime(2026, 9, 14, 11, 0, tzinfo=timezone.utc)
    newest.created_at = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    postgres_session.add_all([oldest, middle, newest])
    postgres_session.commit()
    postgres_session.expire_all()

    all_history = list_history(db=postgres_session)
    tech_history = list_history(profile="tech_fixture", db=postgres_session)

    assert [item.id for item in all_history.records] == [newest.id, middle.id, oldest.id]
    assert [item.created_at for item in all_history.records] == [
        "2026-09-14T12:00:00+00:00",
        "2026-09-14T11:00:00+00:00",
        "2026-09-14T10:00:00+00:00",
    ]
    assert all_history.total == 3
    assert [item.id for item in tech_history.records] == [newest.id, oldest.id]
    assert tech_history.total == 2


def test_history_fetch_delete_and_restore_real_record(postgres_session, monkeypatch):
    resume = _resume()
    record = _persist(postgres_session, resume=resume)
    record.created_at = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    postgres_session.add(record)
    postgres_session.commit()
    postgres_session.expire_all()

    fetched = get_history_record(record.id, postgres_session)
    assert fetched.id == record.id
    assert fetched.created_at == "2026-09-14T12:00:00+00:00"
    assert fetched.selected_keywords == ["FastAPI", "PostgreSQL", "JSONB"]

    restored = {}
    monkeypatch.setattr("routes.history._store_resume", lambda session_id, value: restored.update({session_id: value}))
    result = restore_session(record.id, postgres_session)
    assert restored[result["session_id"]] == resume

    deleted = delete_history_record(record.id, postgres_session)
    assert deleted.deleted is True
    with pytest.raises(HTTPException, match="Record not found") as exc_info:
        get_history_record(record.id, postgres_session)
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException, match="Record not found") as exc_info:
        get_history_record("missing-record", postgres_session)
    assert exc_info.value.status_code == 404


def test_cover_letter_store_updates_existing_record_without_insert(postgres_session):
    record = _persist(postgres_session)
    _store_cover_letter(postgres_session, record.id, "Dear Hiring Manager,\n\nStored letter")
    postgres_session.expire_all()

    records = postgres_session.exec(select(TailoredResumeRecord)).all()
    assert len(records) == 1
    assert records[0].id == record.id
    assert records[0].cover_letter == "Dear Hiring Manager,\n\nStored letter"


def test_cover_letter_none_reads_back_and_download_routes_use_real_record(postgres_session, monkeypatch, tmp_path):
    no_letter = _persist(postgres_session)
    postgres_session.expire_all()
    assert postgres_session.get(TailoredResumeRecord, no_letter.id).cover_letter is None
    with pytest.raises(HTTPException, match="No cover letter stored") as exc_info:
        download_history_cover_letter(no_letter.id, postgres_session)
    assert exc_info.value.status_code == 404

    stored = _persist(postgres_session, company="Letter Co")
    _store_cover_letter(postgres_session, stored.id, "Dear Hiring Manager,\n\nStored letter")

    def write_pdf(letter, output_path):
        assert letter == "Dear Hiring Manager,\n\nStored letter"
        output_path.write_bytes(b"%PDF-1.4 test")

    monkeypatch.setattr("routes.history.OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr("routes.history.build_cover_letter_pdf", write_pdf)
    response = download_history_cover_letter(stored.id, postgres_session)

    assert response.media_type == "application/pdf"
    assert "Alex-Example-Letter-Co-Platform-Engineer-Cover-Letter.pdf" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"


def test_jsonb_payloads_round_trip_nested_unicode_and_quotes(postgres_session, postgres_persistence_engine):
    resume = _resume()
    resume["round_trip"] = {
        "nested": [{"city": "Montréal", "quote": "She said, \"ship it\"."}],
        "values": ["résumé", {"emoji": "✓"}],
    }
    record = _persist(postgres_session, resume=resume)
    postgres_session.expire_all()
    stored = postgres_session.get(TailoredResumeRecord, record.id)

    assert stored is not None
    assert stored.tailored_resume == resume
    assert json.dumps(stored.tailored_resume, ensure_ascii=False, sort_keys=True) == json.dumps(
        resume, ensure_ascii=False, sort_keys=True
    )

    with postgres_persistence_engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'tailored_resumes'
              AND column_name IN ('selected_keywords', 'tailored_resume')
            ORDER BY column_name
        """)).all()

    assert rows == [
        ("selected_keywords", "jsonb", "jsonb"),
        ("tailored_resume", "jsonb", "jsonb"),
    ]


def test_master_skill_dictionary_round_trips_as_jsonb_and_defaults_to_null(
    postgres_session, postgres_persistence_engine
):
    dictionary = {
        "terms": {"venipuncture": "clinical"},
        "profile_hash": "abc123",
        "seeded_at": "2026-09-15T00:00:00Z",
        "last_attempt_at": None,
        "last_attempt_failed": False,
    }
    with_dictionary = MasterResumeRecord(
        name="Dictionary", target_role="Technician", resume_data={}, skill_dictionary=dictionary
    )
    without_dictionary = MasterResumeRecord(
        name="No Dictionary", target_role="Technician", resume_data={}
    )
    postgres_session.add_all([with_dictionary, without_dictionary])
    postgres_session.commit()
    postgres_session.expire_all()

    assert postgres_session.get(MasterResumeRecord, with_dictionary.id).skill_dictionary == dictionary
    assert postgres_session.get(MasterResumeRecord, without_dictionary.id).skill_dictionary is None
    with postgres_persistence_engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'master_resumes'
              AND column_name = 'skill_dictionary'
        """)).all()
    assert rows == [("skill_dictionary", "jsonb", "jsonb")]
