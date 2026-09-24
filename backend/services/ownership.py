"""Ownership-scoped persistence helpers for user-owned resources."""

from typing import Any

from sqlmodel import Session, select


def get_owned_record(
    db: Session, model: Any, record_id: str, user_id: str | None,
) -> Any | None:
    """Fetch by primary key and owner in one query for application requests.

    ``user_id`` is optional only for direct unit-level calls that do not run
    through FastAPI's authentication middleware. Every HTTP API request has a
    user ID set by that middleware and therefore uses the ownership predicate.
    """
    if user_id is None:
        return db.get(model, record_id)
    return db.exec(select(model).where(
        model.id == record_id,
        model.user_id == user_id,
    )).first()
