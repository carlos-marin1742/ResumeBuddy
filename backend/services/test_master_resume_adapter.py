import pytest

from services.master_resume_adapter import master_resume_to_profile, split_skill_items


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
    assert profile["skills"] == {"systems": ["CTMS", "EDC"]}
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

    assert profile["skills"] == {"systems": ["CTMS", "EDC"]}


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

    assert profile["skills"]["systems"] == ["CTMS", "EDC", "Python"]


def test_no_adapted_skill_contains_stray_list_syntax_characters():
    profile = _profile_with_skill_items(["React", "Node.js"])

    for skill in profile["skills"]["systems"]:
        assert "[" not in skill
        assert "]" not in skill
        assert "'" not in skill


def test_comma_containing_skill_survives_adaptation_as_one_skill():
    profile = _profile_with_skill_items(
        ["Microsoft Office (Word, Excel, Outlook)", "Slack"]
    )

    assert profile["skills"]["systems"] == [
        "Microsoft Office (Word, Excel, Outlook)",
        "Slack",
    ]


def test_legacy_string_skill_items_adapt_without_error():
    profile = _profile_with_skill_items("Python, SQL")

    assert profile["skills"]["systems"] == ["Python", "SQL"]


def test_empty_skill_items_list_adapts_without_raising():
    profile = _profile_with_skill_items([])

    assert profile["skills"]["systems"] == []


def test_missing_skill_items_key_adapts_without_raising():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "skills": [{"key": "systems", "category": "Systems"}],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
    })

    assert profile["skills"]["systems"] == []


def test_skill_group_key_is_used_verbatim_when_it_differs_from_category_slug():
    profile = master_resume_to_profile({
        "skills": [{"key": "clinical_platforms", "category": "Clinical Tools", "items": ["CTMS"]}],
    })

    assert profile["skills"] == {"clinical_platforms": ["CTMS"]}


def test_reordering_skill_groups_keeps_their_profile_keys():
    groups = [
        {"key": "clinical_skills", "category": "Clinical Skills", "items": ["CTMS"]},
        {"key": "tools", "category": "Tools", "items": ["Excel"]},
    ]

    first = master_resume_to_profile({"skills": groups})
    reordered = master_resume_to_profile({"skills": list(reversed(groups))})

    assert set(first["skills"]) == {"clinical_skills", "tools"}
    assert set(reordered["skills"]) == {"clinical_skills", "tools"}


def test_deleting_a_middle_skill_group_keeps_remaining_profile_keys():
    groups = [
        {"key": "clinical_skills", "category": "Clinical Skills", "items": ["CTMS"]},
        {"key": "tools", "category": "Tools", "items": ["Excel"]},
        {"key": "certifications", "category": "Certifications", "items": ["GCP"]},
    ]

    profile = master_resume_to_profile({"skills": [groups[0], groups[2]]})

    assert set(profile["skills"]) == {"clinical_skills", "certifications"}


def test_missing_key_falls_back_to_an_underscore_category_slug():
    profile = master_resume_to_profile({
        "skills": [{"category": "Clinical & Patient Care", "items": ["Venipuncture"]}],
    })

    assert profile["skills"] == {"clinical_patient_care": ["Venipuncture"]}


def test_missing_key_and_category_uses_unique_index_fallback_and_keeps_items():
    profile = master_resume_to_profile({
        "skills": [
            {"category": "", "items": ["Venipuncture"]},
            {"items": ["Specimen handling"]},
        ],
    })

    assert profile["skills"] == {
        "skill_0": ["Venipuncture"],
        "skill_1": ["Specimen handling"],
    }


def test_colliding_derived_skill_keys_get_numeric_suffixes():
    profile = master_resume_to_profile({
        "skills": [
            {"key": "systems", "category": "Systems", "items": ["CTMS"]},
            {"key": "systems", "category": "Other Systems", "items": ["EDC"]},
        ],
    })

    assert profile["skills"] == {"systems": ["CTMS"], "systems_2": ["EDC"]}


def test_legacy_groups_without_key_fields_adapt_without_error():
    profile = master_resume_to_profile({
        "skills": [
            {"category": "Systems", "items": ["CTMS"]},
            {"category": "Clinical Skills", "items": ["GCP"]},
        ],
    })

    assert profile["skills"] == {"systems": ["CTMS"], "clinical_skills": ["GCP"]}


def test_adapter_does_not_write_unread_skill_labels():
    profile = master_resume_to_profile({
        "skills": [{"key": "systems", "category": "Systems", "items": ["CTMS"]}],
    })

    assert "skill_labels" not in profile["ats_config"]
