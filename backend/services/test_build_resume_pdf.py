from build_resume_pdf import _render_html


def test_resume_html_escapes_script_tags_in_bullet_text():
    html = _render_html({
        "contact": {"name": "Jamie Rivera"},
        "experience": [{
            "company": "Acme",
            "title": "Engineer",
            "bullets": [{"text": "<script>alert(document.cookie)</script>"}],
        }],
    })

    assert "<script>alert(document.cookie)</script>" not in html
    assert "&lt;script&gt;" in html


def test_resume_html_escapes_name_and_summary():
    html = _render_html({
        "contact": {"name": '<img src=x onerror=alert(1)>'},
        "summary": '"><script>alert(1)</script>',
    })

    assert "<img src=x" not in html
    assert "<script>alert(1)</script>" not in html


def test_resume_html_escapes_skill_and_project_fields():
    html = _render_html({
        "contact": {"name": "Jamie Rivera"},
        "skills": {"languages": ['<b onmouseover=alert(1)>Python</b>']},
        "ats_config": {"skills_order": ["languages"]},
        "projects": [{
            "name": '</span><script>alert(2)</script>',
            "bullets": [{"text": "Shipped it."}],
        }],
    })

    assert "<b onmouseover=" not in html
    assert "<script>alert(2)</script>" not in html


def test_resume_html_labels_additional_skills_without_raw_category_key():
    html = _render_html({
        "contact": {"name": "Jamie Rivera"},
        "skills": {"additional_skills": ["Venipuncture"]},
        "ats_config": {"skills_order": ["additional_skills"]},
    })

    assert "Additional Skills:" in html
    assert "additional_skills:" not in html


def test_resume_html_drops_javascript_scheme_links():
    html = _render_html({
        "contact": {
            "name": "Jamie Rivera",
            "portfolio": "javascript:alert(document.domain)",
        },
    })

    assert "javascript:" not in html


def test_resume_html_escapes_quote_in_email_to_prevent_attribute_breakout():
    html = _render_html({
        "contact": {
            "name": "Jamie Rivera",
            "email": 'x"><script>alert(3)</script>@evil.test',
        },
    })

    assert "<script>alert(3)</script>" not in html


def test_resume_html_keeps_valid_https_links():
    html = _render_html({
        "contact": {"name": "Jamie Rivera", "portfolio": "https://example.test"},
    })

    assert 'href="https://example.test"' in html


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
