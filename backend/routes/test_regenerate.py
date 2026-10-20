from unittest.mock import patch

import pytest
from fastapi import HTTPException

from routes.generate import RESUME_STORE, RESUME_STORE_OWNERS, _store_resume
from routes.regenerate import RegenerateRequest, regenerate_section
from services.claude_service import ATSScoreResult


def _ats_result() -> ATSScoreResult:
    return ATSScoreResult(
        overall_score=80,
        keyword_coverage=0.5,
        matched_keywords=["Python"],
        missing_keywords=["Docker"],
        suggestions=[],
        raw_response="",
    )


@patch("routes.regenerate.score_resume")
@patch("routes.regenerate.regenerate_summary")
def test_regenerate_summary_updates_session_and_returns_new_score(
    mock_regenerate_summary,
    mock_score_resume,
    user_request,
):
    session_id = "regenerate-summary"
    _store_resume(session_id, {
        "summary": {"default": "Original summary"},
        "tailored_summary": "Current summary",
    }, user_request.state.user_id)
    mock_regenerate_summary.return_value = "Alternative summary"
    mock_score_resume.return_value = _ats_result()

    try:
        response = regenerate_section(
            RegenerateRequest(
                session_id=session_id,
                section="summary",
                feedback="Make it more direct.",
                job_description="Python role",
                selected_keywords=["Python"],
            ),
            http_request=user_request,
        )
        stored_summary = RESUME_STORE[session_id]["tailored_summary"]
    finally:
        RESUME_STORE.pop(session_id, None)

    assert response.summary == "Alternative summary"
    assert response.ats.overall_score == 80
    assert stored_summary == "Alternative summary"
    assert mock_regenerate_summary.call_args.kwargs["original_summary"] == "Original summary"
    assert mock_regenerate_summary.call_args.kwargs["user_feedback"] == "Make it more direct."


def test_regenerate_rejects_expired_session(user_request):
    with pytest.raises(HTTPException) as exc_info:
        regenerate_section(
            RegenerateRequest(
                session_id="expired",
                section="summary",
                job_description="Python role",
            ),
            http_request=user_request,
        )

    assert exc_info.value.status_code == 404


def test_regenerate_project_requires_target(user_request):
    session_id = "regenerate-project-target"
    _store_resume(session_id, {"projects": []}, user_request.state.user_id)

    try:
        with pytest.raises(HTTPException) as exc_info:
            regenerate_section(
                RegenerateRequest(
                    session_id=session_id,
                    section="project",
                    job_description="Python role",
                ),
                http_request=user_request,
            )
    finally:
        RESUME_STORE.pop(session_id, None)

    assert exc_info.value.status_code == 422
    assert "target (project name) is required" in exc_info.value.detail


def test_regenerate_rejects_unknown_section(user_request):
    session_id = "regenerate-unknown"
    _store_resume(session_id, {"tailored_summary": "Existing session"}, user_request.state.user_id)

    try:
        with pytest.raises(HTTPException) as exc_info:
            regenerate_section(
                RegenerateRequest(
                    session_id=session_id,
                    section="education",
                    job_description="Python role",
                ),
                http_request=user_request,
            )
    finally:
        RESUME_STORE.pop(session_id, None)

    assert exc_info.value.status_code == 422
    assert "Invalid section 'education'" in exc_info.value.detail
