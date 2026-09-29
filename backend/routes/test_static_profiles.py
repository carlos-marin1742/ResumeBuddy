"""HTTP coverage for the static-profile privacy gate."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import db
import main
from routes import extract as extract_module
from routes import generate as generate_module
from routes import resumes as resumes_module
from services.claude_service import KeywordExtractionResult, TailoredResume


@pytest.fixture
def authenticated_client(monkeypatch):
    user = SimpleNamespace(id="static-profile-test-user")
    monkeypatch.setattr(main, "get_current_user", lambda request, session: user)
    monkeypatch.setattr(main, "get_session", lambda: iter([MagicMock()]))
    main.app.dependency_overrides[db.get_session] = lambda: iter([MagicMock()])
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()


def test_static_profiles_disabled_returns_empty_and_rejects_static_ids(
    monkeypatch, authenticated_client,
):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")

    assert authenticated_client.get("/api/resumes").json() == {"resumes": []}
    assert authenticated_client.post(
        "/api/extract-keywords", json={"job_description": "Python", "resume_id": "base_resume"},
    ).status_code == 404
    assert authenticated_client.post(
        "/api/generate-resume", json={"job_description": "Python", "resume_id": "base_resume"},
    ).status_code == 404


def test_master_resume_remains_usable_when_static_profiles_disabled(
    monkeypatch, authenticated_client,
):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "false")
    monkeypatch.setattr(
        extract_module, "get_owned_record",
        lambda *args: SimpleNamespace(resume_data={"skills": [], "experience": [], "projects": []}),
    )
    monkeypatch.setattr(
        extract_module, "claude_extract_keywords",
        lambda _: KeywordExtractionResult(
            hard_skills=[], soft_skills=[], tools_and_technologies=[], job_titles=[],
            certifications=[], priority_keywords=[], raw_response="",
        ),
    )

    response = authenticated_client.post(
        "/api/extract-keywords",
        json={"job_description": "Python", "master_resume_id": "master-1"},
    )

    assert response.status_code == 200


def test_static_profiles_enabled_lists_and_uses_profiles(monkeypatch, tmp_path, authenticated_client):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "true")
    (tmp_path / "profile.json").write_text('{"meta":{"label":"Profile"}}')
    monkeypatch.setattr(resumes_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(extract_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(generate_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        extract_module, "claude_extract_keywords",
        lambda _: KeywordExtractionResult(
            hard_skills=[], soft_skills=[], tools_and_technologies=[], job_titles=[],
            certifications=[], priority_keywords=[], raw_response="",
        ),
    )

    assert authenticated_client.get("/api/resumes").json()["resumes"][0]["id"] == "profile"
    assert authenticated_client.post(
        "/api/extract-keywords", json={"job_description": "Python", "resume_id": "profile"},
    ).status_code == 200


def test_invalid_static_profile_flag_is_rejected(monkeypatch):
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "sometimes")
    with pytest.raises(RuntimeError, match="STATIC_PROFILES_ENABLED"):
        resumes_module.static_profiles_enabled()
