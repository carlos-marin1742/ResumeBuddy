"""Runtime gate for operator-provided static resume profiles."""
import os


def static_profiles_enabled() -> bool:
    """Read the static-profile gate, rejecting ambiguous configuration."""
    value = os.getenv("STATIC_PROFILES_ENABLED", "false").strip().lower()
    if value in {"true", "1"}:
        return True
    if value in {"false", "0"}:
        return False
    raise RuntimeError(
        "STATIC_PROFILES_ENABLED must be one of true, false, 1, or 0."
    )
