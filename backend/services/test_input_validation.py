import pytest
from pydantic import ValidationError

from services.input_validation import StrictRequest, validate_identifier


class ExampleRequest(StrictRequest):
    name: str
    payload: dict | None = None


def test_strict_request_rejects_unknown_fields_and_control_characters():
    with pytest.raises(ValidationError):
        ExampleRequest(name="candidate", unexpected="field")
    with pytest.raises(ValidationError):
        ExampleRequest(name="candidate\x00")


def test_strict_request_rejects_unsafe_nested_values_and_identifier_syntax():
    with pytest.raises(ValidationError):
        ExampleRequest(name="candidate", payload={"summary": "safe\x1b"})
    with pytest.raises(ValueError):
        validate_identifier("../../database")
    assert validate_identifier("resume_123-abc") == "resume_123-abc"
