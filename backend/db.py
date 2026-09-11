"""
db.py
-----
SQLite + SQLModel persistence layer for tailored resume history.

A single SQLite file lives at backend/data/resume_history.db (gitignored).
Call init_db() once on app startup to create tables.
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
