"""Shared PostgreSQL fixtures for persistence tests that need deployed schema."""
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel

from models import User


BACKEND_DIR = Path(__file__).resolve().parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def alembic_config(database_url: URL) -> Config:
    config = Config(str(ALEMBIC_INI))
    # alembic/env.py gives this explicit test URL precedence over the app URL.
    config.attributes["database_url"] = database_url.render_as_string(
        hide_password=False
    ).replace("%", "%%")
    return config


def schema_drift(database_url: URL) -> list[str]:
    """Differences `alembic check` would report between the database and the models.

    Uses the same comparison options as alembic/env.py (compare_type=True).
    An empty list means the migrated schema matches the models exactly.
    """
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diffs = compare_metadata(context, SQLModel.metadata)
    finally:
        engine.dispose()
    # Table-level changes are tuples; column changes arrive grouped in lists.
    return [
        repr(diff)
        for entry in diffs
        for diff in (entry if isinstance(entry, list) else [entry])
    ]


@contextmanager
def disposable_postgres_database():
    configured_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
    if not configured_url:
        pytest.skip("POSTGRES_TEST_DATABASE_URL is not configured")

    try:
        control_url = make_url(configured_url)
    except (TypeError, ValueError) as exc:
        pytest.skip(f"POSTGRES_TEST_DATABASE_URL is invalid: {exc}")

    if not control_url.database:
        pytest.skip("POSTGRES_TEST_DATABASE_URL must include a database name")

    database_name = f"resumebuddy_migration_test_{uuid4().hex}"
    test_url = control_url.set(database=database_name)
    control_engine = create_engine(control_url, isolation_level="AUTOCOMMIT")

    try:
        with control_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    except SQLAlchemyError as exc:
        control_engine.dispose()
        pytest.skip(f"PostgreSQL migration test database is unavailable: {exc}")

    try:
        yield test_url
    finally:
        # The generated name is the only database targeted here. Terminating
        # its remaining sessions makes cleanup reliable after a failed test.
        with control_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :database_name "
                    "AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        control_engine.dispose()


def _truncate_persistence_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE auth_tokens, user_sessions, master_resumes, "
                "tailored_resumes, users"
            )
        )


@pytest.fixture(scope="session")
def postgres_persistence_engine() -> Engine:
    """One migrated disposable database for the PostgreSQL persistence tests."""
    with disposable_postgres_database() as database_url:
        command.upgrade(alembic_config(database_url), "head")
        engine = create_engine(database_url)
        try:
            yield engine
        finally:
            engine.dispose()


@pytest.fixture
def postgres_session(postgres_persistence_engine: Engine):
    """A clean SQLModel session backed by the Alembic-created PostgreSQL schema."""
    _truncate_persistence_tables(postgres_persistence_engine)
    try:
        with Session(postgres_persistence_engine) as session:
            yield session
    finally:
        _truncate_persistence_tables(postgres_persistence_engine)


@pytest.fixture
def postgres_user(postgres_session: Session) -> User:
    """A persisted user that owns the rows a test creates through routes."""
    user = User(email="owner@example.com", password_hash="not-a-real-hash")
    postgres_session.add(user)
    postgres_session.commit()
    postgres_session.refresh(user)
    return user


@pytest.fixture
def owner_request(postgres_user: User) -> SimpleNamespace:
    """Stands in for the Request the auth middleware stamps with state.user_id."""
    return SimpleNamespace(state=SimpleNamespace(user_id=postgres_user.id))
