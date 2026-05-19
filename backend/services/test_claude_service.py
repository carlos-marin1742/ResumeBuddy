"""
test_claude_service.py
----------------------
Unit tests for claude_service.py.
All Anthropic API calls are mocked — no tokens consumed, no network required.

Run:
    pytest test_claude_service.py -v
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import claude_service as svc
from claude_service import (
    ATSScoreResult,
    KeywordExtractionResult,
    TailoredResume,
    _extract_json,
)


# ---------------------------------------------------------------------------
# Fixtures: canned Claude responses
# ---------------------------------------------------------------------------

KEYWORD_RESPONSE = {
    "hard_skills": ["Python", "PyTorch", "SQL"],
    "soft_skills": ["communication", "leadership"],
    "tools_and_technologies": ["Kubernetes", "MLflow", "AWS SageMaker"],
    "job_titles": ["Senior ML Engineer", "ML Engineer"],
    "certifications": ["AWS Certified Machine Learning"],
    "priority_keywords": ["Python", "PyTorch", "Kubernetes", "MLflow", "leadership"],
}

TAILORING_RESPONSE = {
    "summary": "ML Engineer with 5 years of experience building scalable PyTorch pipelines on Kubernetes.",
    "experiences": [
        {
            "company": "Acme Corp",
            "title": "ML Engineer",
            "tailored_bullets": [
                {
                    "original": "Built training pipelines that reduced model iteration time by 40%.",
                    "tailored": "Engineered PyTorch training pipelines on Kubernetes, reducing model iteration time by 40%.",
                    "keywords_injected": ["PyTorch", "Kubernetes"],
                },
                {
                    "original": "Collaborated with product teams to ship recommendation features.",
                    "tailored": "Led cross-functional collaboration with product teams to deliver MLflow-tracked recommendation features.",
                    "keywords_injected": ["MLflow", "cross-functional"],
                },
            ],
        }
    ],
    "skills_to_highlight": ["Python", "PyTorch", "Kubernetes", "MLflow"],
}

SCORING_RESPONSE = {
    "overall_score": 82,
    "keyword_coverage": 0.76,
    "matched_keywords": ["Python", "PyTorch", "Kubernetes", "MLflow"],
    "missing_keywords": ["AWS SageMaker", "dbt"],
    "suggestions": [
        "Add AWS SageMaker to your skills section.",
        "Mention dbt in a relevant bullet if applicable.",
    ],
}

SAMPLE_JD = "We need a Senior ML Engineer with Python, PyTorch, and Kubernetes experience."

SAMPLE_RESUME = {
    "summary": "Software engineer with 5 years of ML experience.",
    "skills": {"languages": ["Python"], "ai_ml": ["PyTorch"]},
    "experience": [
        {
            "company": "Acme Corp",
            "title": "ML Engineer",
            "bullets": [
                {"text": "Built training pipelines that reduced model iteration time by 40%."},
                {"text": "Collaborated with product teams to ship recommendation features."},
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Helper: build a mock Anthropic message response
# ---------------------------------------------------------------------------

def _mock_message(response_dict: dict) -> MagicMock:
    """Return a MagicMock shaped like anthropic.types.Message."""
    msg = MagicMock()
    msg.content = [MagicMock()]
    msg.content[0].text = json.dumps(response_dict)
    return msg


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_parses_plain_json(self):
        raw = json.dumps({"key": "value"})
        assert _extract_json(raw) == {"key": "value"}

    def test_strips_json_fences(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        assert _extract_json(raw) == {"key": "value"}

    def test_strips_plain_fences(self):
        raw = "```\n{\"key\": \"value\"}\n```"
        assert _extract_json(raw) == {"key": "value"}

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("this is not json")

    def test_handles_nested_objects(self):
        data = {"a": {"b": [1, 2, 3]}}
        assert _extract_json(json.dumps(data)) == data


# ---------------------------------------------------------------------------
# extract_keywords
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    @patch("claude_service._get_client")
    def test_returns_keyword_extraction_result(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(KEYWORD_RESPONSE)

        result = svc.extract_keywords(SAMPLE_JD)

        assert isinstance(result, KeywordExtractionResult)

    @patch("claude_service._get_client")
    def test_hard_skills_populated(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(KEYWORD_RESPONSE)

        result = svc.extract_keywords(SAMPLE_JD)

        assert result.hard_skills == ["Python", "PyTorch", "SQL"]

    @patch("claude_service._get_client")
    def test_priority_keywords_populated(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(KEYWORD_RESPONSE)

        result = svc.extract_keywords(SAMPLE_JD)

        assert "Python" in result.priority_keywords

    @patch("claude_service._get_client")
    def test_raw_response_preserved(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(KEYWORD_RESPONSE)

        result = svc.extract_keywords(SAMPLE_JD)

        assert result.raw_response  # non-empty

    @patch("claude_service._get_client")
    def test_missing_fields_default_to_empty_list(self, mock_get_client):
        # Claude returns a response with some fields missing
        partial = {"hard_skills": ["Python"]}
        mock_get_client.return_value.messages.create.return_value = _mock_message(partial)

        result = svc.extract_keywords(SAMPLE_JD)

        assert result.soft_skills == []
        assert result.certifications == []

    @patch("claude_service._get_client")
    def test_raises_on_invalid_json_response(self, mock_get_client):
        msg = MagicMock()
        msg.content = [MagicMock()]
        msg.content[0].text = "Sorry, I cannot process that request."
        mock_get_client.return_value.messages.create.return_value = msg

        with pytest.raises(ValueError, match="non-JSON"):
            svc.extract_keywords(SAMPLE_JD)

    @patch("claude_service._get_client")
    def test_api_called_with_correct_model(self, mock_get_client):
        mock_create = mock_get_client.return_value.messages.create
        mock_create.return_value = _mock_message(KEYWORD_RESPONSE)

        svc.extract_keywords(SAMPLE_JD)

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == svc.MODEL

    @patch("claude_service._get_client")
    def test_jd_text_appears_in_prompt(self, mock_get_client):
        mock_create = mock_get_client.return_value.messages.create
        mock_create.return_value = _mock_message(KEYWORD_RESPONSE)

        svc.extract_keywords(SAMPLE_JD)

        call_kwargs = mock_create.call_args.kwargs
        user_content = call_kwargs["messages"][0]["content"]
        assert SAMPLE_JD in user_content


# ---------------------------------------------------------------------------
# tailor_resume
# ---------------------------------------------------------------------------

class TestTailorResume:
    @patch("claude_service._get_client")
    def test_returns_tailored_resume(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, ["Python", "PyTorch"])

        assert isinstance(result, TailoredResume)

    @patch("claude_service._get_client")
    def test_summary_populated(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, ["Python"])

        assert "PyTorch" in result.summary

    @patch("claude_service._get_client")
    def test_experience_count_matches(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, [])

        assert len(result.experiences) == 1

    @patch("claude_service._get_client")
    def test_bullets_have_original_and_tailored(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, [])
        bullet = result.experiences[0].tailored_bullets[0]

        assert bullet.original
        assert bullet.tailored
        assert bullet.original != bullet.tailored

    @patch("claude_service._get_client")
    def test_keywords_injected_field_present(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, ["PyTorch"])
        bullet = result.experiences[0].tailored_bullets[0]

        assert isinstance(bullet.keywords_injected, list)
        assert "PyTorch" in bullet.keywords_injected

    @patch("claude_service._get_client")
    def test_skills_to_highlight_populated(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(TAILORING_RESPONSE)

        result = svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, [])

        assert len(result.skills_to_highlight) > 0

    @patch("claude_service._get_client")
    def test_raises_on_invalid_json_response(self, mock_get_client):
        msg = MagicMock()
        msg.content = [MagicMock()]
        msg.content[0].text = "Here is a tailored resume for you..."
        mock_get_client.return_value.messages.create.return_value = msg

        with pytest.raises(ValueError, match="non-JSON"):
            svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, [])

    @patch("claude_service._get_client")
    def test_selected_keywords_appear_in_prompt(self, mock_get_client):
        mock_create = mock_get_client.return_value.messages.create
        mock_create.return_value = _mock_message(TAILORING_RESPONSE)

        keywords = ["PyTorch", "Kubernetes"]
        svc.tailor_resume(SAMPLE_RESUME, SAMPLE_JD, keywords)

        user_content = mock_create.call_args.kwargs["messages"][0]["content"]
        assert "PyTorch" in user_content
        assert "Kubernetes" in user_content


# ---------------------------------------------------------------------------
# score_resume
# ---------------------------------------------------------------------------

class TestScoreResume:
    @patch("claude_service._get_client")
    def test_returns_ats_score_result(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(SCORING_RESPONSE)

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert isinstance(result, ATSScoreResult)

    @patch("claude_service._get_client")
    def test_overall_score_in_range(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(SCORING_RESPONSE)

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert 0 <= result.overall_score <= 100

    @patch("claude_service._get_client")
    def test_keyword_coverage_is_float(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(SCORING_RESPONSE)

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert isinstance(result.keyword_coverage, float)
        assert 0.0 <= result.keyword_coverage <= 1.0

    @patch("claude_service._get_client")
    def test_matched_and_missing_keywords_populated(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(SCORING_RESPONSE)

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert "Python" in result.matched_keywords
        assert "AWS SageMaker" in result.missing_keywords

    @patch("claude_service._get_client")
    def test_suggestions_is_list(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message(SCORING_RESPONSE)

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert isinstance(result.suggestions, list)
        assert len(result.suggestions) > 0

    @patch("claude_service._get_client")
    def test_raises_on_invalid_json_response(self, mock_get_client):
        msg = MagicMock()
        msg.content = [MagicMock()]
        msg.content[0].text = "Your resume scores well overall."
        mock_get_client.return_value.messages.create.return_value = msg

        with pytest.raises(ValueError, match="non-JSON"):
            svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

    @patch("claude_service._get_client")
    def test_defaults_on_missing_score_fields(self, mock_get_client):
        mock_get_client.return_value.messages.create.return_value = _mock_message({})

        result = svc.score_resume(TAILORING_RESPONSE, SAMPLE_JD)

        assert result.overall_score == 0
        assert result.keyword_coverage == 0.0
        assert result.matched_keywords == []