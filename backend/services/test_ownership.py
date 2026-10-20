"""Ownership lookups fail closed: an unknown user is a bug, never an unscoped read."""
import asyncio
import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main
from models import MasterResumeRecord
from routes.cover_letter import _get_owned_history_record
from routes.generate import RESUME_STORE, RESUME_STORE_OWNERS, get_owned_resume
from routes.history import list_history
from services.ownership import OwnershipContextError, get_owned_record


@pytest.mark.parametrize("unknown", [None, ""])
def test_get_owned_record_raises_without_a_user_id_and_never_queries(unknown):
    db = MagicMock()

    with pytest.raises(OwnershipContextError):
        get_owned_record(db, MasterResumeRecord, "record-1", unknown)

    db.get.assert_not_called()
    db.exec.assert_not_called()


@pytest.mark.parametrize("unknown", [None, ""])
def test_get_owned_resume_raises_without_a_user_id_even_for_a_stored_session(unknown):
    RESUME_STORE["fail-closed-session"] = {"summary": "private"}
    RESUME_STORE_OWNERS["fail-closed-session"] = "someone"
    try:
        with pytest.raises(OwnershipContextError):
            get_owned_resume("fail-closed-session", unknown)
    finally:
        RESUME_STORE.pop("fail-closed-session", None)
        RESUME_STORE_OWNERS.pop("fail-closed-session", None)


@pytest.mark.parametrize("unknown", [None, ""])
def test_get_owned_history_record_raises_without_a_user_id_and_never_queries(unknown):
    db = MagicMock()

    with pytest.raises(OwnershipContextError):
        _get_owned_history_record(db, "history-1", unknown)

    db.get.assert_not_called()
    db.exec.assert_not_called()


def test_list_history_raises_without_a_request_and_never_queries():
    db = MagicMock()

    with pytest.raises(OwnershipContextError):
        list_history(db=db)

    db.exec.assert_not_called()


def test_list_history_raises_when_the_request_carries_no_user_id():
    db = MagicMock()
    request = SimpleNamespace(state=SimpleNamespace(user_id=None))

    with pytest.raises(OwnershipContextError):
        list_history(db=db, http_request=request)

    db.exec.assert_not_called()


def test_the_error_is_logged_when_ownership_is_unknown(monkeypatch):
    # A handler on the logger itself: application logging setup elsewhere in the
    # suite can change propagation, which would hide records from caplog.
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("services.ownership")
    handler = Collect(level=logging.ERROR)
    monkeypatch.setattr(logger, "disabled", False)
    logger.addHandler(handler)
    try:
        with pytest.raises(OwnershipContextError):
            get_owned_record(MagicMock(), MasterResumeRecord, "record-1", None)
    finally:
        logger.removeHandler(handler)

    assert [r.levelno for r in records] == [logging.ERROR]
    assert "get_owned_record called without a user id" in records[0].getMessage()


def test_the_app_answers_the_error_with_a_generic_500():
    response = asyncio.run(main.ownership_context_handler(
        MagicMock(), OwnershipContextError("get_owned_record requires an authenticated user id"),
    ))

    assert response.status_code == 500
    assert json.loads(response.body) == {"detail": "Internal server error."}
    assert b"get_owned_record" not in response.body


def test_the_app_registers_the_handler_for_the_error():
    assert main.app.exception_handlers[OwnershipContextError] is main.ownership_context_handler
