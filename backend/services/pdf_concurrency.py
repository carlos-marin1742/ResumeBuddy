"""Process-wide bound on simultaneous Chromium PDF renders, each time-boxed."""
import concurrent.futures
import logging
import os
import signal
import sys
import threading
import uuid
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PdfBusyError(Exception):
    """Raised when no render slot frees up within the queue timeout."""


class PdfRenderTimeoutError(PdfBusyError):
    """Raised when a render outlives PDF_RENDER_TIMEOUT_SECONDS and is killed.

    A PdfBusyError subclass so every caller that already keeps its result when
    the queue is busy handles a timed-out render the same way.
    """


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _positive_float_env(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


PDF_MAX_CONCURRENCY = _positive_int_env("PDF_MAX_CONCURRENCY", 2)
PDF_QUEUE_TIMEOUT_SECONDS = _positive_float_env("PDF_QUEUE_TIMEOUT_SECONDS", 30.0)
PDF_RENDER_TIMEOUT_SECONDS = _positive_float_env("PDF_RENDER_TIMEOUT_SECONDS", 45.0, minimum=1.0)

# After the browser is killed, how long the worker thread gets to run its
# cleanup (close the browser, delete temp files) before the slot is released.
_KILL_GRACE_SECONDS = 5.0
# Chromium ignores unknown switches; this one only tags the process for the watchdog.
_MARKER_SWITCH = "resumebuddy-render"

_render_slots = threading.BoundedSemaphore(PDF_MAX_CONCURRENCY)


@contextmanager
def pdf_render_slot():
    """Hold one render slot, or raise PdfBusyError after the queue timeout."""
    if not _render_slots.acquire(timeout=PDF_QUEUE_TIMEOUT_SECONDS):
        raise PdfBusyError("PDF rendering is busy. Please try again shortly.")
    try:
        yield
    finally:
        _render_slots.release()


_render_context = threading.local()


def launch_chromium(playwright):
    """Launch Chromium, tagged so the watchdog can find it if the render hangs."""
    token = getattr(_render_context, "token", None)
    args = [f"--{_MARKER_SWITCH}={token}"] if token else []
    return playwright.chromium.launch(args=args, timeout=_operation_timeout_ms())


def new_page(browser):
    """Open a page whose Playwright operations time out before the watchdog fires."""
    page = browser.new_page()
    page.set_default_timeout(_operation_timeout_ms())
    return page


def _operation_timeout_ms() -> int:
    # First line of defense: a third of the whole-render budget, so a few slow
    # operations still fit but one stuck operation fails well before the watchdog.
    return int(PDF_RENDER_TIMEOUT_SECONDS / 3 * 1000)


def _kill_render_processes(token: str) -> int:
    """SIGKILL the Chromium launched for one render, plus its descendants.

    The browser is found by the marker switch from launch_chromium, so a
    concurrent render's browser is never touched. Linux only (it reads /proc);
    elsewhere the Playwright operation timeouts are the only defense.
    """
    if not sys.platform.startswith("linux"):
        logger.warning("Cannot kill a timed-out Chromium on %s; relying on Playwright timeouts", sys.platform)
        return 0
    marker = f"--{_MARKER_SWITCH}={token}".encode()
    parents: dict[int, int] = {}
    doomed: set[int] = set()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as stat_file:
                stat = stat_file.read()
            with open(f"/proc/{name}/cmdline", "rb") as cmdline_file:
                cmdline = cmdline_file.read()
        except OSError:
            continue  # the process exited while scanning
        parents[int(name)] = int(stat.rsplit(b")", 1)[1].split()[1])
        if marker in cmdline:
            doomed.add(int(name))
    grew = True
    while grew:
        children = {pid for pid, ppid in parents.items() if ppid in doomed} - doomed
        doomed |= children
        grew = bool(children)
    doomed.discard(os.getpid())
    for pid in doomed:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            logger.warning("Could not kill timed-out render process %s", pid, exc_info=True)
    return len(doomed)


def run_render(worker, *args):
    """Run a render worker in a thread under a render slot and a hard deadline.

    Threads cannot be interrupted, so on timeout the watchdog kills the
    worker's Chromium; the blocked Playwright call then fails, the worker's
    finally blocks run, and the slot is released.
    """
    with pdf_render_slot():
        token = uuid.uuid4().hex

        def run():
            _render_context.token = token
            return worker(*args)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run)
        try:
            done, _ = concurrent.futures.wait([future], timeout=PDF_RENDER_TIMEOUT_SECONDS)
            if done:
                return future.result()
            killed = _kill_render_processes(token)
            logger.error(
                "PDF render exceeded %.0fs; killed %d process(es)", PDF_RENDER_TIMEOUT_SECONDS, killed
            )
            done, _ = concurrent.futures.wait([future], timeout=_KILL_GRACE_SECONDS)
            if not done:
                logger.error("Timed-out PDF render worker did not stop after its browser was killed")
            raise PdfRenderTimeoutError("PDF rendering timed out. Please try again shortly.")
        finally:
            executor.shutdown(wait=False)
