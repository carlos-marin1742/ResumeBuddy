"""Deleting a user must remove everything they own, and nothing else."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlmodel import select

from models import (
    AuthToken,
    MasterResumeRecord,
    TailoredResumeRecord,
    User,
    UserSession,
)


pytest_plugins = ("postgres_test_support",)

OWNED_MODELS = (AuthToken, UserSession, MasterResumeRecord, TailoredResumeRecord)


def _seed_user(db, label: str) -> User:
    now = datetime.now(timezone.utc)
    user = User(id=f"user-{label}", email=f"{label}@example.test", password_hash="hash")
    db.add(user)
    db.flush()
    db.add_all([
        AuthToken(
            user_id=user.id, token_hash=f"token-{label}", purpose="verify_email",
            expires_at=now + timedelta(hours=1),
        ),
        UserSession(
            user_id=user.id, token_hash=f"session-{label}",
            expires_at=now + timedelta(hours=1), last_seen_at=now,
        ),
        MasterResumeRecord(user_id=user.id, name=f"master-{label}"),
        TailoredResumeRecord(
            user_id=user.id, company="Acme", job_title="Engineer", profile="p",
            job_description="Build APIs",
        ),
    ])
    db.commit()
    return user


def _count(db, model, user_id: str) -> int:
    return db.exec(select(func.count()).select_from(model).where(model.user_id == user_id)).one()


def test_deleting_a_user_cascades_to_everything_they_own(postgres_session):
    doomed = _seed_user(postgres_session, "doomed")
    survivor = _seed_user(postgres_session, "survivor")
    for model in OWNED_MODELS:
        assert _count(postgres_session, model, doomed.id) == 1

    postgres_session.delete(doomed)
    postgres_session.commit()

    for model in OWNED_MODELS:
        assert _count(postgres_session, model, doomed.id) == 0, model.__tablename__
        assert _count(postgres_session, model, survivor.id) == 1, model.__tablename__
    assert postgres_session.get(User, doomed.id) is None
    assert postgres_session.get(User, survivor.id) is not None


def test_every_user_foreign_key_is_declared_on_delete_cascade(postgres_session):
    rules = postgres_session.exec(
        text(
            "SELECT conrelid::regclass::text, confdeltype FROM pg_constraint "
            "WHERE contype = 'f' AND confrelid = 'users'::regclass ORDER BY 1"
        )
    ).all()

    assert [table for table, _ in rules] == [
        "auth_tokens", "master_resumes", "tailored_resumes", "user_sessions",
    ]
    assert {rule for _, rule in rules} == {"c"}  # 'c' is ON DELETE CASCADE
