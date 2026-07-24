import asyncio
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi import HTTPException, UploadFile

from routes.resume_import import parse_resume


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


def test_pdf_upload_returns_draft_for_review_without_storing_file():
    expected_draft = {"contact": {"name": "Jamie Rivera"}}
    with (
        patch("routes.resume_import.extract_pdf_text", return_value="resume text") as extract,
        patch(
            "routes.resume_import.parse_resume_text",
            return_value=(expected_draft, ["Review imported fields."]),
        ),
    ):
        result = asyncio.run(parse_resume(_upload("resume.pdf", b"%PDF-content")))

    extract.assert_called_once_with(b"%PDF-content")
    assert result.filename == "resume.pdf"
    assert result.draft == expected_draft
    assert result.warnings == ["Review imported fields."]


def test_unsupported_upload_type_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(parse_resume(_upload("resume.txt", b"plain text")))

    assert exc_info.value.status_code == 415
    assert "PDF or DOCX" in exc_info.value.detail


def test_file_signature_must_match_extension():
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(parse_resume(_upload("resume.pdf", b"not a pdf")))

    assert exc_info.value.status_code == 400
    assert "valid PDF" in exc_info.value.detail
