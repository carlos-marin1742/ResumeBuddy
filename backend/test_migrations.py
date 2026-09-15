"""PostgreSQL Alembic integration tests using disposable databases."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.dialects import postgresql

from models import MasterResumeRecord, TailoredResumeRecord
from postgres_test_support import alembic_config, disposable_postgres_database


BACKEND_DIR = Path(__file__).resolve().parent
INITIAL_REVISION = "f8ed9f77d689"
HEAD_REVISION = "d4a1b2c3e4f5"
TECH_FIXTURE = BACKEND_DIR / "data" / "fixtures" / "tech_fixture.json"


def _normalized_type_name(type_name: str) -> str:
    return (
        type_name.upper()
        .replace(" WITHOUT TIME ZONE", "")
        .replace("DOUBLE PRECISION", "FLOAT")
    )


def _expected_model_column_types() -> dict[str, dict[str, str]]:
    dialect = postgresql.dialect()
    return {
        table.name: {
            column.name: _normalized_type_name(column.type.compile(dialect=dialect))
            for column in table.columns
        }
        for table in (MasterResumeRecord.__table__, TailoredResumeRecord.__table__)
    }


EXPECTED_MODEL_COLUMN_TYPES = _expected_model_column_types()


def _assert_schema_matches_models(database_url: URL) -> None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        dialect = postgresql.dialect()
        assert {"tailored_resumes", "master_resumes", "alembic_version"} <= set(
            inspector.get_table_names()
        )

        for table_name, expected_types in EXPECTED_MODEL_COLUMN_TYPES.items():
            actual_types = {
                column["name"]: _normalized_type_name(column["type"].compile(dialect=dialect))
                for column in inspector.get_columns(table_name)
            }
            assert set(expected_types) <= set(actual_types)
            assert {
                name: actual_types[name] for name in expected_types
            } == expected_types
    finally:
        engine.dispose()


def _payload_column_types(database_url: URL) -> dict[str, str]:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        master_types = {
            column["name"]: column["type"]
            for column in inspector.get_columns("master_resumes")
        }
        tailored_types = {
            column["name"]: column["type"]
            for column in inspector.get_columns("tailored_resumes")
        }
        return {
            "resume_data": _normalized_type_name(str(master_types["resume_data"])),
            "selected_keywords": _normalized_type_name(
                str(tailored_types["selected_keywords"])
            ),
            "tailored_resume": _normalized_type_name(str(tailored_types["tailored_resume"])),
        }
    finally:
        engine.dispose()


@pytest.fixture
def migration_database() -> URL:
    with disposable_postgres_database() as database_url:
        yield database_url


def test_revision_chain_applies_from_empty_database(migration_database: URL):
    command.upgrade(alembic_config(migration_database), "head")

    _assert_schema_matches_models(migration_database)
    engine = create_engine(migration_database)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD_REVISION
    finally:
        engine.dispose()


def test_jsonb_conversion_preserves_existing_payloads(migration_database: URL):
    command.upgrade(alembic_config(migration_database), INITIAL_REVISION)
    assert _payload_column_types(migration_database) == {
        "resume_data": "JSON",
        "selected_keywords": "JSON",
        "tailored_resume": "JSON",
    }

    resume_data = json.loads(TECH_FIXTURE.read_text())
    tailored_resume = {
        **resume_data,
        "tailored_summary": "Platform engineer focused on PostgreSQL migrations.",
        "_ats_matched_keywords": ["Python", "FastAPI", "PostgreSQL"],
    }
    selected_keywords = ["Python", "FastAPI", "PostgreSQL"]
    created_at = datetime(2026, 9, 14, 12, 0)
    master_id = uuid4().hex
    tailored_id = uuid4().hex

    engine = create_engine(migration_database)
    try:
        metadata = MetaData()
        master_resumes = Table("master_resumes", metadata, autoload_with=engine)
        tailored_resumes = Table("tailored_resumes", metadata, autoload_with=engine)
        with engine.begin() as connection:
            connection.execute(
                master_resumes.insert(),
                {
                    "id": master_id,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "name": "Alex Example",
                    "target_role": "Platform Engineer",
                    "resume_data": resume_data,
                },
            )
            connection.execute(
                tailored_resumes.insert(),
                {
                    "id": tailored_id,
                    "created_at": created_at,
                    "company": "Example Systems",
                    "job_title": "Platform Engineer",
                    "profile": "tech_fixture",
                    "job_description": "Build reliable PostgreSQL-backed application services.",
                    "selected_keywords": selected_keywords,
                    "tailored_resume": tailored_resume,
                    "cover_letter": "Dear Hiring Manager,",
                    "ats_overall_score": 91,
                    "ats_keyword_coverage": 0.75,
                    "pdf_path": "outputs/example.pdf",
                },
            )
    finally:
        engine.dispose()

    # A bare timestamp-to-timestamptz ALTER uses the session TimeZone. Put the
    # head migration and readback in a non-UTC session to prove the revision
    # explicitly preserves legacy UTC instants.
    non_utc_database = make_url(
        f"{migration_database.render_as_string(hide_password=False)}"
        "?options=-c+TimeZone=America/Chicago"
    )
    command.upgrade(alembic_config(non_utc_database), "head")
    _assert_schema_matches_models(non_utc_database)
    assert _payload_column_types(non_utc_database) == {
        "resume_data": "JSONB",
        "selected_keywords": "JSONB",
        "tailored_resume": "JSONB",
    }

    engine = create_engine(non_utc_database)
    try:
        metadata = MetaData()
        master_resumes = Table("master_resumes", metadata, autoload_with=engine)
        tailored_resumes = Table("tailored_resumes", metadata, autoload_with=engine)
        with engine.connect() as connection:
            actual_resume_data, actual_master_created_at, actual_master_updated_at = connection.execute(
                select(master_resumes.c.resume_data, master_resumes.c.created_at, master_resumes.c.updated_at).where(
                    master_resumes.c.id == master_id
                )
            ).one()
            actual_selected_keywords, actual_tailored_resume, actual_tailored_created_at = connection.execute(
                select(tailored_resumes.c.selected_keywords, tailored_resumes.c.tailored_resume, tailored_resumes.c.created_at).where(
                    tailored_resumes.c.id == tailored_id
                )
            ).one()
    finally:
        engine.dispose()

    assert actual_resume_data == resume_data
    assert actual_selected_keywords == selected_keywords
    assert actual_tailored_resume == tailored_resume
    assert actual_master_created_at == created_at.replace(tzinfo=timezone.utc)
    assert actual_master_updated_at == created_at.replace(tzinfo=timezone.utc)
    assert actual_tailored_created_at == created_at.replace(tzinfo=timezone.utc)


def test_skill_dictionary_migration_leaves_existing_rows_null(migration_database: URL):
    command.upgrade(alembic_config(migration_database), "c3d8a1e6b4f2")
    engine = create_engine(migration_database)
    try:
        with engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO master_resumes
                    (id, created_at, updated_at, name, target_role, resume_data)
                VALUES ('before-dictionary', now(), now(), 'Avery', 'Technician', '{}'::jsonb)
            """))
    finally:
        engine.dispose()

    command.upgrade(alembic_config(migration_database), "head")
    engine = create_engine(migration_database)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("""
                SELECT skill_dictionary FROM master_resumes WHERE id = 'before-dictionary'
            """)).scalar_one() is None
    finally:
        engine.dispose()


def test_revision_chain_downgrades_to_base(migration_database: URL):
    command.upgrade(alembic_config(migration_database), "head")
    command.downgrade(alembic_config(migration_database), "base")

    engine = create_engine(migration_database)
    try:
        assert inspect(engine).get_table_names() == ["alembic_version"]
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).all() == []
    finally:
        engine.dispose()
