import pytest

from services.master_resume_adapter import master_resume_to_profile, split_skill_items


def _skills_by_key(profile):
    return {group["key"]: group["items"] for group in profile["skills"]}


# Shared with client/src/components/ResumeBuilder.test.jsx's splitSkillItems
# fixture list. The two splitters are pinned together by this identical
# input/output list rather than shared code, since the boundary is JS/Python.
SKILL_ITEMS_FIXTURES = [
    ("React, TypeScript, Vite", ["React", "TypeScript", "Vite"]),
    (
        "Microsoft Office (Word, Excel, Outlook)",
        ["Microsoft Office (Word, Excel, Outlook)"],
    ),
    (
        "Phlebotomy, adult and pediatric\nVenipuncture",
        ["Phlebotomy, adult and pediatric", "Venipuncture"],
    ),
    (
        "IV Insertion [peripheral, central], Wound Care",
        ["IV Insertion [peripheral, central]", "Wound Care"],
    ),
    ("Python,,SQL", ["Python", "SQL"]),
    ("  React ,  Vite  ", ["React", "Vite"]),
    (", ", []),
    ("", []),
]


@pytest.mark.parametrize("raw, expected", SKILL_ITEMS_FIXTURES)
def test_split_skill_items_matches_shared_fixture(raw, expected):
    assert split_skill_items(raw) == expected


def test_master_resume_adapter_preserves_experience_bullets_and_builder_fields():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "targetRole": "Research Resume",
        "targetJobTitle": "Clinical AI Engineer",
        "summary": "Clinical research professional.",
        "skills": [{"category": "Systems", "items": "CTMS, EDC"}],
        "experience": [{
            "company": "Example Hospital",
            "title": "Research Coordinator",
            "location": "Houston, TX",
            "startDate": "2023-01",
            "endDate": "",
            "highlights": "Managed trials.\nResolved queries.",
        }],
        "education": [{
            "institution": "State University",
            "degree": "B.S.",
            "field": "Biology",
            "graduationDate": "2017",
        }],
        "projects": [],
        "certifications": [{"name": "GCP", "issuer": "CITI", "date": ""}],
    })

    assert profile["summary"]["default"] == "Clinical research professional."
    assert profile["meta"] == {
        "label": "Research Resume",
        "occupation": "Clinical AI Engineer",
        "target_roles": [],
    }
    assert profile["skills"] == [{"key": "systems", "label": "Systems", "items": ["CTMS", "EDC"]}]
    assert [bullet["text"] for bullet in profile["experience"][0]["bullets"]] == [
        "Managed trials.",
        "Resolved queries.",
    ]
    assert profile["education"][0]["graduation_date"] == "2017"
    assert profile["certifications"][0]["name"] == "GCP"


def test_master_resume_adapter_accepts_array_skill_items():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "skills": [{"key": "systems", "category": "Systems", "items": ["CTMS", "EDC"]}],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
    })

    assert profile["skills"] == [{"key": "systems", "label": "Systems", "items": ["CTMS", "EDC"]}]


def _profile_with_skill_items(items):
    return master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "skills": [{"key": "systems", "category": "Systems", "items": items}],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
    })


def test_array_skill_items_adapt_as_separate_entries_not_a_stringified_list():
    profile = _profile_with_skill_items(["CTMS", "EDC", "Python"])

    assert _skills_by_key(profile)["systems"] == ["CTMS", "EDC", "Python"]


def test_no_adapted_skill_contains_stray_list_syntax_characters():
    profile = _profile_with_skill_items(["React", "Node.js"])

    for skill in _skills_by_key(profile)["systems"]:
        assert "[" not in skill
        assert "]" not in skill
        assert "'" not in skill


def test_comma_containing_skill_survives_adaptation_as_one_skill():
    profile = _profile_with_skill_items(
        ["Microsoft Office (Word, Excel, Outlook)", "Slack"]
    )

    assert _skills_by_key(profile)["systems"] == [
        "Microsoft Office (Word, Excel, Outlook)",
        "Slack",
    ]


def test_legacy_string_skill_items_adapt_without_error():
    profile = _profile_with_skill_items("Python, SQL")

    assert _skills_by_key(profile)["systems"] == ["Python", "SQL"]


def test_empty_skill_items_list_adapts_without_raising():
    profile = _profile_with_skill_items([])

    assert _skills_by_key(profile)["systems"] == []


def test_missing_skill_items_key_adapts_without_raising():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "skills": [{"key": "systems", "category": "Systems"}],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
    })

    assert _skills_by_key(profile)["systems"] == []


def test_already_slugged_skill_group_key_is_unchanged():
    profile = master_resume_to_profile({
        "skills": [{"key": "clinical_platforms", "category": "Clinical Tools", "items": ["CTMS"]}],
    })

    assert profile["skills"] == [{"key": "clinical_platforms", "label": "Clinical Tools", "items": ["CTMS"]}]


@pytest.mark.parametrize(
    ("key", "expected_key"),
    [
        ("Languages", "languages"),
        ("Clinical Skills", "clinical_skills"),
    ],
)
def test_display_style_skill_group_key_is_slugged(key, expected_key):
    profile = master_resume_to_profile({
        "skills": [{"key": key, "category": key, "items": ["Example"]}],
    })

    assert profile["skills"] == [
        {"key": expected_key, "label": key, "items": ["Example"]}
    ]


def test_reordering_skill_groups_keeps_their_profile_keys():
    groups = [
        {"key": "clinical_skills", "category": "Clinical Skills", "items": ["CTMS"]},
        {"key": "tools", "category": "Tools", "items": ["Excel"]},
    ]

    first = master_resume_to_profile({"skills": groups})
    reordered = master_resume_to_profile({"skills": list(reversed(groups))})

    assert [group["key"] for group in first["skills"]] == ["clinical_skills", "tools"]
    assert [group["key"] for group in reordered["skills"]] == ["tools", "clinical_skills"]


def test_deleting_a_middle_skill_group_keeps_remaining_profile_keys():
    groups = [
        {"key": "clinical_skills", "category": "Clinical Skills", "items": ["CTMS"]},
        {"key": "tools", "category": "Tools", "items": ["Excel"]},
        {"key": "certifications", "category": "Certifications", "items": ["GCP"]},
    ]

    profile = master_resume_to_profile({"skills": [groups[0], groups[2]]})

    assert [group["key"] for group in profile["skills"]] == ["clinical_skills", "certifications"]


def test_missing_key_falls_back_to_an_underscore_category_slug():
    profile = master_resume_to_profile({
        "skills": [{"category": "Clinical & Patient Care", "items": ["Venipuncture"]}],
    })

    assert profile["skills"] == [{"key": "clinical_patient_care", "label": "Clinical & Patient Care", "items": ["Venipuncture"]}]


def test_missing_key_and_category_uses_unique_index_fallback_and_keeps_items():
    profile = master_resume_to_profile({
        "skills": [
            {"category": "", "items": ["Venipuncture"]},
            {"items": ["Specimen handling"]},
        ],
    })

    assert profile["skills"] == [
        {"key": "skill_0", "label": "skill_0", "items": ["Venipuncture"]},
        {"key": "skill_1", "label": "skill_1", "items": ["Specimen handling"]},
    ]


def test_colliding_derived_skill_keys_get_numeric_suffixes():
    profile = master_resume_to_profile({
        "skills": [
            {"key": "systems", "category": "Systems", "items": ["CTMS"]},
            {"key": "systems", "category": "Other Systems", "items": ["EDC"]},
        ],
    })

    assert profile["skills"] == [
        {"key": "systems", "label": "Systems", "items": ["CTMS"]},
        {"key": "systems_2", "label": "Other Systems", "items": ["EDC"]},
    ]


def test_legacy_groups_without_key_fields_adapt_without_error():
    profile = master_resume_to_profile({
        "skills": [
            {"category": "Systems", "items": ["CTMS"]},
            {"category": "Clinical Skills", "items": ["GCP"]},
        ],
    })

    assert profile["skills"] == [
        {"key": "systems", "label": "Systems", "items": ["CTMS"]},
        {"key": "clinical_skills", "label": "Clinical Skills", "items": ["GCP"]},
    ]


def test_adapter_preserves_distinct_skill_key_and_label():
    profile = master_resume_to_profile({
        "skills": [{"key": "systems", "category": "Systems", "items": ["CTMS"]}],
    })

    assert profile["skills"] == [
        {"key": "systems", "label": "Systems", "items": ["CTMS"]}
    ]
    assert "skills_order" not in profile["ats_config"]
