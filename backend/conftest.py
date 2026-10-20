"""Test-only application overrides that avoid requiring a configured database."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

TEST_USER_ID = "unit-test-user"


@pytest.fixture(autouse=True)
def isolate_http_app(monkeypatch):
    """Keep HTTP route tests independent from infrastructure configuration."""
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("STATIC_PROFILES_ENABLED", "true")
    try:
        import db
        import main
    except RuntimeError:
        yield
        return

    main.app.dependency_overrides[db.get_session] = lambda: iter([MagicMock()])
    monkeypatch.setattr(main, "get_session", lambda: iter([MagicMock()]))
    monkeypatch.setattr(
        main,
        "get_current_user",
        lambda request, session: SimpleNamespace(id=TEST_USER_ID),
    )
    yield
    main.app.dependency_overrides.clear()


@pytest.fixture
def test_user_id() -> str:
    """The id the stubbed authentication middleware gives every unit-test request."""
    return TEST_USER_ID


@pytest.fixture
def user_request(test_user_id) -> SimpleNamespace:
    """Stands in for the Request the auth middleware stamps with state.user_id."""
    return SimpleNamespace(state=SimpleNamespace(user_id=test_user_id))
