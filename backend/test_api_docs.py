"""Interactive API docs are on outside production and 404 in production."""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import main

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def _app_for(app_env: str | None) -> TestClient:
    app = FastAPI(**main.docs_settings(app_env))

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


@pytest.mark.parametrize("path", DOC_PATHS)
@pytest.mark.parametrize("app_env", ["production"])
def test_docs_return_404_in_production(app_env, path):
    client = _app_for(app_env)

    assert client.get(path).status_code == 404
    assert client.get("/ping").status_code == 200


@pytest.mark.parametrize("path", DOC_PATHS)
@pytest.mark.parametrize("app_env", [None, "development", "staging", "test"])
def test_docs_are_served_outside_production(app_env, path):
    assert _app_for(app_env).get(path).status_code == 200


def test_production_also_drops_the_swagger_oauth_redirect():
    client = _app_for("production")

    assert client.get("/docs/oauth2-redirect").status_code == 404


def test_the_real_app_uses_the_environment_setting():
    expected = main.docs_settings(os.getenv("APP_ENV"))

    assert main.app.docs_url == expected["docs_url"]
    assert main.app.redoc_url == expected["redoc_url"]
    assert main.app.openapi_url == expected["openapi_url"]


@pytest.mark.parametrize("path", DOC_PATHS)
def test_the_real_app_serves_docs_without_a_session_in_this_environment(path):
    if os.getenv("APP_ENV") == "production":
        pytest.skip("this environment really is production")

    assert TestClient(main.app).get(path).status_code == 200
