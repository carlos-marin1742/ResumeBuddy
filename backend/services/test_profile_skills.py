from services.profile_skills import normalize_profile_skills


def test_normalize_profile_skills_keeps_legacy_order_and_array_labels():
    legacy = normalize_profile_skills(
        {"backend": ["FastAPI"], "languages": ["Python"]},
        ["languages", "backend"],
    )
    assert legacy == [
        {"key": "languages", "label": "languages", "items": ["Python"]},
        {"key": "backend", "label": "backend", "items": ["FastAPI"]},
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
        {"key": "languages", "label": "languages", "items": ["Python"]}
    ]
