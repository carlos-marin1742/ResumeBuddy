"""PostgreSQL-only checks; skipped unless an explicit test database is supplied."""
import os

import pytest
from sqlalchemy import create_engine, inspect


@pytest.mark.skipif(
    not os.getenv("POSTGRES_TEST_DATABASE_URL"),
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
def test_resume_payload_columns_are_jsonb():
    engine = create_engine(os.environ["POSTGRES_TEST_DATABASE_URL"])
    inspector = inspect(engine)
    master_types = {
        column["name"]: column["type"].__class__.__name__
        for column in inspector.get_columns("master_resumes")
    }
    assert master_types["resume_data"] == "JSONB"
    tailored_types = {
        column["name"]: column["type"].__class__.__name__
        for column in inspector.get_columns("tailored_resumes")
    }
    assert tailored_types["selected_keywords"] == "JSONB"
    assert tailored_types["tailored_resume"] == "JSONB"
