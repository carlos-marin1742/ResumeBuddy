"""Startup validation that only applies when APP_ENV=production."""
import os

import pytest

from services.production_config import validate_production_config

BASE = {
    "APP_ENV": "production",
    "AUTH_TOKEN_PEPPER": "p" * 40,
    "ANTHROPIC_API_KEY": "a",
    "GROQ_API_KEY": "g",
    "REQUIRE_HTTPS": "true",
}
SMTP = {"SMTP_HOST": "smtp.example.test", "SMTP_FROM": "noreply@example.test"}


def env(**extra):
    return {**BASE, **extra}


def test_non_production_is_never_validated():
    validate_production_config({"APP_ENV": "development"})
    validate_production_config({})


def test_closed_mode_boots_without_smtp():
    validate_production_config(env())


@pytest.mark.parametrize("mode", ["allowlist", "open"])
def test_smtp_is_required_once_registration_can_send_email(mode):
    with pytest.raises(RuntimeError, match="Production security configuration is incomplete"):
        validate_production_config(env(REGISTRATION_MODE=mode))
    validate_production_config(env(REGISTRATION_MODE=mode, **SMTP))


def test_half_configured_smtp_is_rejected_even_when_closed():
    with pytest.raises(RuntimeError):
        validate_production_config(env(SMTP_HOST="smtp.example.test"))
    with pytest.raises(RuntimeError):
        validate_production_config(env(SMTP_FROM="noreply@example.test"))


@pytest.mark.parametrize("missing", ["AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "REQUIRE_HTTPS"])
def test_core_settings_remain_required(missing):
    settings = env()
    del settings[missing]
    with pytest.raises(RuntimeError):
        validate_production_config(settings)


def test_insecure_cookies_are_rejected():
    with pytest.raises(RuntimeError):
        validate_production_config(env(SESSION_COOKIE_SECURE="false"))


def test_main_refuses_to_import_with_an_incomplete_production_config():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, '.'); import main"],
        env={"APP_ENV": "production", "PATH": os.environ.get("PATH", "")},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode != 0
    assert "Production security configuration is incomplete" in result.stderr
