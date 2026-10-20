"""PostgreSQL-only checks; skipped unless an explicit test database is supplied."""
from alembic import command
from sqlalchemy import create_engine, inspect

from postgres_test_support import alembic_config, disposable_postgres_database


def test_resume_payload_columns_are_jsonb():
    with disposable_postgres_database() as database_url:
        command.upgrade(alembic_config(database_url), "head")
        engine = create_engine(database_url)
        try:
            inspector = inspect(engine)
            master_types = {
                column["name"]: column["type"].__class__.__name__
                for column in inspector.get_columns("master_resumes")
            }
            tailored_types = {
                column["name"]: column["type"].__class__.__name__
                for column in inspector.get_columns("tailored_resumes")
            }
        finally:
            engine.dispose()

    assert master_types["resume_data"] == "JSONB"
    assert tailored_types["selected_keywords"] == "JSONB"
    assert tailored_types["tailored_resume"] == "JSONB"
