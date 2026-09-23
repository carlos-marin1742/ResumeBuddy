from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlmodel import SQLModel, Session, create_engine, select
from starlette.requests import Request

from models import AuthToken, User, UserSession
from services.auth_service import (
    SESSION_COOKIE,
    consume_token,
    create_session,
    get_current_user,
    hash_password,
    issue_token,
    utcnow,
    verify_password,
)


@pytest.fixture
def auth_db(monkeypatch):
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "test-only-pepper")
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _request(token: str) -> Request:
    return Request({"type": "http", "headers": [(b"cookie", f"{SESSION_COOKIE}={token}".encode())]})


def test_passwords_are_bcrypt_hashes_and_not_reversible():
    encoded = hash_password("a secure passphrase")
    assert encoded != "a secure passphrase"
    assert encoded.startswith("$2")
    assert verify_password("a secure passphrase", encoded)
    assert not verify_password("wrong password", encoded)


def test_one_time_tokens_expire_and_cannot_be_reused(auth_db):
    user = User(email="person@example.com", password_hash=hash_password("a secure passphrase"))
    auth_db.add(user); auth_db.commit(); auth_db.refresh(user)
    raw = issue_token(auth_db, user, "verify_email"); auth_db.commit()
    assert consume_token(auth_db, raw, "verify_email").id == user.id
    auth_db.commit()
    with pytest.raises(HTTPException, match="invalid or has expired"):
        consume_token(auth_db, raw, "verify_email")
    expired = AuthToken(user_id=user.id, token_hash="expired", purpose="password_reset", expires_at=utcnow() - timedelta(seconds=1))
    auth_db.add(expired); auth_db.commit()
    with pytest.raises(HTTPException, match="invalid or has expired"):
        consume_token(auth_db, "not-the-expired-token", "password_reset")


def test_expired_server_session_is_rejected(auth_db):
    user = User(email="person@example.com", password_hash=hash_password("a secure passphrase"), email_verified_at=utcnow())
    auth_db.add(user); auth_db.commit(); auth_db.refresh(user)
    raw = create_session(auth_db, user); auth_db.commit()
    session = auth_db.exec(select(UserSession).where(UserSession.user_id == user.id)).one()
    session.expires_at = utcnow() - timedelta(seconds=1); auth_db.add(session); auth_db.commit()
    with pytest.raises(HTTPException, match="Session expired"):
        get_current_user(_request(raw), auth_db)
