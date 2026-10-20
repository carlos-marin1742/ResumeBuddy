"""Ownership-scoped persistence helpers for user-owned resources."""

import logging
from typing import Any

from sqlmodel import Session, select


logger = logging.getLogger(__name__)


class OwnershipContextError(RuntimeError):
    """An ownership-scoped lookup ran without an authenticated user id.

    This is a programming error: the authentication middleware sets a user id
    on every /api request, so reaching a lookup without one means a caller
    skipped it. The lookup must fail rather than fall back to an unscoped read.
    """


def require_user_id(user_id: str | None, lookup: str) -> str:
    """Return the user id, or log and raise when ownership is unknown."""
    if not user_id:
        logger.error("Ownership-scoped lookup %s called without a user id", lookup)
        raise OwnershipContextError(f"{lookup} requires an authenticated user id")
    return user_id


def get_owned_record(
    db: Session, model: Any, record_id: str, user_id: str | None,
) -> Any | None:
    """Fetch by primary key and owner in one query.

    Raises OwnershipContextError when ``user_id`` is None; there is no
    unscoped fallback.
    """
    user_id = require_user_id(user_id, "get_owned_record")
    return db.exec(select(model).where(
        model.id == record_id,
        model.user_id == user_id,
    )).first()
