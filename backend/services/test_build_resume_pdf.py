from build_resume_pdf import _render_html


def test_resume_html_renders_target_role_beneath_name():
    html = _render_html({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "targetRole": "Product Manager",
    })

    name_position = html.index('<div class="name">Jamie Rivera</div>')
    role_position = html.index('<div class="role">Product Manager</div>')
    contact_position = html.index('<div class="contact">')

    assert name_position < role_position < contact_position


def test_resume_html_omits_empty_target_role():
    html = _render_html({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
    })

    assert '<div class="role">' not in html


def test_resume_html_accepts_legacy_snake_case_target_role():
    html = _render_html({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "target_role": "Product Manager",
    })

    assert '<div class="role">Product Manager</div>' in html
