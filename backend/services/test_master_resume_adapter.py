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
    assert profile["skills"] == {"builder_0": ["CTMS", "EDC"]}
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

    assert profile["skills"] == {"builder_0": ["CTMS", "EDC"]}


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

    assert profile["skills"]["builder_0"] == ["CTMS", "EDC", "Python"]


def test_no_adapted_skill_contains_stray_list_syntax_characters():
    profile = _profile_with_skill_items(["React", "Node.js"])

    for skill in profile["skills"]["builder_0"]:
        assert "[" not in skill
        assert "]" not in skill
        assert "'" not in skill


def test_comma_containing_skill_survives_adaptation_as_one_skill():
    profile = _profile_with_skill_items(
        ["Microsoft Office (Word, Excel, Outlook)", "Slack"]
    )

    assert profile["skills"]["builder_0"] == [
        "Microsoft Office (Word, Excel, Outlook)",
        "Slack",
    ]


def test_legacy_string_skill_items_adapt_without_error():
    profile = _profile_with_skill_items("Python, SQL")

    assert profile["skills"]["builder_0"] == ["Python", "SQL"]


def test_empty_skill_items_list_adapts_without_raising():
    profile = _profile_with_skill_items([])

    assert profile["skills"]["builder_0"] == []


def test_missing_skill_items_key_adapts_without_raising():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "skills": [{"key": "systems", "category": "Systems"}],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
    })

    assert profile["skills"]["builder_0"] == []
