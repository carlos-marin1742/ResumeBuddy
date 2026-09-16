import pytest
from fastapi import HTTPException
from unittest.mock import patch

from routes.generate import RESUME_STORE
from routes.preview import DownloadRequest, _resolve_resume, download_custom
from services.build_resume_pdf import PdfBuildResult


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


def test_download_custom_reports_pdf_page_count_in_response_headers(tmp_path):
    output = tmp_path / "resume.pdf"
    output.write_bytes(b"%PDF-1.4")
    request = DownloadRequest(session_id="session-1")

    with (
        patch("routes.preview._resolve_resume", return_value={"contact": {"name": "Candidate"}}),
        patch("routes.preview.OUTPUTS_DIR", tmp_path),
        patch(
            "routes.preview.build_pdf_with_overrides",
            return_value=PdfBuildResult(output, 2, False),
        ),
    ):
        response = download_custom(request)

    assert response.headers["X-PDF-Page-Count"] == "2"
    assert response.headers["X-PDF-Fitted-To-One-Page"] == "false"
