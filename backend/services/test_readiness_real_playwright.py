"""Readiness path resolution against the real installed Playwright.

readiness.py parses `playwright install --dry-run` output and a private
Playwright helper, so a Playwright upgrade can break it silently. Everything
else mocks Playwright; these tests do not. They skip only when the browsers
are not installed (for example on a bare host), never when parsing breaks.
"""
import os
import sys
from pathlib import Path

import pytest

from services import readiness


@pytest.fixture(autouse=True)
def fresh_cache():
    readiness._resolved_chromium_path.cache_clear()
    yield
    readiness._resolved_chromium_path.cache_clear()


@pytest.fixture
def installed_headless_shell() -> Path:
    pytest.importorskip("playwright")
    # A parsing failure raises here and fails the test; only a missing install skips.
    install_dir = readiness._headless_shell_install_dir()
    if not install_dir.is_dir() or not any(install_dir.rglob("chrome-headless-shell")):
        pytest.skip("Playwright chromium browsers are not installed")
    return install_dir


def test_resolved_headless_shell_is_an_existing_executable(installed_headless_shell):
    resolved = Path(readiness._resolved_chromium_path())

    assert resolved.name.startswith("chrome-headless-shell")
    assert resolved.is_file()
    assert os.access(resolved, os.X_OK)
    assert installed_headless_shell in resolved.parents
    assert readiness.chromium_ready() is True


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="reads /proc to find the running binary")
def test_resolved_path_is_the_binary_chromium_launch_runs(installed_headless_shell):
    from playwright.sync_api import sync_playwright

    resolved = os.path.realpath(readiness._resolved_chromium_path())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            running = set()
            for name in os.listdir("/proc"):
                if name.isdigit():
                    try:
                        running.add(os.path.realpath(f"/proc/{name}/exe"))
                    except OSError:
                        pass
            assert resolved in running
        finally:
            browser.close()
