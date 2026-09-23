"""
models.py
---------
SQLModel table definitions for persisted tailored resumes.

Each record captures one generation: the company/role it was tailored for,
the JD, the structured tailored output, and the ATS score. The PDF is NOT
stored â€” it is re-rendered on demand from `tailored_resume`.
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TailoredResumeRecord(SQLModel, table=True):
    __tablename__ = "tailored_resumes"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )

    # â”€â”€ What it was tailored for â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    company: str = Field(index=True)
    job_title: str = Field(index=True)
    profile: str = Field(index=True)          # base profile: tech / clinical / admin
    job_description: str

    # â”€â”€ Structured payloads (JSON â†’ TEXT in SQLite) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    selected_keywords: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite")),
    )
    tailored_resume: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite")),
    )
    cover_letter: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # â”€â”€ ATS scoring (flattened for easy sort / filter) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ats_overall_score: int | None = Field(default=None, index=True)
    ats_keyword_coverage: float | None = Field(default=None)

    # â”€â”€ Optional cached render â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    pdf_path: str | None = Field(default=None)


class MasterResumeRecord(SQLModel, table=True):
    """Reusable, user-reviewed resume data created in the resume builder."""

    __tablename__ = "master_resumes"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    name: str = Field(index=True)
    target_role: str = Field(default="", index=True)
    resume_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite")),
    )
    # Populated by the future dictionary-seeding pass. Null means no attempt
    # has created a dictionary; it is intentionally distinct from an empty one.
    skill_dictionary: dict | None = Field(
        default=None,
        sa_column=Column(JSONB().with_variant(JSON(), "sqlite"), nullable=True),
    )


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    email: str = Field(index=True, sa_column_kwargs={"unique": True})
    password_hash: str
    email_verified_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    failed_login_count: int = Field(default=0, nullable=False)
    locked_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class AuthToken(SQLModel, table=True):
    __tablename__ = "auth_tokens"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(index=True, sa_column_kwargs={"unique": True})
    purpose: str = Field(index=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    used_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))


class UserSession(SQLModel, table=True):
    __tablename__ = "user_sessions"

    id: str = Field(default_factory=lambda: uuid4().hex, primary_key=True)
    user_id: str = Field(foreign_key="users.id", index=True)
    token_hash: str = Field(index=True, sa_column_kwargs={"unique": True})
    created_at: datetime = Field(default_factory=_utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    last_seen_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    revoked_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
