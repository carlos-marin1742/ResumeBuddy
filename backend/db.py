"""
db.py
-----
SQLite + SQLModel persistence layer for tailored resume history.

A single SQLite file lives at backend/data/resume_history.db (gitignored).
Call init_db() once on app startup to create tables.
"""
from pathlib import Path
from sqlmodel import SQLModel, Session, create_engine

# ── Database location ─────────────────────────────────────────────────
DB_PATH = Path(__file__).resolve().parent / "data" / "resume_history.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLITE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False: FastAPI may touch the session across threads.
engine = create_engine(
    SQLITE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    from models import TailoredResumeRecord  # noqa: F401  (registers metadata)
    SQLModel.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: yields a session, closes it after the request."""
    with Session(engine) as session:
        yield session