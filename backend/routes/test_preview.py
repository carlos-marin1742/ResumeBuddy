import pytest
from fastapi import HTTPException

from routes.generate import RESUME_STORE
from routes.preview import _resolve_resume


def test_resolve_resume_merges_supported_edits_and_preserves_unedited_data():
    session_id = "preview-merge"
    RESUME_STORE[session_id] = {
        "contact": {"name": "Candidate"},
        "tailored_summary": "Old summary",
        "experience": [
            {
                "company": "Example Co",
                "bullets": [
                    {"id": "exp-1", "text": "Old first"},
                    {"id": "exp-2", "text": "Old second"},
                ],
            }
        ],
        "projects": [
            {
                "name": "Project One",
                "links": {"github": "https://example.test"},
                "bullets": [{"id": "proj-1", "text": "Old project"}],
            }
        ],
    }

    try:
        result = _resolve_resume(
            session_id,
            {
                "tailored_summary": "Edited summary",
                "experience": [
                    {
                        "company": "Example Co",
                        "bullets": [{"text": "Edited first"}],
                    }
                ],
                "projects": [
                    {
                        "name": "Project One",
                        "bullets": [{"text": "Edited project"}],
                    }
                ],
            },
        )
    finally:
        RESUME_STORE.pop(session_id, None)

    assert result["tailored_summary"] == "Edited summary"
    assert result["contact"] == {"name": "Candidate"}
    assert result["experience"][0]["bullets"] == [
        {"id": "exp-1", "text": "Edited first"},
        {"id": "exp-2", "text": "Old second"},
    ]
    assert result["projects"][0]["links"] == {"github": "https://example.test"}
    assert result["projects"][0]["bullets"] == [
        {"id": "proj-1", "text": "Edited project"}
    ]


def test_resolve_resume_without_patch_returns_stored_session():
    stored = {"tailored_summary": "Summary"}
    RESUME_STORE["preview-no-patch"] = stored

    try:
        assert _resolve_resume("preview-no-patch", None) is stored
    finally:
        RESUME_STORE.pop("preview-no-patch", None)


def test_resolve_resume_rejects_expired_session():
    with pytest.raises(HTTPException) as exc_info:
        _resolve_resume("missing-session", None)

    assert exc_info.value.status_code == 404
    assert "Please regenerate your resume" in exc_info.value.detail
