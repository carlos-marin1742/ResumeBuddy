"""
db.py
-----
PostgreSQL + SQLModel persistence layer for resume records.

The application engine reads DATABASE_URL, and Alembic owns schema creation
and upgrades. This module supplies the shared engine and FastAPI session
dependency; it does not create or migrate tables at application startup.
"""
import os

from sqlmodel import Session, create_engine

# ── Database location ─────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://resumebuddy:resumebuddy@postgres:5432/resumebuddy",
)

engine = create_engine(DATABASE_URL, echo=False)


def get_session():
    """FastAPI dependency: yields a session, closes it after the request."""
    with Session(engine) as session:
        yield session
