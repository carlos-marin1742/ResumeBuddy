"""HTTP regression coverage for cookie-session authentication middleware."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session

import db
import main
from models import User, UserSession
from routes import auth as auth_routes
from services import auth_service


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    database_path = tmp_path / "auth-middleware.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", "")
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "auth-middleware-test-pepper")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    db.get_engine.cache_clear()
    engine = db.get_engine()
    SQLModel.metadata.create_all(engine)
    main.app.dependency_overrides.clear()
    monkeypatch.setattr(main, "get_session", db.get_session)
    monkeypatch.setattr(main, "get_current_user", auth_service.get_current_user)
    sent_urls: list[str] = []
    monkeypatch.setattr(
        auth_routes,
        "send_email",
        lambda recipient, subject, url: sent_urls.append(url),
    )
    with TestClient(main.app) as client:
        yield client, engine, sent_urls
    engine.dispose()
    db.get_engine.cache_clear()


def _register_verify_login(client: TestClient, sent_urls: list[str], email: str) -> None:
    credentials = {"email": email, "password": "valid-password-123"}
    assert client.post("/api/auth/register", json=credentials).status_code == 202
    token = sent_urls.pop().split("token=")[1]
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/auth/login", json=credentials).status_code == 200


def test_verified_login_can_access_protected_get(auth_client):
    client, _, sent_urls = auth_client

    _register_verify_login(client, sent_urls, "verified@example.com")

    assert client.get("/api/resumes").status_code == 200


def test_protected_get_without_cookie_returns_401(auth_client):
    client, _, _ = auth_client

    assert client.get("/api/resumes").status_code == 401


def test_logout_revokes_session_for_protected_get(auth_client):
    client, _, sent_urls = auth_client
    _register_verify_login(client, sent_urls, "revoked@example.com")

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/resumes").status_code == 401


def test_unverified_session_returns_403(auth_client):
    client, engine, _ = auth_client
    raw_token = "unverified-session-token"
    with Session(engine) as session:
        user = User(email="unverified@example.com", password_hash="unused")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserSession(
            user_id=user.id,
            token_hash=auth_service.digest(raw_token),
            last_seen_at=auth_service.utcnow(),
            expires_at=auth_service.utcnow() + timedelta(hours=1),
        ))
        session.commit()

    client.cookies.set(auth_service.SESSION_COOKIE, raw_token)
    assert client.get("/api/resumes").status_code == 403


def test_auth_routes_are_reachable_without_a_session(auth_client):
    client, _, _ = auth_client

    assert client.get("/api/auth/me").status_code == 401
