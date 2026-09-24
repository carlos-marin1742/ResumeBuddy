"""Shared, fail-closed validation for data received from HTTP clients."""

from __future__ import annotations

import re
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


# IDs are used for database lookups, session keys, and filenames.  Keeping the
# alphabet deliberately small prevents path/query syntax ever crossing those
# boundaries.
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_JSON_DEPTH = 12
MAX_JSON_ITEMS = 500


def validate_identifier(value: str, field_name: str = "identifier") -> str:
    if not isinstance(value, str) or not SAFE_IDENTIFIER.fullmatch(value):
        raise ValueError(f"{field_name} contains invalid characters.")
    return value


def validate_untrusted_value(value: Any, *, depth: int = 0) -> None:
    """Reject malformed JSON shapes and control characters before use.

    HTML is intentionally not stripped here: resume prose can legitimately
    contain angle brackets, and output renderers escape it at the HTML sink.
    This keeps stored data faithful while preventing active markup execution.
    """
    if depth > MAX_JSON_DEPTH:
        raise ValueError("Input is nested too deeply.")
    if isinstance(value, str):
        if CONTROL_CHARACTERS.search(value):
            raise ValueError("Input contains unsupported control characters.")
        return
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Input contains a non-finite number.")
        return
    if isinstance(value, list):
        if len(value) > MAX_JSON_ITEMS:
            raise ValueError("Input contains too many items.")
        for item in value:
            validate_untrusted_value(item, depth=depth + 1)
        return
    if isinstance(value, dict):
        if len(value) > MAX_JSON_ITEMS:
            raise ValueError("Input contains too many fields.")
        for key, item in value.items():
            if not isinstance(key, str) or CONTROL_CHARACTERS.search(key):
                raise ValueError("Input contains an invalid field name.")
            validate_untrusted_value(item, depth=depth + 1)
        return
    raise ValueError("Input contains an unsupported value type.")


class StrictRequest(BaseModel):
    """Base model for public JSON bodies: exact fields and exact JSON types."""

    model_config = ConfigDict(extra="forbid", strict=True)

    @model_validator(mode="after")
    def reject_unsafe_values(self):
        validate_untrusted_value(self.model_dump())
        return self
