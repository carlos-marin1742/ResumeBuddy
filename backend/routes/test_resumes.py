import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from routes.resumes import list_resumes


def test_list_resumes_returns_valid_profiles_and_skips_bad_or_example_files(tmp_path):
    (tmp_path / "base_resume.json").write_text(
        json.dumps(
            {
                "meta": {
                    "label": "Technology",
                    "target_roles": ["Engineer"],
                    "last_updated": "2026-07-01",
                }
            }
        )
    )
    (tmp_path / "clinical_resume.json").write_text(json.dumps({}))
    (tmp_path / "resume_example.json").write_text(json.dumps({"meta": {"label": "Skip"}}))
    (tmp_path / "malformed.json").write_text("{not-json")

    with patch("routes.resumes.DATA_DIR", tmp_path):
        result = list_resumes()

    assert len(result.resumes) == 2
    assert [profile.id for profile in result.resumes] == [
        "base_resume",
        "clinical_resume",
    ]
    assert result.resumes[0].name == "Technology"
    assert result.resumes[0].target_roles == ["Engineer"]
    assert result.resumes[1].name == "Clinical Resume"


def test_list_resumes_returns_404_when_no_valid_profiles_exist(tmp_path):
    (tmp_path / "malformed.json").write_text("{not-json")

    with patch("routes.resumes.DATA_DIR", tmp_path):
        with pytest.raises(HTTPException) as exc_info:
            list_resumes()

    assert exc_info.value.status_code == 404
    assert "No resume profiles found" in exc_info.value.detail
