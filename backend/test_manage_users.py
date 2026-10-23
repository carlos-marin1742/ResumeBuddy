"""Admin script: create and reset users, exercised against PostgreSQL and the real HTTP stack."""
import pytest
from sqlalchemy import text
from sqlmodel import Session, select

from auth_http_support import PASSWORD
from models import User, UserSession
from scripts import manage_users
from services import auth_service

pytest_plugins = ("postgres_test_support", "auth_http_support")

NEW_PASSWORD = "a-different-password-456"


def _prompts(*answers):
    queue = list(answers)
    return lambda prompt="": queue.pop(0)


def _run(*argv, answers=()):
    out: list[str] = []
    code = manage_users.main(list(argv), prompt_password=_prompts(*answers), out=out.append)
    return code, "\n".join(out)


def _login(stack, address, password):
    return stack.client.post("/api/auth/login", json={"email": address, "password": password})


def test_created_user_is_verified_and_can_log_in_over_http(auth_stack):
    code, output = _run("create", "Admin@Example.com", answers=(PASSWORD, PASSWORD))

    assert code == 0
    assert PASSWORD not in output
    with Session(auth_stack.engine) as session:
        user = session.exec(select(User).where(User.email == "admin@example.com")).one()
        assert user.email_verified_at is not None
    assert _login(auth_stack, "admin@example.com", PASSWORD).status_code == 200
    assert auth_stack.client.get("/api/auth/me").json() == {"email": "admin@example.com"}


def test_second_create_reports_existing_and_changes_nothing(auth_stack):
    _run("create", "admin@example.com", answers=(PASSWORD, PASSWORD))
    with Session(auth_stack.engine) as session:
        before = session.exec(select(User)).one().password_hash

    code, output = _run("create", "admin@example.com", answers=(NEW_PASSWORD, NEW_PASSWORD))

    assert code == 0
    assert "already exists" in output
    with Session(auth_stack.engine) as session:
        users = session.exec(select(User)).all()
        assert len(users) == 1 and users[0].password_hash == before
    assert _login(auth_stack, "admin@example.com", PASSWORD).status_code == 200


def test_short_password_is_rejected_and_creates_nothing(auth_stack):
    code, output = _run("create", "admin@example.com", answers=("short", "short"))

    assert code == 1
    assert "12 to 128" in output
    with auth_stack.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_mismatched_confirmation_is_rejected_and_creates_nothing(auth_stack):
    code, output = _run("create", "admin@example.com", answers=(PASSWORD, PASSWORD + "x"))

    assert code == 1
    assert "do not match" in output
    with auth_stack.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_reset_changes_password_and_revokes_existing_sessions(auth_stack):
    _run("create", "admin@example.com", answers=(PASSWORD, PASSWORD))
    assert _login(auth_stack, "admin@example.com", PASSWORD).status_code == 200
    assert auth_stack.client.get("/api/resumes").status_code == 200  # the session cookie works

    code, _ = _run("reset", "admin@example.com", answers=(NEW_PASSWORD, NEW_PASSWORD))

    assert code == 0
    assert auth_stack.client.get("/api/auth/me").status_code == 401  # old cookie stops working
    auth_stack.client.cookies.clear()
    assert _login(auth_stack, "admin@example.com", PASSWORD).status_code == 401
    assert _login(auth_stack, "admin@example.com", NEW_PASSWORD).status_code == 200
    with Session(auth_stack.engine) as session:
        old = session.exec(select(UserSession).where(UserSession.revoked_at.is_not(None))).all()
        assert len(old) == 1


def test_reset_of_an_unknown_user_fails_without_creating_one(auth_stack):
    code, output = _run("reset", "ghost@example.com", answers=(NEW_PASSWORD, NEW_PASSWORD))

    assert code == 1
    assert "No user" in output
    with auth_stack.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 0


def test_list_prints_emails_and_verified_status_only(auth_stack):
    _run("create", "admin@example.com", answers=(PASSWORD, PASSWORD))
    with Session(auth_stack.engine) as session:
        session.add(User(email="pending@example.com", password_hash="$2b$12$hash-must-not-print"))
        session.commit()

    code, output = _run("list")

    assert code == 0
    assert "admin@example.com" in output and "pending@example.com" in output
    assert "verified" in output and "unverified" in output
    assert "$2b$" not in output and auth_stack.database_url not in output


def test_script_never_prints_the_database_url_on_failure(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://admin:hunter2secret@nowhere.invalid:5432/x")
    import db
    db.get_engine.cache_clear()

    code = manage_users.main(["list"], prompt_password=_prompts(), out=print)

    db.get_engine.cache_clear()
    captured = capsys.readouterr()
    assert code == 1
    assert "hunter2secret" not in captured.out + captured.err
    assert "nowhere.invalid" not in captured.out + captured.err
