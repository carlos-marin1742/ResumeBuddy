import copy
import json
from pathlib import Path

import pytest

from build_resume_pdf import _render_html
from claude_service import TailoredResume, determine_skills_to_add
from routes.generate import _build_tailored_resume_dict
from test_profile_skills_golden import _assert_skills_html_matches_golden


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"

# Tech exercises existing, mapped-existing, mapped-absent, and unmapped cases.
# Java creates a fourth Languages item so skills_to_filter can remove it while
# preserving the three-item minimum required by the merge behavior.
GENERATION_CASES = [
    (
        "tech_fixture",
        ["Python", "SQL", "Java", "Kubernetes", "Event Sourcing"],
        ["languages", "backend"],
        {"languages": ["Python", "TypeScript", "SQL"]},
    ),
    # A mapped-existing case is unrepresentable here: SKILL_TO_CATEGORY has no
    # target for clinical_skills, patient_care, systems, or certifications_licenses.
    # Injection retargeting onto user-defined categories will change this behavior.
    ("clinical_fixture", ["Venipuncture", "Python", "Specimen Workflow"], [], {}),
    # A mapped-existing case is unrepresentable here: SKILL_TO_CATEGORY has no
    # target for technical_skills, safety_compliance, or equipment. Injection
    # retargeting onto user-defined categories will change this behavior.
    ("trades_fixture", ["OSHA-10", "Python", "Arc Flash Analysis"], [], {}),
]


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


def _skills_section(html: str) -> str:
    skills_start = "<div class='section'><div class='section-title'>SKILLS</div>"
    _, separator, after_skills = html.partition(skills_start)
    assert separator, "Rendered resume did not contain a SKILLS section."
    skills_body, _, _ = after_skills.partition("<div class='section'>")
    return skills_start + skills_body.removesuffix("</div>")


def _tailored_resume(
    resume: dict,
    selected_keywords: list[str],
    *,
    skills_to_show: list[str] | None = None,
    skills_to_filter: dict[str, list[str]] | None = None,
) -> TailoredResume:
    return TailoredResume(
        summary=resume["summary"]["default"],
        experiences=[],
        projects=[],
        skills_to_highlight=[],
        skills_to_add=determine_skills_to_add(resume["skills"], selected_keywords),
        skills_to_show=skills_to_show or [],
        skills_to_filter=skills_to_filter or {},
        raw_response="generation golden fixture",
    )


@pytest.mark.parametrize(
    ("name", "selected_keywords", "skills_to_show", "skills_to_filter"),
    GENERATION_CASES,
)
def test_generation_skills_html_matches_current_golden(
    name,
    selected_keywords,
    skills_to_show,
    skills_to_filter,
):
    resume = copy.deepcopy(_load_fixture(name))
    tailored = _tailored_resume(
        resume,
        selected_keywords,
        skills_to_show=skills_to_show,
        skills_to_filter=skills_to_filter,
    )

    generated = _build_tailored_resume_dict(resume, tailored)
    actual = _skills_section(_render_html(generated))

    _assert_skills_html_matches_golden(
        name, actual, f"{name}_generated_skills.html"
    )
