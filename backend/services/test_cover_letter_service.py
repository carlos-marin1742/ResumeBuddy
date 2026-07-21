from unittest.mock import MagicMock, patch

from services.cover_letter_service import (
    _format_cover_letter,
    generate_cover_letter,
)


def test_adds_required_greeting_and_sign_off():
    letter = _format_cover_letter("I would welcome the opportunity to contribute.", "Carlos Marin")

    assert letter == (
        "Dear Hiring Manager,\n\n"
        "I would welcome the opportunity to contribute.\n\n"
        "Thank You\nCarlos Marin"
    )


def test_replaces_model_added_wrappers_without_duplication():
    raw = "Dear Hiring Manager,\n\nBody paragraph.\n\nSincerely,\nCandidate"
    letter = _format_cover_letter(raw, "Carlos Marin")

    assert letter.count("Dear Hiring Manager,") == 1
    assert letter.count("Thank You") == 1
    assert "Sincerely" not in letter
    assert letter.endswith("Thank You\nCarlos Marin")


def test_formatted_letter_word_count_includes_greeting_and_sign_off():
    letter = _format_cover_letter("Body paragraph.", "Carlos Marin")

    # Dear Hiring Manager (3) + Body paragraph (2) + Thank You (2) + name (2)
    assert len(letter.split()) == 9


@patch("services.cover_letter_service._build_chain")
def test_generation_still_returns_letter_with_user_name(mock_build_chain):
    chain = MagicMock()
    chain.invoke.return_value = "A focused body paragraph."
    mock_build_chain.return_value = chain

    result = generate_cover_letter(
        tailored_resume={"contact": {"name": "Carlos Marin"}},
        job_description="A sufficiently detailed job description.",
        company="Example Co",
        job_title="Engineer",
        selected_keywords=["Python"],
    )

    assert result.letter.startswith("Dear Hiring Manager,\n\n")
    assert result.letter.endswith("Thank You\nCarlos Marin")
    assert result.company == "Example Co"
    assert result.job_title == "Engineer"
    assert result.word_count == len(result.letter.split())
