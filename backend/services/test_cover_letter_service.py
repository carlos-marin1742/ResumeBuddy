from unittest.mock import MagicMock, patch

from services.cover_letter_service import (
    _format_contact_header,
    _format_cover_letter,
    _format_cover_letter_body,
    generate_cover_letter,
)


def test_adds_required_greeting_and_sign_off():
    letter = _format_cover_letter_body("I would welcome the opportunity to contribute.", "Carlos Marin")

    assert letter == (
        "Dear Hiring Manager,\n\n"
        "I would welcome the opportunity to contribute.\n\n"
        "Thank You\nCarlos Marin"
    )


def test_replaces_model_added_wrappers_without_duplication():
    raw = "Dear Hiring Manager,\n\nBody paragraph.\n\nSincerely,\nCandidate"
    letter = _format_cover_letter_body(raw, "Carlos Marin")

    assert letter.count("Dear Hiring Manager,") == 1
    assert letter.count("Thank You") == 1
    assert "Sincerely" not in letter
    assert letter.endswith("Thank You\nCarlos Marin")


def test_formatted_letter_word_count_includes_greeting_and_sign_off():
    letter = _format_cover_letter_body("Body paragraph.", "Carlos Marin")

    # Dear Hiring Manager (3) + Body paragraph (2) + Thank You (2) + name (2)
    assert len(letter.split()) == 9


def test_contact_header_contains_applicant_and_company_information():
    contact = {
        "name": "Carlos Marin",
        "location": "Houston, TX",
        "phone": "713-555-0555",
        "email": "MYEMAIL@EMAIL.COM",
    }

    assert _format_contact_header(contact, "Example Co") == (
        "Carlos Marin\nHouston, TX\n713-555-0555\nMYEMAIL@EMAIL.COM\n\n"
        "Hiring Manager\nExample Co"
    )


def test_contact_header_omits_missing_optional_applicant_fields():
    assert _format_contact_header({"name": "Carlos Marin"}, "Example Co") == (
        "Carlos Marin\n\nHiring Manager\nExample Co"
    )


@patch("services.cover_letter_service._build_chain")
def test_generation_still_returns_letter_with_user_name(mock_build_chain):
    chain = MagicMock()
    chain.invoke.return_value = "A focused body paragraph."
    mock_build_chain.return_value = chain

    result = generate_cover_letter(
        tailored_resume={
            "contact": {
                "name": "Carlos Marin",
                "location": "Houston, TX",
                "phone": "713-555-0555",
                "email": "MYEMAIL@EMAIL.COM",
            }
        },
        job_description="A sufficiently detailed job description.",
        company="Example Co",
        job_title="Engineer",
        selected_keywords=["Python"],
    )

    assert result.letter.startswith(
        "Carlos Marin\nHouston, TX\n713-555-0555\nMYEMAIL@EMAIL.COM\n\n"
        "Hiring Manager\nExample Co\n\nDear Hiring Manager,\n\n"
    )
    assert result.letter.endswith("Thank You\nCarlos Marin")
    assert result.company == "Example Co"
    assert result.job_title == "Engineer"
    counted_text = result.letter[result.letter.index("Dear Hiring Manager,"):]
    assert result.word_count == len(counted_text.split())
