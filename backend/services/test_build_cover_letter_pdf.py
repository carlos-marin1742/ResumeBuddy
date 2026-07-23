from services.build_cover_letter_pdf import (
    _render_cover_letter_html,
    cover_letter_filename,
)


def test_cover_letter_html_uses_required_font_and_size():
    rendered = _render_cover_letter_html("Dear Hiring Manager,\n\nHello")

    assert 'font-family: "Times New Roman", Times, serif' in rendered
    assert "font-size: 12pt" in rendered
    assert "white-space: pre-wrap" in rendered


def test_cover_letter_html_escapes_user_content():
    rendered = _render_cover_letter_html("<script>alert('no')</script>")

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_cover_letter_filename_removes_unsafe_characters():
    assert cover_letter_filename(
        "Carlos Marin",
        "Example & Co.",
        "Software/Engineer",
    ) == "Carlos-Marin-Example-Co-Software-Engineer-Cover-Letter.pdf"
