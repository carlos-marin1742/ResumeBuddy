"""Dependency checks behind the /health/ready readiness probe."""
import json
import logging
import os
import subprocess
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session

from db import get_engine
from services.static_profiles import static_profiles_enabled

logger = logging.getLogger(__name__)


def database_ready() -> bool:
    """Round-trip SELECT 1 against the configured database."""
    try:
        with Session(get_engine()) as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("Readiness: database check failed", exc_info=True)
        return False


def _headless_shell_install_dir() -> Path:
    """Ask Playwright where it installs the headless shell (no launch).

    Playwright's Python API only exposes the full-Chromium path, but
    chromium.launch() runs chrome-headless-shell. The CLI's dry-run prints the
    install location it resolves, honouring PLAYWRIGHT_BROWSERS_PATH.
    """
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    node, cli = compute_driver_executable()
    result = subprocess.run(
        [node, cli, "install", "--dry-run", "chromium"],
        capture_output=True, text=True, timeout=30, check=True, env=get_driver_env(),
    )
    in_headless_block = False
    for line in result.stdout.splitlines():
        if "Headless Shell" in line:
            in_headless_block = True
        elif in_headless_block and "Install location:" in line:
            return Path(line.split("Install location:", 1)[1].strip())
    raise RuntimeError("Headless shell install location not reported by Playwright")


@lru_cache(maxsize=1)
def _resolved_chromium_path() -> str:
    """Resolve the executable that chromium.launch() actually runs.

    Raising keeps lru_cache from caching a failure, so a later probe retries.
    """
    install_dir = _headless_shell_install_dir()
    for candidate in install_dir.rglob("chrome-headless-shell*"):
        if candidate.is_file() and candidate.stem == "chrome-headless-shell":
            return str(candidate)
    raise FileNotFoundError("chrome-headless-shell is not installed")


def chromium_ready() -> bool:
    """Confirm the Chromium executable exists on disk (no launch)."""
    try:
        return os.path.exists(_resolved_chromium_path())
    except Exception:
        logger.warning("Readiness: chromium check failed", exc_info=True)
        return False


def static_profile_ready(base_resume_path: Path) -> bool:
    """Check base_resume.json only when static profiles are enabled."""
    try:
        if not static_profiles_enabled():
            return True
        json.loads(base_resume_path.read_text())
        return True
    except Exception:
        logger.warning("Readiness: static profile check failed", exc_info=True)
        return False
