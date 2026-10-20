"""Dependency checks behind the /health/ready readiness probe."""
import json
import logging
import os
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


@lru_cache(maxsize=1)
def _resolved_chromium_path() -> str:
    """Resolve Playwright's Chromium path without launching it.

    Raising keeps lru_cache from caching a failure, so a later probe retries.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        return playwright.chromium.executable_path


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
