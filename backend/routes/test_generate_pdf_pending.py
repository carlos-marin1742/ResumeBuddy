"""A busy or failing PDF render must never discard a completed generation."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import db as db_module
import main
from models import TailoredResumeRecord, User
from routes.test_generate import _tailored_resume
from services.build_resume_pdf import PdfBuildResult
from services.pdf_concurrency import PdfBusyError, PdfRenderTimeoutError

USER_ID = "user-1"


@pytest.fixture
def session(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine, tables=[TailoredResumeRecord.__table__, User.__table__])
    with Session(engine) as db:
        def override():
            yield db

        main.app.dependency_overrides[db_module.get_session] = override
        monkeypatch.setattr(main, "get_current_user", lambda request, s: SimpleNamespace(id=USER_ID))
        yield db
    main.app.dependency_overrides.pop(db_module.get_session, None)


def _score():
    score = MagicMock(
        overall_score=90, keyword_coverage=0.8, matched_keywords=["FastAPI"],
        missing_keywords=[], suggestions=[],
    )
    score.model_dump.return_value = {"overall_score": 90, "keyword_coverage": 0.8}
    return score


def _generate(client, build_pdf):
    base_resume = {"contact": {"name": "Candidate"}, "projects": []}
    with (
        patch("routes.generate._load_resume", return_value=base_resume),
        patch("routes.generate.tailor_resume", return_value=_tailored_resume()),
        patch("routes.generate.score_resume", return_value=_score()),
        patch("routes.generate.build_pdf", side_effect=build_pdf),
    ):
        return client.post(
            "/api/generate-resume",
            json={"job_description": "Build APIs", "selected_keywords": ["FastAPI"],
                  "company": "Acme", "job_title": "Engineer"},
        )


def _busy(*args, **kwargs):
    raise PdfBusyError("busy")


def test_busy_queue_keeps_result_and_record_then_downloads_once_free(session, tmp_path):
    client = TestClient(main.app)
    with patch("routes.generate.OUTPUTS_DIR", tmp_path), patch("routes.history.OUTPUTS_DIR", tmp_path):
        response = _generate(client, _busy)

        assert response.status_code == 200
        body = response.json()
        assert body["pdf_url"] is None
        assert body["pdf_status"] == "pending"
        assert body["pdf_page_count"] is None and body["pdf_fitted_to_one_page"] is None
        assert body["summary"] == "Targeted summary"
        record = session.exec(select(TailoredResumeRecord)).one()
        assert record.id == body["history_id"]
        assert record.pdf_path is None
        assert record.tailored_resume["contact"]["name"] == "Candidate"

        # Still busy: the download answers 503 with Retry-After, never a 500.
        with patch("routes.generate.build_pdf", side_effect=_busy):
            busy = client.get(f"/api/download-history/{record.id}")
        assert busy.status_code == 503 and busy.headers["retry-after"]

        # Queue frees up: the same record renders on demand and is cached.
        def render(resume_data, output_path):
            output_path.write_bytes(b"%PDF-1.4 test")
            return PdfBuildResult(output_path, 1, True)

        with patch("routes.generate.build_pdf", side_effect=render) as build:
            ok = client.get(f"/api/download-history/{record.id}")
            again = client.get(f"/api/download-history/{record.id}")

    assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
    assert again.status_code == 200
    assert build.call_count == 1  # second download used the cached file
    session.refresh(record)
    assert record.pdf_path


def test_render_error_also_keeps_result_as_pending(session, tmp_path):
    def explode(*args, **kwargs):
        raise RuntimeError("chromium crashed")

    with patch("routes.generate.OUTPUTS_DIR", tmp_path):
        response = _generate(TestClient(main.app), explode)

    assert response.status_code == 200
    assert response.json()["pdf_status"] == "pending"
    assert session.exec(select(TailoredResumeRecord)).one().pdf_path is None


def test_successful_render_reports_ready_and_caches_path(session, tmp_path):
    def render(resume_data, output_path):
        output_path.write_bytes(b"%PDF-1.4 test")
        return PdfBuildResult(output_path, 1, True)

    with patch("routes.generate.OUTPUTS_DIR", tmp_path):
        body = _generate(TestClient(main.app), render).json()

    assert body["pdf_status"] == "ready"
    assert body["pdf_url"].startswith("/api/download/")
    assert body["pdf_page_count"] == 1 and body["pdf_fitted_to_one_page"] is True
    assert session.exec(select(TailoredResumeRecord)).one().pdf_path


def test_timed_out_render_keeps_result_pending_and_download_answers_503(session, tmp_path):
    def hung(*args, **kwargs):
        raise PdfRenderTimeoutError("timed out")

    client = TestClient(main.app)
    with patch("routes.generate.OUTPUTS_DIR", tmp_path), patch("routes.history.OUTPUTS_DIR", tmp_path):
        response = _generate(client, hung)
        assert response.status_code == 200
        assert response.json()["pdf_url"] is None
        assert response.json()["pdf_status"] == "pending"
        record = session.exec(select(TailoredResumeRecord)).one()
        assert record.pdf_path is None

        with patch("routes.generate.build_pdf", side_effect=hung):
            timed_out = client.get(f"/api/download-history/{record.id}")

    assert timed_out.status_code == 503 and timed_out.headers["retry-after"]
    assert "timed out" in timed_out.json()["detail"].lower()
