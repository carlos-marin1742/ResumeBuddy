"""Who may create an account: REGISTRATION_MODE and REGISTRATION_ALLOWLIST."""
import os
from collections.abc import Mapping

MODES = ("closed", "allowlist", "open")


def registration_mode(environ: Mapping[str, str] | None = None) -> str:
    """The configured mode. Unset or blank means closed; anything unknown is an error."""
    mode = (os.environ if environ is None else environ).get("REGISTRATION_MODE", "").strip().lower() or "closed"
    if mode not in MODES:
        raise RuntimeError(f"REGISTRATION_MODE must be one of: {', '.join(MODES)}.")
    return mode


def _allowlist() -> set[str]:
    return {item.strip().lower() for item in os.getenv("REGISTRATION_ALLOWLIST", "").split(",") if item.strip()}


def registration_open() -> bool:
    """True only for open mode, so the public config reveals nothing about the allowlist."""
    return registration_mode() == "open"


def registration_allowed(address: str) -> bool:
    """Exact, case-insensitive match; no alias or plus-address handling."""
    mode = registration_mode()
    if mode == "open":
        return True
    if mode == "allowlist":
        return address.strip().lower() in _allowlist()
    return False
