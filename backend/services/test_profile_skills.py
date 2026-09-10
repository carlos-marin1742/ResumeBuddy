from services.profile_skills import normalize_profile_skills


def test_normalize_profile_skills_keeps_legacy_order_and_array_labels():
    legacy = normalize_profile_skills(
        {"backend": ["FastAPI"], "languages": ["Python"]},
        ["languages", "backend"],
    )
    assert legacy == [
        {"key": "languages", "label": "Languages", "items": ["Python"]},
        {"key": "backend", "label": "Backend", "items": ["FastAPI"]},
    ]

    ordered = normalize_profile_skills([
        {"key": "systems", "label": "Clinical Systems", "items": ["CTMS"]}
    ])
    assert ordered == [
        {"key": "systems", "label": "Clinical Systems", "items": ["CTMS"]}
    ]


def test_normalize_profile_skills_respects_legacy_skills_order():
    groups = normalize_profile_skills(
        {"languages": ["Python"], "tools": ["Git"]}, ["languages"]
    )
    assert groups == [
        {"key": "languages", "label": "Languages", "items": ["Python"]}
    ]


def test_normalize_profile_skills_slugs_display_style_legacy_dict_keys():
    groups = normalize_profile_skills({"Clinical Skills": ["Venipuncture"]})

    assert groups == [
        {
            "key": "clinical_skills",
            "label": "Clinical Skills",
            "items": ["Venipuncture"],
        }
    ]


def test_array_group_without_label_falls_back_to_its_key_in_renderer():
    from services.build_resume_pdf import _render_html

    html = _render_html({"skills": [{"key": "custom_tools", "items": ["Tool"]}]})
    assert "custom_tools:" in html
