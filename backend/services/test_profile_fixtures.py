import json
from pathlib import Path
from unittest.mock import patch

import pytest

from routes.extract import load_resume
from services.claude_service import (
    STANDARD_TECH_CATEGORIES,
    _occupation_descriptor,
    determine_skills_to_show,
)


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"
REQUIRED_TOP_LEVEL_KEYS = {
    "meta",
    "contact",
    "summary",
    "skills",
    "experience",
    "education",
    "certifications",
    "ats_config",
}
EXPECTED_CATEGORIES = {
    "tech_fixture": ["languages", "ai_ml", "backend", "frontend", "tools"],
    "clinical_fixture": [
        "clinical_skills",
        "patient_care",
        "systems",
        "certifications_licenses",
    ],
    "trades_fixture": ["technical_skills", "safety_compliance", "equipment"],
}


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


@pytest.mark.parametrize("name", EXPECTED_CATEGORIES)
def test_fixture_is_valid_json_with_required_top_level_keys(name):
    fixture = _load_fixture(name)

    assert REQUIRED_TOP_LEVEL_KEYS <= fixture.keys()


@pytest.mark.parametrize(("name", "categories"), EXPECTED_CATEGORIES.items())
def test_fixture_skills_use_the_expected_current_keyed_dict_shape(name, categories):
    skills = _load_fixture(name)["skills"]
    assert [group["key"] for group in skills] == categories
    assert all(group["label"] and isinstance(group["items"], list) for group in skills)


@pytest.mark.parametrize("name", ["clinical_fixture", "trades_fixture"])
def test_non_technical_fixtures_do_not_define_projects(name):
    assert not _load_fixture(name).get("projects")


def test_trades_fixture_has_no_target_roles():
    assert "target_roles" not in _load_fixture("trades_fixture")["meta"]


@pytest.mark.parametrize("name", EXPECTED_CATEGORIES)
def test_fixture_loads_through_the_existing_profile_loader(name):
    with patch("routes.extract.DATA_DIR", FIXTURES_DIR):
        assert load_resume(name) == _load_fixture(name)


@pytest.mark.parametrize(
    ("name", "occupation"),
    [
        ("tech_fixture", "Platform Engineer"),
        ("clinical_fixture", "Clinical Laboratory Technician"),
        ("trades_fixture", "Industrial Electrician Fixture"),
    ],
)
def test_fixture_occupation_uses_the_existing_profile_data_fallback_chain(name, occupation):
    assert _occupation_descriptor(_load_fixture(name)) == occupation


@pytest.mark.parametrize(
    ("name", "expected_categories"),
    [
        ("tech_fixture", ["languages", "backend"]),
        ("clinical_fixture", EXPECTED_CATEGORIES["clinical_fixture"]),
        ("trades_fixture", EXPECTED_CATEGORIES["trades_fixture"]),
    ],
)
def test_fixture_documents_current_per_role_category_filter_behavior(name, expected_categories):
    skills = _load_fixture(name)["skills"]
    result = determine_skills_to_show(
        "A backend role using FastAPI.", ["Python", "FastAPI"], skills
    )

    if name == "tech_fixture":
        assert {group["key"] for group in skills}.intersection(STANDARD_TECH_CATEGORIES)
        assert result == expected_categories
    else:
        assert not {group["key"] for group in skills}.intersection(STANDARD_TECH_CATEGORIES)
        assert set(result) == set(expected_categories)
