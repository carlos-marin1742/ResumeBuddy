"""
models.py
---------
SQLModel table definitions for persisted tailored resumes.

Each record captures one generation: the company/role it was tailored for,
the JD, the structured tailored output, and the ATS score. The PDF is NOT
stored — it is re-rendered on demand from `tailored_resume`.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TailoredResumeRecord(SQLModel, table=True):
    __tablename__ = "tailored_resumes"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)

    # ── What it was tailored for ──────────────────────────────────────
    company: str = Field(index=True)
    job_title: str = Field(index=True)
    profile: str = Field(index=True)          # base profile: tech / clinical / admin
    job_description: str

    # ── Structured payloads (JSON → TEXT in SQLite) ───────────────────
    selected_keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    tailored_resume: dict = Field(default_factory=dict, sa_column=Column(JSON))
    cover_letter: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # ── ATS scoring (flattened for easy sort / filter) ────────────────
    ats_overall_score: int | None = Field(default=None, index=True)
    ats_keyword_coverage: float | None = Field(default=None)

    # ── Optional cached render ────────────────────────────────────────
    pdf_path: str | None = Field(default=None)


class MasterResumeRecord(SQLModel, table=True):
    """Reusable, user-reviewed resume data created in the resume builder."""

    __tablename__ = "master_resumes"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow, index=True)
    name: str = Field(index=True)
    target_role: str = Field(default="", index=True)
    resume_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
