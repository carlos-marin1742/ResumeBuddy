"""Registration modes: closed (default), allowlist and open."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import main
from auth_http_support import PASSWORD
from routes import auth as auth_routes
from services import registration

pytest_plugins = ("postgres_test_support", "auth_http_support")

GENERIC = {"detail": "If this address can register, a verification email has been sent."}


def _user_count(stack) -> int:
    with stack.engine.connect() as connection:
        return connection.execute(text("SELECT count(*) FROM users")).scalar_one()


def _register(stack, address: str):
    return stack.client.post("/api/auth/register", json={"email": address, "password": PASSWORD})


# ── Configuration parsing ────────────────────────────────────────────────────

def test_unset_mode_is_closed(monkeypatch):
    monkeypatch.delenv("REGISTRATION_MODE", raising=False)
    assert registration.registration_mode() == "closed"


def test_blank_mode_is_closed(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "  ")
    assert registration.registration_mode() == "closed"


def test_invalid_mode_raises_a_clear_error(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "wide-open")
    with pytest.raises(RuntimeError, match="REGISTRATION_MODE must be one of: closed, allowlist, open"):
        registration.registration_mode()


def test_invalid_mode_fails_application_startup(auth_stack, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "wide-open")
    with pytest.raises(RuntimeError, match="REGISTRATION_MODE"):
        with TestClient(main.app):
            pass


def test_allowlist_entries_are_trimmed_and_lowercased(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("REGISTRATION_ALLOWLIST", "  Alice@Example.com , ,bob@example.com")
    assert registration.registration_allowed("alice@example.com")
    assert registration.registration_allowed("  ALICE@EXAMPLE.COM ")
    assert registration.registration_allowed("bob@example.com")


def test_allowlist_is_exact_match_with_no_alias_handling(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("REGISTRATION_ALLOWLIST", "alice@example.com")
    assert not registration.registration_allowed("alice+tag@example.com")
    assert not registration.registration_allowed("a.lice@example.com")
    assert not registration.registration_allowed("alice@example.com.evil.test")


def test_allowlist_mode_with_empty_list_behaves_as_closed(monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("REGISTRATION_ALLOWLIST", " , ")
    assert not registration.registration_allowed("anyone@example.com")


# ── Register route ───────────────────────────────────────────────────────────

def test_default_closed_returns_generic_202_with_no_row_and_no_email(auth_stack):
    response = _register(auth_stack, "new@example.com")

    assert response.status_code == 202
    assert response.json() == GENERIC
    assert _user_count(auth_stack) == 0
    assert auth_stack.sent_urls == []


def test_allowlist_proceeds_for_a_listed_mixed_case_padded_address(auth_stack, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("REGISTRATION_ALLOWLIST", " Alice@Example.COM ,bob@example.com")

    response = _register(auth_stack, "ALICE@example.com")

    assert response.status_code == 202
    assert response.json() == GENERIC
    assert _user_count(auth_stack) == 1
    assert len(auth_stack.sent_urls) == 1


def test_allowlist_refusal_is_identical_to_acceptance_and_creates_nothing(auth_stack, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "allowlist")
    monkeypatch.setenv("REGISTRATION_ALLOWLIST", "alice@example.com")
    accepted = _register(auth_stack, "alice@example.com")
    users_after_accept = _user_count(auth_stack)
    emails_after_accept = len(auth_stack.sent_urls)

    refused = _register(auth_stack, "mallory@example.com")

    assert (refused.status_code, refused.json()) == (accepted.status_code, accepted.json())
    assert set(refused.headers) == set(accepted.headers)
    assert _user_count(auth_stack) == users_after_accept
    assert len(auth_stack.sent_urls) == emails_after_accept


def test_refused_path_performs_a_password_hash(auth_stack, monkeypatch):
    calls = []
    real = auth_routes.hash_password
    monkeypatch.setattr(auth_routes, "hash_password", lambda p: calls.append(p) or real(p))

    _register(auth_stack, "new@example.com")

    assert calls == [PASSWORD]


def test_open_mode_registers_and_sends_verification(auth_stack, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "open")

    response = _register(auth_stack, "anyone@example.com")

    assert response.status_code == 202
    assert response.json() == GENERIC
    assert _user_count(auth_stack) == 1
    assert len(auth_stack.sent_urls) == 1


def test_register_stays_rate_limited_per_ip_in_every_mode(auth_stack, monkeypatch):
    monkeypatch.setattr(main, "AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS", 2)
    main._auth_rate_limit_hits.clear()
    statuses = [_register(auth_stack, f"u{i}@example.com").status_code for i in range(3)]
    assert statuses == [202, 202, 429]


# ── Config endpoint ──────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("mode", "allowlist", "expected"),
    [(None, None, False), ("closed", None, False), ("allowlist", "a@example.com", False), ("open", None, True)],
)
def test_config_reports_registration_open_only_for_open_mode(auth_stack, monkeypatch, mode, allowlist, expected):
    if mode:
        monkeypatch.setenv("REGISTRATION_MODE", mode)
    if allowlist:
        monkeypatch.setenv("REGISTRATION_ALLOWLIST", allowlist)

    response = auth_stack.client.get("/api/auth/config")

    assert response.status_code == 200
    assert response.json() == {"registration_open": expected}
