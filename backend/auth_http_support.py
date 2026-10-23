"""Shared fixtures for tests that drive the real auth stack over HTTP on PostgreSQL."""
from dataclasses import dataclass

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

import db
import main
from postgres_test_support import alembic_config, disposable_postgres_database
from routes import auth as auth_routes
from services import auth_service

PASSWORD = "valid-password-123"


@dataclass
class AuthStack:
    client: TestClient
    engine: object
    sent_urls: list[str]
    database_url: str


@pytest.fixture(scope="module")
def auth_database_url():
    with disposable_postgres_database() as url:
        command.upgrade(alembic_config(url), "head")
        yield url.render_as_string(hide_password=False)


@pytest.fixture
def auth_stack(auth_database_url, monkeypatch):
    """The real middleware, sessions and routes against a clean migrated database.

    Registration is closed unless a test sets REGISTRATION_MODE itself.
    """
    monkeypatch.setenv("DATABASE_URL", auth_database_url)
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", "")
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", "auth-stack-test-pepper")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    monkeypatch.delenv("REGISTRATION_ALLOWLIST", raising=False)
    db.get_engine.cache_clear()
    main.app.dependency_overrides.clear()
    monkeypatch.setattr(main, "get_session", db.get_session)
    monkeypatch.setattr(main, "get_current_user", auth_service.get_current_user)
    for name in (
        "API_RATE_LIMIT_MAX_REQUESTS", "READ_RATE_LIMIT_MAX_REQUESTS",
        "AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS", "AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS",
    ):
        monkeypatch.setattr(main, name, 10**9)
    sent_urls: list[str] = []
    monkeypatch.setattr(
        auth_routes, "send_email", lambda recipient, subject, url: sent_urls.append(url)
    )
    engine = db.get_engine()
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE auth_tokens, user_sessions, master_resumes, tailored_resumes, users"))
    with TestClient(main.app) as client:
        yield AuthStack(client, engine, sent_urls, auth_database_url)
    for buckets in (
        main._api_rate_limit_hits, main._read_rate_limit_hits, main._auth_rate_limit_hits,
    ):
        buckets.clear()
    engine.dispose()
    db.get_engine.cache_clear()
