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
    "ALLOWED_ORIGINS": "https://resume.example.com",
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
    validate_production_config(env(REGISTRATION_MODE=mode, PUBLIC_APP_URL="https://resume.example.com", **SMTP))


def test_half_configured_smtp_is_rejected_even_when_closed():
    with pytest.raises(RuntimeError):
        validate_production_config(env(SMTP_HOST="smtp.example.test"))
    with pytest.raises(RuntimeError):
        validate_production_config(env(SMTP_FROM="noreply@example.test"))


@pytest.mark.parametrize("missing", ["AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "REQUIRE_HTTPS", "ALLOWED_ORIGINS"])
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


def test_error_names_every_problem_setting_and_never_a_value():
    settings = env(SESSION_COOKIE_SECURE="false", SMTP_HOST="smtp-secret-host.test", GROQ_API_KEY="")
    del settings["AUTH_TOKEN_PEPPER"]
    del settings["REQUIRE_HTTPS"]
    with pytest.raises(RuntimeError) as caught:
        validate_production_config(settings)
    message = str(caught.value)
    for name in ("AUTH_TOKEN_PEPPER", "GROQ_API_KEY", "SMTP_FROM", "REQUIRE_HTTPS", "SESSION_COOKIE_SECURE"):
        assert name in message
    assert "ANTHROPIC_API_KEY" not in message
    assert "smtp-secret-host.test" not in message


def test_short_pepper_is_rejected_by_name_without_echoing_it():
    with pytest.raises(RuntimeError) as caught:
        validate_production_config(env(AUTH_TOKEN_PEPPER="short-pepper-31-chars-xxxxxxxxxx"[:31]))
    assert "AUTH_TOKEN_PEPPER" in str(caught.value)
    assert "short-pepper" not in str(caught.value)
    validate_production_config(env(AUTH_TOKEN_PEPPER="p" * 32))


def test_public_url_is_not_required_while_email_cannot_be_sent():
    validate_production_config(env())


@pytest.mark.parametrize("trigger", [{"REGISTRATION_MODE": "open", **SMTP}, {"REGISTRATION_MODE": "allowlist", **SMTP}, SMTP])
def test_public_url_is_required_once_email_can_be_sent(trigger):
    with pytest.raises(RuntimeError, match="PUBLIC_APP_URL"):
        validate_production_config(env(**trigger))
    validate_production_config(env(PUBLIC_APP_URL="https://resume.example.com", **trigger))


@pytest.mark.parametrize(
    "url",
    [
        "http://resume.example.com",
        "resume.example.com",
        "https://",
        "https://localhost",
        "https://LOCALHOST:8443/",
        "https://app.localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://0.0.0.0",
        "ftp://resume.example.com",
    ],
)
def test_public_url_must_be_https_and_not_local(url):
    with pytest.raises(RuntimeError, match="PUBLIC_APP_URL"):
        validate_production_config(env(PUBLIC_APP_URL=url, **SMTP))


def test_public_url_with_port_and_path_is_accepted():
    validate_production_config(env(PUBLIC_APP_URL="https://resume.example.com:8443/app/", **SMTP))


@pytest.mark.parametrize(
    "origins",
    [
        "",
        " , ",
        "*",
        "https://*.example.com",
        "http://resume.example.com",
        "resume.example.com",
        "https://localhost",
        "https://app.localhost",
        "https://127.0.0.1",
        "http://localhost:5175,https://resume.example.com",
        "https://resume.example.com,http://localhost:8000",
        "https://resume.example.com/",
        "https://resume.example.com/app",
        "https://user@resume.example.com",
    ],
)
def test_allowed_origins_must_be_public_https_origins(origins):
    with pytest.raises(RuntimeError) as caught:
        validate_production_config(env(ALLOWED_ORIGINS=origins))
    assert "ALLOWED_ORIGINS" in str(caught.value)


def test_allowed_origins_accepts_several_https_origins_with_ports():
    validate_production_config(
        env(ALLOWED_ORIGINS="https://resume.example.com, https://www.example.com:8443")
    )


def test_allowed_origins_error_does_not_echo_the_value():
    with pytest.raises(RuntimeError) as caught:
        validate_production_config(env(ALLOWED_ORIGINS="http://internal-secret-host.test"))
    assert "internal-secret-host" not in str(caught.value)
