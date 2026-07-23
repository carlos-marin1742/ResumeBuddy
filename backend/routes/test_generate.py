from unittest.mock import MagicMock

from routes.generate import (
    GenerateRequest,
    _apply_summary_variant,
    _build_tailored_resume_dict,
    _pdf_display_name,
    _pdf_storage_name,
    _persist_generation,
)
from services.claude_service import (
    TailoredBullet,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)


def _tailored_resume() -> TailoredResume:
    return TailoredResume(
        summary="Targeted summary",
        experiences=[
            TailoredExperience(
                company="Example Co",
                title="Engineer",
                tailored_bullets=[
                    TailoredBullet(
                        original="Built an API.",
                        tailored="Built a FastAPI service.",
                        keywords_injected=["FastAPI"],
                    )
                ],
            )
        ],
        projects=[
            TailoredProject(
                name="Project One",
                tailored_bullets=[
                    TailoredBullet(
                        original="Shipped a project.",
                        tailored="Shipped a React project.",
                        keywords_injected=["React"],
                    )
                ],
            )
        ],
        skills_to_highlight=["FastAPI"],
        skills_to_add={"Backend": ["FastAPI", "Python"]},
        skills_to_show=["Languages", "Backend"],
        skills_to_filter={"Languages": ["Python", "SQL", "Go"]},
        raw_response="{}",
    )


def test_build_tailored_resume_merges_content_without_dropping_metadata():
    base = {
        "contact": {"name": "Candidate"},
        "experience": [
            {
                "company": "Example Co",
                "title": "Engineer",
                "location": "Remote",
                "bullets": [{"id": "exp-1", "text": "Built an API."}],
            }
        ],
        "projects": [
            {
                "name": "Project One",
                "links": {"github": "https://example.test/repo"},
                "bullets": [{"id": "proj-1", "text": "Shipped a project."}],
            }
        ],
        "skills": [
            {"category": "Languages", "items": ["Python", "SQL", "Go", "Rust"]},
            {"category": "Backend", "items": ["Django"]},
        ],
        "ats_config": {"skills_order": ["Languages", "Backend", "Tools"]},
    }

    result = _build_tailored_resume_dict(base, _tailored_resume())

    assert result["tailored_summary"] == "Targeted summary"
    assert result["experience"][0]["location"] == "Remote"
    assert result["experience"][0]["bullets"] == [
        {
            "original": "Built an API.",
            "text": "Built a FastAPI service.",
            "keywords_injected": ["FastAPI"],
        }
    ]
    assert result["projects"][0]["links"] == {"github": "https://example.test/repo"}
    assert result["projects"][0]["bullets"][0]["text"] == "Shipped a React project."
    assert result["skills"]["Languages"] == ["Python", "SQL", "Go"]
    assert result["skills"]["Backend"] == ["Django", "FastAPI", "Python"]
    assert result["ats_config"]["skills_order"] == ["Languages", "Backend"]
    assert result["contact"] == {"name": "Candidate"}


def test_summary_variant_changes_only_the_default_summary():
    base = {
        "summary": {
            "default": "Original",
            "variants": {"backend": "Backend specialist"},
        },
        "contact": {"name": "Candidate"},
    }

    result = _apply_summary_variant(base, "backend")

    assert result["summary"]["default"] == "Backend specialist"
    assert result["summary"]["variants"] == base["summary"]["variants"]
    assert result["contact"] == base["contact"]


def test_unknown_summary_variant_preserves_resume():
    base = {"summary": {"default": "Original", "variants": {}}}

    assert _apply_summary_variant(base, "missing") is base


def test_persist_generation_maps_request_and_score_to_record():
    db = MagicMock()
    request = GenerateRequest(
        job_description="Build reliable APIs.",
        selected_keywords=["FastAPI"],
        resume_id="base_resume",
        company=" Example Co ",
        job_title=" Engineer ",
    )

    record = _persist_generation(
        db,
        request=request,
        final_resume={"tailored_summary": "Summary"},
        ats_score={"overall_score": 91, "keyword_coverage": 0.75},
        pdf_path="outputs/resume.pdf",
    )

    assert record.company == "Example Co"
    assert record.job_title == "Engineer"
    assert record.profile == "base_resume"
    assert record.ats_overall_score == 91
    assert record.ats_keyword_coverage == 0.75
    assert record.pdf_path == "outputs/resume.pdf"
    db.add.assert_called_once_with(record)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(record)


def test_pdf_names_are_safe_and_displayable():
    storage_name = _pdf_storage_name(
        "Candidate / Name",
        "Example: Co",
        "Software*Engineer",
    )

    assert "/" not in storage_name
    assert ":" not in storage_name
    assert "*" not in storage_name
    assert storage_name.endswith(".pdf")
    assert _pdf_display_name(storage_name) == (
        "Candidate Name-Example Co-SoftwareEngineer Resume.pdf"
    )
