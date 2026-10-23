"""The Dockerfile start command and healthcheck follow the deploy environment."""
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parent.parent / "Dockerfile"

pytestmark = pytest.mark.skipif(not DOCKERFILE.exists(), reason="Dockerfile is outside the test image")


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def _instruction(text: str, name: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(name))


def test_start_command_binds_to_port_with_default_8000(dockerfile):
    cmd = _instruction(dockerfile, "CMD")
    assert "--port ${PORT:-8000}" in cmd
    assert "--port 8000" not in cmd


def test_healthcheck_uses_the_same_port(dockerfile):
    healthcheck = dockerfile[dockerfile.index("HEALTHCHECK"):]
    healthcheck = healthcheck[: healthcheck.index("\nCMD")]
    assert "PORT" in healthcheck and "8000" in healthcheck  # PORT with an 8000 default
    assert "127.0.0.1:8000" not in healthcheck


def test_forwarded_allow_ips_comes_from_the_environment_and_defaults_to_loopback(dockerfile):
    cmd = _instruction(dockerfile, "CMD")
    assert "${FORWARDED_ALLOW_IPS:-127.0.0.1}" in cmd
    assert "--forwarded-allow-ips=*" not in cmd


def test_start_command_runs_a_single_worker(dockerfile):
    cmd = _instruction(dockerfile, "CMD")
    assert "--workers" not in cmd
    assert "memory" in dockerfile.lower() and "RESUME_STORE" in dockerfile


def test_test_only_helper_modules_are_kept_out_of_the_image():
    ignored = {line.strip() for line in (DOCKERFILE.parent / ".dockerignore").read_text(encoding="utf-8").splitlines()}
    backend = DOCKERFILE.parent / "backend"
    helpers = [
        path.name
        for path in backend.glob("*.py")
        if not path.name.startswith("test_") and "import pytest" in path.read_text(encoding="utf-8")
    ]
    assert helpers, "expected at least one test helper module"
    leaked = [name for name in helpers if f"backend/{name}" not in ignored]
    assert leaked == []
