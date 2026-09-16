from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from routes.generate import GenerateRequest, generate_resume
from services.build_resume_pdf import PdfBuildResult
from services.claude_service import TailoredBullet, TailoredProject, TailoredResume
from services.project_selection import MAX_PROJECTS


def test_generate_route_passes_at_most_max_projects_to_tailoring(tmp_path):
    projects = [
        {"name": f"Project {index}", "bullets": [{"text": "Built APIs."}]}
        for index in range(MAX_PROJECTS + 1)
    ]
    tailored = TailoredResume(
        summary="Summary",
        experiences=[],
        projects=[TailoredProject(
            name=project["name"],
            tailored_bullets=[TailoredBullet(
                original="Built APIs.", tailored="Built APIs.", keywords_injected=[]
            )],
        ) for project in projects[:MAX_PROJECTS]],
        skills_to_highlight=[],
        skills_to_add={},
        skills_to_show=[],
        skills_to_filter={},
        raw_response="{}",
    )
    score = MagicMock(
        overall_score=90,
        keyword_coverage=0.8,
        matched_keywords=[],
        missing_keywords=[],
        suggestions=[],
    )
    score.model_dump.return_value = {"overall_score": 90, "keyword_coverage": 0.8}

    with (
        patch("routes.generate._load_resume", return_value={"contact": {"name": "Candidate"}, "projects": projects}),
        patch("routes.generate.tailor_resume", return_value=tailored) as tailor,
        patch("routes.generate.score_resume", return_value=score),
        patch("routes.generate.build_pdf", return_value=PdfBuildResult(tmp_path / "resume.pdf", 1, True)),
        patch("routes.generate._persist_generation", return_value=SimpleNamespace(id="history-1")),
    ):
        generate_resume(GenerateRequest(job_description="Build APIs"), MagicMock())

    assert len(tailor.call_args.kwargs["base_resume"]["projects"]) == MAX_PROJECTS
