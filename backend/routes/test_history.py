from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from models import TailoredResumeRecord
from routes.history import _to_item, download_history_cover_letter


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


def test_history_item_supports_legacy_record_without_cover_letter():
    item = _to_item(make_record())

    assert item.cover_letter is None
    assert item.job_description == "Build reliable systems."


@patch("routes.history.build_cover_letter_pdf")
def test_download_history_cover_letter_renders_stored_text(mock_build_pdf, tmp_path):
    record = make_record(cover_letter="Dear Hiring Manager,\n\nStored letter")
    db = MagicMock()
    db.get.return_value = record

    def create_pdf(letter, output_path):
        assert letter == record.cover_letter
        output_path.write_bytes(b"%PDF-1.4 test")

    mock_build_pdf.side_effect = create_pdf

    with patch("routes.history.OUTPUTS_DIR", tmp_path):
        response = download_history_cover_letter(record.id, db)

    assert response.media_type == "application/pdf"
    assert "Carlos-Marin-Example-Co-Engineer-Cover-Letter.pdf" in (
        response.headers["content-disposition"]
    )
    assert response.headers["cache-control"] == "no-store"


def test_download_history_cover_letter_rejects_record_without_letter():
    db = MagicMock()
    db.get.return_value = make_record()

    with pytest.raises(HTTPException) as exc_info:
        download_history_cover_letter("history-123", db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "No cover letter stored for this record."
