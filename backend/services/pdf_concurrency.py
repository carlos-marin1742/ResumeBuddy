"""Process-wide bound on simultaneous Chromium PDF renders."""
import os
import threading
from contextlib import contextmanager


class PdfBusyError(Exception):
    """Raised when no render slot frees up within the queue timeout."""


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _positive_float_env(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except ValueError:
        return default


PDF_MAX_CONCURRENCY = _positive_int_env("PDF_MAX_CONCURRENCY", 2)
PDF_QUEUE_TIMEOUT_SECONDS = _positive_float_env("PDF_QUEUE_TIMEOUT_SECONDS", 30.0)

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
