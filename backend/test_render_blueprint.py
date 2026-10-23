"""render.yaml keeps secrets out of the repo and covers the README's required production variables."""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
BLUEPRINT = ROOT / "render.yaml"
README = ROOT / "README.md"
RUNBOOK = ROOT / "docs" / "deploy-render.md"

SECRET_KEYS = {"AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "ALLOWED_ORIGINS"}

pytestmark = pytest.mark.skipif(not BLUEPRINT.exists(), reason="render.yaml is outside the test image")


@pytest.fixture(scope="module")
def blueprint() -> dict:
    return yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def web(blueprint) -> dict:
    (service,) = [s for s in blueprint["services"] if s["type"] == "web"]
    return service


def _env_by_key(web: dict) -> dict:
    return {entry["key"]: entry for entry in web["envVars"]}


def _readme_required_vars() -> set[str]:
    text = README.read_text(encoding="utf-8")
    section = text[text.index("\nRequired:\n"):text.index("\nOptional:")]
    return set(re.findall(r"^\| `([A-Z][A-Z0-9_]+)` \|", section, flags=re.MULTILINE))


def _runbook_set_by_hand() -> set[str]:
    if not RUNBOOK.exists():
        return set()
    text = RUNBOOK.read_text(encoding="utf-8")
    match = re.search(r"<!-- set-by-hand:start -->(.*?)<!-- set-by-hand:end -->", text, flags=re.DOTALL)
    return set(re.findall(r"`([A-Z][A-Z0-9_]+)`", match.group(1))) if match else set()


def test_secrets_are_prompted_for_and_never_carry_a_value(web):
    env = _env_by_key(web)
    for key in SECRET_KEYS:
        assert key in env, f"{key} is missing"
        assert env[key].get("sync") is False, f"{key} must use sync: false"
        assert "value" not in env[key], f"{key} has an inline value"
        assert "fromDatabase" not in env[key]


def test_plain_values_match_the_deploy_plan(web):
    env = _env_by_key(web)
    assert env["APP_ENV"]["value"] == "production"
    assert env["REQUIRE_HTTPS"]["value"] == "true"
    assert env["PDF_MAX_CONCURRENCY"]["value"] == "1"
    for key in ("REGISTRATION_MODE", "STATIC_PROFILES_ENABLED", "FORWARDED_ALLOW_IPS"):
        assert key not in env


def test_database_url_comes_from_the_internal_connection_string(blueprint, web):
    ref = _env_by_key(web)["DATABASE_URL"]["fromDatabase"]
    assert ref["property"] == "connectionString"
    (database,) = blueprint["databases"]
    assert ref["name"] == database["name"]
    assert database["region"] == web["region"] == "ohio"  # explicit, never the default


def test_service_shape(web):
    assert web["runtime"] == "docker"
    assert web["healthCheckPath"] == "/health"
    assert web["plan"] == "0.5c-512mb"


def test_auto_deploy_is_off_through_the_current_field(web):
    assert "autoDeploy" not in web, "autoDeploy is deprecated; use autoDeployTrigger"
    assert web["autoDeployTrigger"] == "off"  # a bare YAML `off` would parse as False


@pytest.mark.skipif(not RUNBOOK.exists(), reason="runbook is outside the test image")
def test_runbook_set_by_hand_list_matches_the_prompted_secrets(web):
    prompted = {key for key, entry in _env_by_key(web).items() if entry.get("sync") is False}
    assert prompted == SECRET_KEYS
    assert _runbook_set_by_hand() == prompted


def test_every_required_production_variable_is_in_the_file_or_the_runbook_list(web):
    required = _readme_required_vars()
    assert {"APP_ENV", "DATABASE_URL", "ALLOWED_ORIGINS"} <= required, "README table was not parsed"
    covered = set(_env_by_key(web)) | _runbook_set_by_hand()
    assert required - covered == set()
