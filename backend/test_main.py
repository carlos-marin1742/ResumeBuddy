from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import create_engine

import main
from main import app

client = TestClient(app)


def test_security_headers_present_on_every_response():
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_ai_route_rate_limit_returns_429_after_limit_exceeded():
    main._rate_limit_hits.clear()
    try:
        with patch.object(main, "RATE_LIMIT_MAX_REQUESTS", 2):
            payload = {"job_description": "  "}  # invalid, but still consumes the bucket
            first = client.post("/api/extract-keywords", json=payload)
            second = client.post("/api/extract-keywords", json=payload)
            third = client.post("/api/extract-keywords", json=payload)

        assert first.status_code == 422
        assert second.status_code == 422
        assert third.status_code == 429
    finally:
        main._rate_limit_hits.clear()


def test_rate_limit_does_not_apply_to_unrelated_routes():
    main._rate_limit_hits.clear()
    try:
        with patch.object(main, "RATE_LIMIT_MAX_REQUESTS", 1):
            client.post("/api/extract-keywords", json={"job_description": "  "})
            response = client.get("/api/resumes")

        assert response.status_code != 429
    finally:
        main._rate_limit_hits.clear()


def test_liveness_needs_no_database_or_dependencies():
    with patch("services.readiness.get_engine", side_effect=AssertionError("db touched")),             patch("services.readiness._resolved_chromium_path", side_effect=AssertionError("chromium touched")):
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_ok_when_every_dependency_is_ready(monkeypatch):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    with patch("services.readiness.database_ready", return_value=True),             patch("services.readiness.chromium_ready", return_value=True):
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_fails_when_database_is_unreachable():
    # Nothing listens on port 1, so the connection is refused immediately.
    dead_engine = create_engine(
        "postgresql+psycopg://user:secret@127.0.0.1:1/db",
        connect_args={"connect_timeout": 1},
    )
    with patch("services.readiness.get_engine", return_value=dead_engine),             patch("services.readiness.chromium_ready", return_value=True):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "secret" not in response.text and "127.0.0.1" not in response.text


def test_readiness_fails_when_chromium_is_missing(tmp_path):
    missing = str(tmp_path / "no-chrome")
    with patch("services.readiness.database_ready", return_value=True),             patch("services.readiness._resolved_chromium_path", return_value=missing):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert missing not in response.text


def test_readiness_checks_base_resume_only_when_static_profiles_enabled(monkeypatch, tmp_path):
    missing = tmp_path / "base_resume.json"
    with patch("services.readiness.database_ready", return_value=True),             patch("services.readiness.chromium_ready", return_value=True),             patch.object(main, "BASE_RESUME_PATH", missing):
        monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
        assert client.get("/health/ready").status_code == 200

        monkeypatch.setenv("STATIC_PROFILES_ENABLED", "true")
        assert client.get("/health/ready").status_code == 503

        missing.write_text("{}")
        assert client.get("/health/ready").status_code == 200


def test_health_routes_skip_auth_and_rate_limits(monkeypatch):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    main._api_rate_limit_hits.clear()
    main._read_rate_limit_hits.clear()
    try:
        with patch("services.readiness.database_ready", return_value=True),                 patch("services.readiness.chromium_ready", return_value=True),                 patch.object(main, "API_RATE_LIMIT_MAX_REQUESTS", 1),                 patch.object(main, "READ_RATE_LIMIT_MAX_REQUESTS", 1):
            statuses = [
                client.get(path).status_code
                for _ in range(3)
                for path in ("/health", "/health/ready")
            ]
        assert statuses == [200] * 6  # no session cookie, limits of 1, still never 401/429
        assert not main._api_rate_limit_hits and not main._read_rate_limit_hits
    finally:
        main._api_rate_limit_hits.clear()
        main._read_rate_limit_hits.clear()
