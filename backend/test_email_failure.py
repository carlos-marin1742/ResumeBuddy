"""A failed email send must look exactly like a successful one and leak nothing."""
import logging
import smtplib

import pytest
from sqlalchemy import text

from auth_http_support import PASSWORD
from routes import auth as auth_routes
from services import auth_service

pytest_plugins = ("postgres_test_support", "auth_http_support")

REGISTER_BODY = {"detail": "If this address can register, a verification email has been sent."}
RESET_BODY = {"detail": "If an account exists, a reset email has been sent."}
ADDRESS = "target@example.com"


def _refused(*_):
    raise smtplib.SMTPRecipientsRefused({ADDRESS: (550, b"no such user target@example.com")})


def _disconnected(*_):
    raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")


def _unreachable(*_):
    raise ConnectionRefusedError(f"[Errno 111] Connection refused while sending to {ADDRESS}")


def _timeout(*_):
    raise TimeoutError("timed out")


def _smtp_error(*_):
    raise smtplib.SMTPException(f"boom for {ADDRESS}")


def _unconfigured(*args):
    return auth_service.send_email(*args)  # the real sender, with SMTP_HOST unset


FAILURES = [_refused, _disconnected, _unreachable, _timeout, _smtp_error, _unconfigured]


@pytest.fixture
def open_stack(auth_stack, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    return auth_stack


@pytest.fixture
def security_log():
    class Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records, self.lines = [], []

        def emit(self, record):
            self.records.append(record)
            self.lines.append(self.format(record))

    from services.security_logging import JsonFormatter

    handler = Capture()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("resumebuddy.security")
    logger.disabled = False  # alembic's fileConfig in the migration fixture disables existing loggers
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


def _users(stack) -> int:
    with stack.engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM users")).scalar_one()


def _register(stack, address=ADDRESS):
    return stack.client.post("/api/auth/register", json={"email": address, "password": PASSWORD})


def _reset(stack, address=ADDRESS):
    return stack.client.post("/api/auth/password-reset", json={"email": address})


def _seed_verified_user(stack):
    assert _register(stack).status_code == 202
    with stack.engine.begin() as connection:
        connection.execute(text("UPDATE users SET email_verified_at = now()"))
    stack.sent_urls.clear()


@pytest.mark.parametrize("failure", FAILURES)
def test_register_send_failure_matches_success_and_leaves_no_row(open_stack, monkeypatch, failure):
    success = _register(open_stack, "someone@example.com")
    assert len(open_stack.sent_urls) == 1
    monkeypatch.setattr(auth_routes, "send_email", failure)

    failed = _register(open_stack)

    assert (failed.status_code, failed.json()) == (success.status_code, success.json()) == (202, REGISTER_BODY)
    assert set(failed.headers) == set(success.headers)
    assert _users(open_stack) == 1  # only the successful one; the failed attempt was rolled back


def test_register_can_be_retried_after_a_failed_send(open_stack, monkeypatch):
    monkeypatch.setattr(auth_routes, "send_email", _refused)
    _register(open_stack)
    monkeypatch.setattr(auth_routes, "send_email", lambda recipient, subject, url: open_stack.sent_urls.append(url))

    _register(open_stack)

    assert _users(open_stack) == 1
    assert len(open_stack.sent_urls) == 1


@pytest.mark.parametrize("failure", FAILURES)
def test_reset_send_failure_matches_unknown_address_and_keeps_no_token(open_stack, monkeypatch, failure):
    _seed_verified_user(open_stack)
    unknown = _reset(open_stack, "nobody@example.com")
    monkeypatch.setattr(auth_routes, "send_email", failure)

    failed = _reset(open_stack)

    assert (failed.status_code, failed.json()) == (unknown.status_code, unknown.json()) == (202, RESET_BODY)
    assert set(failed.headers) == set(unknown.headers)
    with open_stack.engine.connect() as connection:
        reset_tokens = connection.execute(text("SELECT count(*) FROM auth_tokens WHERE purpose='password_reset'")).scalar_one()
    assert reset_tokens == 0


@pytest.mark.parametrize("failure", FAILURES)
@pytest.mark.parametrize("route", ["register", "reset"])
def test_failure_log_is_one_generic_event_without_address_token_url_or_traceback(
    open_stack, security_log, monkeypatch, failure, route
):
    if route == "reset":
        _seed_verified_user(open_stack)
    tokens = []

    def failing(recipient, subject, url):
        tokens.append(url.split("token=")[1])
        return failure(recipient, subject, url)

    monkeypatch.setattr(auth_routes, "send_email", failing)
    security_log.records.clear()
    security_log.lines.clear()

    (_register if route == "register" else _reset)(open_stack)

    failures = [r for r in security_log.records if getattr(r, "event", "") == "email_delivery_failed"]
    assert len(failures) == 1
    assert all(r.exc_info is None for r in security_log.records)
    output = "\n".join(security_log.lines)
    assert "Traceback" not in output
    for secret in (ADDRESS, "example.com", "target", "http", *tokens):
        assert secret not in output
