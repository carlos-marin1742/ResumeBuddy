import os
import subprocess
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services import build_cover_letter_pdf as cover_module
from services import build_resume_pdf as resume_module
from services import pdf_concurrency
from services.pdf_concurrency import PdfBusyError, PdfRenderTimeoutError


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


class _HangingBrowser:
    """A Playwright double whose page.pdf blocks until its Chromium is killed."""

    def __init__(self, hang_seconds: float = 5.0):
        self.hang_seconds = hang_seconds
        self.killed = threading.Event()
        self.launch_args = None
        self.browser = MagicMock()
        page = MagicMock()
        page.pdf.side_effect = self._pdf
        self.browser.new_page.return_value = page
        playwright = MagicMock()
        playwright.chromium.launch.side_effect = self._launch
        self.manager = MagicMock()
        self.manager.__enter__.return_value = playwright

    def _launch(self, **kwargs):
        self.launch_args = kwargs["args"]
        return self.browser

    def _pdf(self, path, **kwargs):
        open(path, "wb").write(b"partial")
        # Like a real Playwright call, this only fails once its browser dies.
        if not self.killed.wait(timeout=self.hang_seconds):
            raise RuntimeError("render was never killed")
        raise RuntimeError("Target closed")

    def kill(self, token):
        assert any(token in arg for arg in self.launch_args)  # the tagged browser
        self.killed.set()
        return 1


@pytest.fixture
def short_timeouts(monkeypatch):
    monkeypatch.setattr(pdf_concurrency, "PDF_RENDER_TIMEOUT_SECONDS", 0.3)
    monkeypatch.setattr(pdf_concurrency, "_KILL_GRACE_SECONDS", 2.0)


def test_hung_render_is_killed_then_slot_frees_and_next_render_succeeds(limit, short_timeouts, monkeypatch, tmp_path):
    limit(1, timeout=0.5)
    hung = _HangingBrowser()
    monkeypatch.setattr(pdf_concurrency, "_kill_render_processes", hung.kill)

    begun = time.monotonic()
    with patch("playwright.sync_api.sync_playwright", return_value=hung.manager):
        with pytest.raises(PdfRenderTimeoutError, match="timed out"):
            cover_module.build_cover_letter_pdf("hi", tmp_path / "hung.pdf")
    assert time.monotonic() - begun < 4

    assert hung.killed.is_set()
    hung.browser.close.assert_called_once()
    assert list(tmp_path.iterdir()) == []  # no partial or temp PDF left behind

    # A leaked slot would make this wait out the 0.5s queue timeout and raise PdfBusyError.
    page = MagicMock()
    page.pdf.side_effect = lambda path, **kwargs: open(path, "wb").write(b"%PDF-1.4 ok")
    healthy, browser = _fake_playwright(page)
    with patch("playwright.sync_api.sync_playwright", return_value=healthy):
        result = cover_module.build_cover_letter_pdf("hi", tmp_path / "ok.pdf")
    assert result.read_bytes() == b"%PDF-1.4 ok"
    assert [path.name for path in tmp_path.iterdir()] == ["ok.pdf"]


def test_hung_resume_render_times_out_and_removes_temp_pdf(limit, short_timeouts, monkeypatch, tmp_path):
    limit(1, timeout=0.5)
    hung = _HangingBrowser()
    monkeypatch.setattr(pdf_concurrency, "_kill_render_processes", hung.kill)
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()
    monkeypatch.setattr("tempfile.tempdir", str(temp_dir))

    with patch("playwright.sync_api.sync_playwright", return_value=hung.manager):
        with pytest.raises(PdfRenderTimeoutError):
            resume_module.build_pdf({"contact": {}}, tmp_path / "out.pdf")

    assert list(temp_dir.iterdir()) == []
    assert not (tmp_path / "out.pdf").exists()


def test_render_that_finishes_in_time_is_not_killed(limit, monkeypatch, tmp_path):
    limit(1)
    killed = []
    monkeypatch.setattr(pdf_concurrency, "_kill_render_processes", lambda token: killed.append(token))
    monkeypatch.setattr(cover_module, "_build_cover_letter_pdf_worker", lambda *a, **k: "done")

    assert cover_module.build_cover_letter_pdf("hi", tmp_path / "x.pdf") == "done"
    assert killed == []


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the watchdog reads /proc")
def test_kill_render_processes_kills_tagged_tree_and_spares_others():
    token = "unit-test-token"
    sleeper = [sys.executable, "-c", "import time; time.sleep(60)"]
    tagged = subprocess.Popen(sleeper + [f"--{pdf_concurrency._MARKER_SWITCH}={token}"])
    # A child of the tagged process stands in for Chromium's renderer/GPU processes.
    parent = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)",
         f"--{pdf_concurrency._MARKER_SWITCH}={token}-parent"]
    )
    other = subprocess.Popen(sleeper + [f"--{pdf_concurrency._MARKER_SWITCH}=other-render"])
    try:
        time.sleep(0.5)  # let the grandchild start
        assert pdf_concurrency._kill_render_processes(f"{token}-parent") == 2
        assert pdf_concurrency._kill_render_processes(token) == 1
        assert tagged.wait(timeout=5) == -9
        assert parent.wait(timeout=5) == -9
        assert other.poll() is None
    finally:
        for process in (tagged, parent, other):
            process.kill()
            process.wait()


def test_route_maps_render_timeout_to_503_with_timeout_message(tmp_path):
    client = TestClient(app)
    body = {"letter": "Hello", "candidate_name": "A", "company": "B", "job_title": "C"}
    with patch("routes.cover_letter.build_cover_letter_pdf", side_effect=PdfRenderTimeoutError("slow")),             patch("routes.cover_letter.OUTPUTS_DIR", tmp_path):
        response = client.post("/api/download-cover-letter", json=body)

    assert response.status_code == 503
    assert response.headers["retry-after"]
    assert "timed out" in response.json()["detail"].lower()
