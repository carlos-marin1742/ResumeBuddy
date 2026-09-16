from pypdf import PdfReader

from build_resume_pdf import _build_pdf_overrides_worker, _build_pdf_worker, _render_html


def _minimal_resume() -> dict:
    return {
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "summary": "Backend engineer who builds reliable services.",
        "experience": [{
            "company": "Acme",
            "title": "Engineer",
            "bullets": [{"text": "Built a reliable API."}],
        }],
    }


def _dense_resume() -> dict:
    resume = _minimal_resume()
    resume["experience"][0]["bullets"] = [
        {"text": f"Delivered measurable platform improvement number {index} with detailed implementation notes."}
        for index in range(100)
    ]
    return resume


def test_auto_pdf_worker_reports_one_page_for_fitting_document(tmp_path):
    output = tmp_path / "fitting.pdf"

    result = _build_pdf_worker(_minimal_resume(), output)

    assert result.path == output
    assert result.page_count == 1
    assert result.fitted_to_one_page is True
    assert len(PdfReader(output).pages) == 1


def test_auto_pdf_worker_reports_real_overflow_and_writes_pdf(tmp_path):
    output = tmp_path / "auto-overflow.pdf"

    result = _build_pdf_worker(_dense_resume(), output)

    assert result.fitted_to_one_page is False
    assert result.page_count == len(PdfReader(output).pages)
    assert result.page_count > 1


def test_overrides_worker_preserves_font_and_reports_real_overflow(tmp_path, monkeypatch):
    output = tmp_path / "overflow.pdf"
    requested_font_size = 8.5
    rendered_font_sizes = []
    original_render_html = _render_html

    def record_font_size(*args, **kwargs):
        rendered_font_sizes.append(kwargs["overrides"]["font_size"])
        return original_render_html(*args, **kwargs)

    monkeypatch.setattr("build_resume_pdf._render_html", record_font_size)
    result = _build_pdf_overrides_worker(
        _dense_resume(),
        output,
        {
            "font_size": requested_font_size,
            "margin": 0.4,
            "side_margin": 0.5,
            "entry_spacing": 5.0,
            "section_spacing": 6.0,
        },
    )

    assert result.fitted_to_one_page is False
    assert result.page_count == len(PdfReader(output).pages)
    assert result.page_count > 1
    assert rendered_font_sizes == [requested_font_size, requested_font_size, requested_font_size]


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
