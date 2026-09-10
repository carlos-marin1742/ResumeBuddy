import copy
import difflib
import json
import os
from pathlib import Path

import pytest

from build_resume_pdf import _render_html
from claude_service import determine_skills_to_show


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
UPDATE_GOLDENS_ENV = "UPDATE_SKILLS_HTML_GOLDENS"

FILTER_INPUT = {
    "job_description": "A backend role using FastAPI.",
    "selected_keywords": ["Python", "FastAPI"],
}
EXPECTED_VISIBLE_CATEGORIES = {
    "tech_fixture": ["languages", "backend"],
    "clinical_fixture": ["clinical_skills", "patient_care"],
    "trades_fixture": ["technical_skills", "safety_compliance"],
}


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _render_fixture_skills(name: str) -> tuple[str, list[str]]:
    resume = copy.deepcopy(_load_fixture(name))
    visible_categories = determine_skills_to_show(
        FILTER_INPUT["job_description"],
        FILTER_INPUT["selected_keywords"],
        resume["skills"],
    )
    resume["skills"] = [
        group for group in resume["skills"]
        if group["key"] in visible_categories
    ]
    html = _render_html(resume)

    skills_start = "<div class='section'><div class='section-title'>SKILLS</div>"
    _, separator, after_skills = html.partition(skills_start)
    assert separator, "Rendered resume did not contain a SKILLS section."
    skills_body, _, _ = after_skills.partition("<div class='section'>")
    return skills_start + skills_body.removesuffix("</div>"), visible_categories


def _assert_skills_html_matches_golden(name: str, actual: str, golden_name: str) -> None:
    golden_path = GOLDEN_DIR / golden_name
    if os.environ.get(UPDATE_GOLDENS_ENV) == "1":
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")

    # Goldens may use the conventional final newline while the renderer returns
    # the section as a fragment without one; it is not rendered HTML content.
    expected = golden_path.read_text(encoding="utf-8").rstrip("\r\n")
    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=str(golden_path),
            tofile=f"rendered/{golden_name}",
        )
    )
    assert actual == expected, f"Skills HTML golden mismatch:\n{diff}"


@pytest.mark.parametrize("name", EXPECTED_VISIBLE_CATEGORIES)
def test_fixture_skills_html_matches_current_golden(name):
    actual, visible_categories = _render_fixture_skills(name)
    fixture_categories = [group["key"] for group in _load_fixture(name)["skills"]]

    assert visible_categories == EXPECTED_VISIBLE_CATEGORIES[name]
    assert set(visible_categories) <= set(fixture_categories)

    _assert_skills_html_matches_golden(name, actual, f"{name}_skills.html")
