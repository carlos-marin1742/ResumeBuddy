"""
db.py
-----
PostgreSQL + SQLModel persistence layer for resume records.

The application engine reads DATABASE_URL, and Alembic owns schema creation
and upgrades. This module supplies the shared engine and FastAPI session
dependency; it does not create or migrate tables at application startup.
"""
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from sqlmodel import Session, create_engine

# ── Database location ─────────────────────────────────────────────────
def _database_url() -> str:
    """Build the deployment connection URL without placing its password in env."""
    if url := os.getenv("DATABASE_URL"):
        return url
    password_file = os.getenv("DATABASE_PASSWORD_FILE")
    if password_file:
        try:
            password = Path(password_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("Database password secret is unavailable.") from exc
        if not password:
            raise RuntimeError("Database password secret is empty.")
        return (
            "postgresql+psycopg://"
            f"{quote_plus(os.getenv('DATABASE_USER', 'resumebuddy'))}:"
            f"{quote_plus(password)}@{os.getenv('DATABASE_HOST', 'postgres')}:5432/"
            f"{quote_plus(os.getenv('DATABASE_NAME', 'resumebuddy'))}"
        )
    raise RuntimeError(
        "Database configuration is required. Set DATABASE_URL locally or "
        "DATABASE_PASSWORD_FILE in a secret-managed deployment."
    )


def get_database_url() -> str:
    """Return the configured database URL when the caller needs it."""
    return _database_url()


@lru_cache
def get_engine():
    """Create the shared engine only when a request or startup needs it."""
    return create_engine(get_database_url(), echo=False)


def get_session():
    """FastAPI dependency: yields a session, closes it after the request."""
    with Session(get_engine()) as session:
        yield session
