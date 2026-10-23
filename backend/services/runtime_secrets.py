"""Secrets from a mounted file (NAME_FILE) or a plain env var (NAME), never both."""
import os
from pathlib import Path

SECRET_NAMES = ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "AUTH_TOKEN_PEPPER", "SMTP_USERNAME", "SMTP_PASSWORD")

# Names whose value this process copied from a file into the environment, so a
# second load_runtime_secrets() call does not see its own output as a conflict.
_exported: set[str] = set()


def read_secret(name: str) -> str | None:
    """Return the secret from NAME_FILE or NAME, or None when neither is set.

    Setting both is ambiguous and fails. Only names are ever put in error text.
    """
    secret_file = os.getenv(f"{name}_FILE") or None
    plain = os.getenv(name) or None
    if secret_file and plain and name not in _exported:
        raise RuntimeError(f"Both {name} and {name}_FILE are set; set only one.")
    if plain and not (secret_file and name in _exported):
        return plain
    if not secret_file:
        return None
    try:
        value = Path(secret_file).read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise RuntimeError(f"Required secret {name} is unavailable.") from exc
    if not value:
        raise RuntimeError(f"Secret {name} is empty.")
    return value


def load_runtime_secrets() -> None:
    """Export file-mounted secrets to the environment without logging their values."""
    for name in SECRET_NAMES:
        value = read_secret(name)
        if value is not None and os.environ.get(name) != value:
            os.environ[name] = value
            _exported.add(name)
