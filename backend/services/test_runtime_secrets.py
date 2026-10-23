"""read_secret: one helper for NAME_FILE (mounted file) or NAME (plain env var)."""
import logging

import pytest

import db
from services import runtime_secrets
from services.runtime_secrets import load_runtime_secrets, read_secret

VALUE = "s3cr3t-value-do-not-leak"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("DEMO_KEY", "DEMO_KEY_FILE", "DATABASE_URL", "DATABASE_PASSWORD", "DATABASE_PASSWORD_FILE", *runtime_secrets.SECRET_NAMES):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(f"{name}_FILE", raising=False)


def _secret_file(tmp_path, content):
    path = tmp_path / "secret.txt"
    path.write_bytes(content)
    return str(path)


def test_file_only(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_KEY_FILE", _secret_file(tmp_path, VALUE.encode()))
    assert read_secret("DEMO_KEY") == VALUE


def test_env_only(monkeypatch):
    monkeypatch.setenv("DEMO_KEY", VALUE)
    assert read_secret("DEMO_KEY") == VALUE


def test_neither_returns_none():
    assert read_secret("DEMO_KEY") is None


def test_empty_variables_count_as_unset(monkeypatch):
    monkeypatch.setenv("DEMO_KEY", "")
    monkeypatch.setenv("DEMO_KEY_FILE", "")
    assert read_secret("DEMO_KEY") is None


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b""])
def test_trailing_newline_is_stripped(monkeypatch, tmp_path, ending):
    monkeypatch.setenv("DEMO_KEY_FILE", _secret_file(tmp_path, VALUE.encode() + ending))
    assert read_secret("DEMO_KEY") == VALUE


def test_both_set_is_a_startup_error_that_names_the_variables_not_the_values(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("DEMO_KEY", "plain-" + VALUE)
    monkeypatch.setenv("DEMO_KEY_FILE", _secret_file(tmp_path, VALUE.encode()))

    with caplog.at_level(logging.DEBUG), pytest.raises(RuntimeError) as error:
        read_secret("DEMO_KEY")

    text = str(error.value) + caplog.text
    assert "DEMO_KEY" in text and "DEMO_KEY_FILE" in text
    assert VALUE not in text


def test_unreadable_file_error_does_not_contain_a_value(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_KEY_FILE", str(tmp_path / "missing.txt"))
    with pytest.raises(RuntimeError, match="DEMO_KEY") as error:
        read_secret("DEMO_KEY")
    assert VALUE not in str(error.value)


def test_empty_file_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_KEY_FILE", _secret_file(tmp_path, b"\n"))
    with pytest.raises(RuntimeError, match="DEMO_KEY.*empty"):
        read_secret("DEMO_KEY")


def test_loader_exports_file_secrets_to_the_environment_without_logging_them(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("GROQ_API_KEY_FILE", _secret_file(tmp_path, VALUE.encode() + b"\n"))

    with caplog.at_level(logging.DEBUG):
        load_runtime_secrets()

    import os
    assert os.environ["GROQ_API_KEY"] == VALUE
    assert VALUE not in caplog.text
    monkeypatch.delenv("GROQ_API_KEY")


def test_loader_accepts_plain_env_vars_and_is_safe_to_run_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_TOKEN_PEPPER", VALUE)
    monkeypatch.setenv("GROQ_API_KEY_FILE", _secret_file(tmp_path, VALUE.encode()))

    load_runtime_secrets()
    load_runtime_secrets()  # the file-derived value now sits in the env beside its _FILE

    import os
    assert os.environ["AUTH_TOKEN_PEPPER"] == VALUE and os.environ["GROQ_API_KEY"] == VALUE
    monkeypatch.delenv("GROQ_API_KEY")


def test_loader_fails_when_a_secret_is_set_both_ways(monkeypatch, tmp_path):
    monkeypatch.setenv("SMTP_PASSWORD", VALUE)
    monkeypatch.setenv("SMTP_PASSWORD_FILE", _secret_file(tmp_path, VALUE.encode()))
    with pytest.raises(RuntimeError, match="SMTP_PASSWORD"):
        load_runtime_secrets()


# ── DATABASE_URL and the database password ───────────────────────────────────

@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("postgresql+psycopg://u:p@h:5432/d", "postgresql+psycopg://u:p@h:5432/d"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_scheme_is_normalized_to_the_psycopg_driver(monkeypatch, given, expected):
    monkeypatch.setenv("DATABASE_URL", given)
    assert db.get_database_url() == expected


def test_database_password_from_a_plain_env_var(monkeypatch):
    monkeypatch.setenv("DATABASE_PASSWORD", "p@ss word")
    monkeypatch.setenv("DATABASE_HOST", "db.internal")
    assert db.get_database_url() == "postgresql+psycopg://resumebuddy:p%40ss+word@db.internal:5432/resumebuddy"


def test_database_password_from_a_file_matches_today(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", _secret_file(tmp_path, b"filepw\n"))
    monkeypatch.setenv("DATABASE_HOST", "db.internal")
    assert db.get_database_url() == "postgresql+psycopg://resumebuddy:filepw@db.internal:5432/resumebuddy"


def test_database_password_both_ways_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PASSWORD", "one")
    monkeypatch.setenv("DATABASE_PASSWORD_FILE", _secret_file(tmp_path, b"two"))
    with pytest.raises(RuntimeError, match="DATABASE_PASSWORD"):
        db.get_database_url()


def test_no_database_configuration_still_fails_clearly():
    with pytest.raises(RuntimeError, match="Database configuration is required"):
        db.get_database_url()
