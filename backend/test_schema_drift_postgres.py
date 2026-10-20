"""Fail when the Alembic-migrated schema differs from the SQLModel models."""
from alembic import command

from postgres_test_support import alembic_config, disposable_postgres_database, schema_drift


def test_migrated_schema_matches_models_exactly():
    with disposable_postgres_database() as database_url:
        command.upgrade(alembic_config(database_url), "head")

        drift = schema_drift(database_url)

        assert not drift, (
            "Migrated schema differs from models; add a migration or fix the model:\n"
            + "\n".join(drift)
        )
