"""Startup checks that apply only when APP_ENV=production."""
import ipaddress
import os
from collections.abc import Mapping
from urllib.parse import urlparse

from services.registration import registration_mode

ALWAYS_REQUIRED = ("AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY")
SMTP_REQUIRED = ("SMTP_HOST", "SMTP_FROM")
MIN_PEPPER_LENGTH = 32


def _public_url_ok(value: str) -> bool:
    """An https URL with a real host: emailed links must not point at localhost."""
    try:
        parsed = urlparse(value.strip())
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (address.is_loopback or address.is_unspecified)


def _origins_ok(value: str) -> bool:
    """A non-empty list of bare https origins (scheme://host[:port]) on public hosts.

    Browsers send the Origin header with no path, so an entry with one could never match.
    """
    entries = [entry.strip() for entry in value.split(",") if entry.strip()]
    if not entries:
        return False
    for entry in entries:
        if "*" in entry or not _public_url_ok(entry):
            return False
        try:
            parsed = urlparse(entry)
            parsed.port
        except ValueError:
            return False
        if parsed.path or parsed.params or parsed.query or parsed.fragment or parsed.username or parsed.password:
            return False
    return True


def validate_production_config(environ: Mapping[str, str] | None = None) -> None:
    env = os.environ if environ is None else environ
    if env.get("APP_ENV") != "production":
        return
    required = list(ALWAYS_REQUIRED)
    # Email is only sent when registration is enabled or SMTP was configured on purpose.
    sends_email = registration_mode(env) != "closed" or bool(env.get("SMTP_HOST") or env.get("SMTP_FROM"))
    if sends_email:
        required.extend(SMTP_REQUIRED + ("PUBLIC_APP_URL",))
    problems = [name for name in required if not env.get(name)]
    if env.get("AUTH_TOKEN_PEPPER") and len(env["AUTH_TOKEN_PEPPER"]) < MIN_PEPPER_LENGTH:
        problems.append(f"AUTH_TOKEN_PEPPER (at least {MIN_PEPPER_LENGTH} characters)")
    if sends_email and env.get("PUBLIC_APP_URL") and not _public_url_ok(env["PUBLIC_APP_URL"]):
        problems.append("PUBLIC_APP_URL (must be an https:// URL that is not localhost)")
    # Unset falls back to localhost origins in main.py, which rejects every real browser POST.
    if not _origins_ok(env.get("ALLOWED_ORIGINS", "")):
        problems.append("ALLOWED_ORIGINS (comma-separated https:// origins, no localhost, path or wildcard)")
    if env.get("REQUIRE_HTTPS", "false").lower() != "true":
        problems.append("REQUIRE_HTTPS (must be true)")
    if env.get("SESSION_COOKIE_SECURE", "true").lower() != "true":
        problems.append("SESSION_COOKIE_SECURE (must not be false)")
    if problems:
        # Names only: values may be secrets.
        raise RuntimeError(f"Production security configuration is incomplete: {', '.join(problems)}.")
