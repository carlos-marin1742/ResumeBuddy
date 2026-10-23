"""Startup checks that apply only when APP_ENV=production."""
import os
from collections.abc import Mapping

from services.registration import registration_mode

ALWAYS_REQUIRED = ("AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY")
SMTP_REQUIRED = ("SMTP_HOST", "SMTP_FROM")


def validate_production_config(environ: Mapping[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    if env.get("APP_ENV") != "production":
        return
    required = list(ALWAYS_REQUIRED)
    # Email is only sent when registration is enabled or SMTP was configured on purpose.
    if registration_mode(env) != "closed" or env.get("SMTP_HOST") or env.get("SMTP_FROM"):
        required.extend(SMTP_REQUIRED)
    missing = [name for name in required if not env.get(name)]
    https_ok = env.get("REQUIRE_HTTPS", "false").lower() == "true"
    cookie_ok = env.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    if missing or not https_ok or not cookie_ok:
        raise RuntimeError("Production security configuration is incomplete.")
