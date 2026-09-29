"""Test-only application overrides that avoid requiring a configured database."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


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
        lambda request, session: SimpleNamespace(id=None),
    )
    yield
    main.app.dependency_overrides.clear()
