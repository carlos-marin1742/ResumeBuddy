from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app
from routes.generate import RESUME_STORE
from routes.cover_letter import _store_cover_letter
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


@patch("routes.cover_letter.build_cover_letter_pdf")
def test_download_cover_letter_builds_pdf_from_edited_text(mock_build_pdf, tmp_path):
    def create_pdf(letter, output_path):
        assert letter == "Edited cover letter text."
        output_path.write_bytes(b"%PDF-1.4 test")
        return output_path

    mock_build_pdf.side_effect = create_pdf

    with patch("routes.cover_letter.OUTPUTS_DIR", tmp_path):
        response = client.post(
            "/api/download-cover-letter",
            json={
                "letter": "  Edited cover letter text.  ",
                "candidate_name": "Carlos Marin",
                "company": "Example & Co.",
                "job_title": "Software Engineer",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert "Carlos-Marin-Example-Co-Software-Engineer-Cover-Letter.pdf" in (
        response.headers["content-disposition"]
    )


def test_download_cover_letter_rejects_empty_text():
    response = client.post(
        "/api/download-cover-letter",
        json={"letter": "   "},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "cover letter cannot be empty."


def test_store_cover_letter_updates_history_record():
    record = MagicMock()
    db = MagicMock()
    db.get.return_value = record

    _store_cover_letter(db, "history-123", "Edited letter")

    assert record.cover_letter == "Edited letter"
    db.add.assert_called_once_with(record)
    db.commit.assert_called_once()


def test_store_cover_letter_preserves_backward_compatibility_without_history_id():
    db = MagicMock()

    _store_cover_letter(db, None, "Generated letter")

    db.get.assert_not_called()
    db.commit.assert_not_called()
