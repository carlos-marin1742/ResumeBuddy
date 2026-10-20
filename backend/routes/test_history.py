from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from models import TailoredResumeRecord
from routes.history import HistoryItem, _to_item, download_history_cover_letter


def make_record(**overrides):
    values = {
        "id": "history-123",
        "created_at": datetime.now(timezone.utc),
        "company": "Example Co",
        "job_title": "Engineer",
        "profile": "base_resume",
        "job_description": "Build reliable systems.",
        "selected_keywords": ["Python"],
        "tailored_resume": {"contact": {"name": "Carlos Marin"}},
        "cover_letter": None,
    }
    values.update(overrides)
    return TailoredResumeRecord(**values)


def test_history_item_reports_has_pdf_and_never_the_server_path():
    rendered = _to_item(make_record(pdf_path="/srv/outputs/Candidate-Example-Engineer_Resume_ab12.pdf"))
    pending = _to_item(make_record(pdf_path=None))

    assert rendered.has_pdf is True
    assert pending.has_pdf is False
    assert "pdf_path" not in HistoryItem.model_fields
    assert "pdf_path" not in rendered.model_dump()
    assert "/srv/outputs" not in rendered.model_dump_json()


def test_history_item_supports_legacy_record_without_cover_letter():
    item = _to_item(make_record())

    assert item.cover_letter is None
    assert item.job_description == "Build reliable systems."


@patch("routes.history.build_cover_letter_pdf")
def test_download_history_cover_letter_renders_stored_text(mock_build_pdf, tmp_path, user_request):
    record = make_record(cover_letter="Dear Hiring Manager,\n\nStored letter")
    db = MagicMock()
    db.exec.return_value.first.return_value = record

    def create_pdf(letter, output_path):
        assert letter == record.cover_letter
        output_path.write_bytes(b"%PDF-1.4 test")

    mock_build_pdf.side_effect = create_pdf

    with patch("routes.history.OUTPUTS_DIR", tmp_path):
        response = download_history_cover_letter(record.id, db, http_request=user_request)

    assert response.media_type == "application/pdf"
    assert "Carlos-Marin-Example-Co-Engineer-Cover-Letter.pdf" in (
        response.headers["content-disposition"]
    )
    assert response.headers["cache-control"] == "no-store"


def test_download_history_cover_letter_rejects_record_without_letter(user_request):
    db = MagicMock()
    db.exec.return_value.first.return_value = make_record()

    with pytest.raises(HTTPException) as exc_info:
        download_history_cover_letter("history-123", db, http_request=user_request)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "No cover letter stored for this record."
