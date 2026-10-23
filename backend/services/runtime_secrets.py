"""File-mounted secrets, loaded into the environment before the app or admin tools read them."""
import os
from pathlib import Path

SECRET_NAMES = ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "AUTH_TOKEN_PEPPER", "SMTP_USERNAME", "SMTP_PASSWORD")


def load_runtime_secrets() -> None:
    """Load Docker/Kubernetes file-mounted secrets without logging their values."""
    for name in SECRET_NAMES:
        secret_file = os.getenv(f"{name}_FILE")
        if secret_file and not os.getenv(name):
            try:
                os.environ[name] = Path(secret_file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RuntimeError(f"Required secret {name} is unavailable.") from exc
