from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from routes.generate import RESUME_STORE
from services.cover_letter_service import CoverLetterResult


client = TestClient(app)


@patch("routes.cover_letter.generate_cover_letter")
def test_route_recovers_name_from_session_when_edit_patch_omits_contact(mock_generate):
    session_id = "cover-letter-test-session"
    contact = {
        "name": "Carlos Marin",
        "location": "Houston, TX",
        "phone": "713-555-0555",
        "email": "MYEMAIL@EMAIL.COM",
    }
    RESUME_STORE[session_id] = {"contact": contact}
    mock_generate.return_value = CoverLetterResult(
        letter="Dear Hiring Manager,\n\nLetter\n\nThank You\nCarlos Marin",
        word_count=8,
        company="Example Co",
        job_title="Engineer",
    )

    try:
        response = client.post(
            "/api/generate-cover-letter",
            json={
                "tailored_resume": {"tailored_summary": "Edited summary"},
                "session_id": session_id,
                "job_description": "A sufficiently detailed job description.",
                "company": "Example Co",
                "job_title": "Engineer",
                "selected_keywords": ["Python"],
            },
        )
    finally:
        RESUME_STORE.pop(session_id, None)

    assert response.status_code == 200
    assert mock_generate.call_args.kwargs["candidate_name"] == "Carlos Marin"
    assert mock_generate.call_args.kwargs["applicant_contact"] == contact


def test_route_preserves_job_description_validation():
    response = client.post(
        "/api/generate-cover-letter",
        json={"tailored_resume": {"contact": {"name": "Carlos Marin"}}, "job_description": "  "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "job_description cannot be empty."
