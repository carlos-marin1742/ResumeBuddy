import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services import build_cover_letter_pdf as cover_module
from services import build_resume_pdf as resume_module
from services import pdf_concurrency
from services.pdf_concurrency import PdfBusyError


@pytest.fixture
def limit(monkeypatch):
    """Install a render limit of N slots and a queue timeout for one test."""
    def configure(slots: int, timeout: float = 10.0):
        monkeypatch.setattr(pdf_concurrency, "_render_slots", threading.BoundedSemaphore(slots))
        monkeypatch.setattr(pdf_concurrency, "PDF_QUEUE_TIMEOUT_SECONDS", timeout)
    return configure


class _ActiveCounter:
    """Stands in for a Chromium render and records peak simultaneous renders."""

    def __init__(self, hold: float = 0.05):
        self.hold = hold
        self.active = 0
        self.peak = 0
        self.finished = 0
        self._lock = threading.Lock()

    def render(self, *args, **kwargs):
        with self._lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(self.hold)
        with self._lock:
            self.active -= 1
            self.finished += 1
        return object()


def test_parallel_resume_and_cover_letter_renders_never_exceed_limit(limit, monkeypatch, tmp_path):
    limit(2)
    counter = _ActiveCounter()
    monkeypatch.setattr(resume_module, "_build_pdf_worker", counter.render)
    monkeypatch.setattr(resume_module, "_build_pdf_overrides_worker", counter.render)
    monkeypatch.setattr(cover_module, "_build_cover_letter_pdf_worker", counter.render)
    calls = [
        lambda: resume_module.build_pdf({}, tmp_path / "a.pdf"),
        lambda: resume_module.build_pdf_with_overrides({}, tmp_path / "b.pdf", {}),
        lambda: cover_module.build_cover_letter_pdf("hi", tmp_path / "c.pdf"),
    ] * 4  # 12 callers share the one limit

    threads = [threading.Thread(target=call) for call in calls]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert counter.finished == 12
    assert counter.peak == 2


def test_slot_is_released_after_a_render_error(limit, monkeypatch, tmp_path):
    limit(1, timeout=1.0)

    def explode(*args, **kwargs):
        raise RuntimeError("chromium crashed")

    monkeypatch.setattr(cover_module, "_build_cover_letter_pdf_worker", explode)
    with pytest.raises(RuntimeError, match="chromium crashed"):
        cover_module.build_cover_letter_pdf("hi", tmp_path / "x.pdf")

    monkeypatch.setattr(cover_module, "_build_cover_letter_pdf_worker", lambda *a, **k: "ok")
    # A leaked slot would make this wait out the 1s timeout and raise PdfBusyError.
    assert cover_module.build_cover_letter_pdf("hi", tmp_path / "x.pdf") == "ok"


def test_waiting_past_the_queue_timeout_raises_busy(limit, monkeypatch, tmp_path):
    limit(1, timeout=0.2)
    started, release = threading.Event(), threading.Event()

    def blocking(*args, **kwargs):
        started.set()
        release.wait(timeout=10)

    monkeypatch.setattr(cover_module, "_build_cover_letter_pdf_worker", blocking)
    holder = threading.Thread(target=cover_module.build_cover_letter_pdf, args=("hi", tmp_path / "h.pdf"))
    holder.start()
    try:
        assert started.wait(timeout=5)
        begun = time.monotonic()
        with pytest.raises(PdfBusyError):
            resume_module.build_pdf({}, tmp_path / "w.pdf")
        assert time.monotonic() - begun < 5
    finally:
        release.set()
        holder.join(timeout=10)


@pytest.mark.parametrize(
    "target, url, body",
    [
        ("routes.cover_letter.build_cover_letter_pdf", "/api/download-cover-letter",
         {"letter": "Hello", "candidate_name": "A", "company": "B", "job_title": "C"}),
    ],
)
def test_route_maps_busy_to_503_not_500(target, url, body, tmp_path):
    client = TestClient(app)
    with patch(target, side_effect=PdfBusyError("busy")), patch("routes.cover_letter.OUTPUTS_DIR", tmp_path):
        response = client.post(url, json=body)

    assert response.status_code == 503
    assert response.headers["retry-after"]
    assert "busy" in response.json()["detail"].lower()


def _fake_playwright(page):
    browser = MagicMock()
    browser.new_page.return_value = page
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    manager = MagicMock()
    manager.__enter__.return_value = playwright
    return manager, browser


@pytest.mark.parametrize("worker_name, extra_args", [
    ("_build_pdf_worker", ()),
    ("_build_pdf_overrides_worker", ({},)),
])
def test_resume_workers_close_browser_and_remove_temp_pdf_on_error(worker_name, extra_args, tmp_path):
    page = MagicMock()
    leaked = []

    def failing_pdf(path, **kwargs):
        leaked.append(path)
        open(path, "wb").write(b"partial")
        raise RuntimeError("render blew up")

    page.pdf.side_effect = failing_pdf
    manager, browser = _fake_playwright(page)

    with patch("playwright.sync_api.sync_playwright", return_value=manager):
        with pytest.raises(RuntimeError, match="render blew up"):
            getattr(resume_module, worker_name)({"contact": {}}, tmp_path / "out.pdf", *extra_args)

    browser.close.assert_called_once()
    assert leaked and not __import__("os").path.exists(leaked[0])
