"""Create, reset and list users from a shell in the deployed service's environment.

    python -m scripts.manage_users create EMAIL
    python -m scripts.manage_users reset EMAIL
    python -m scripts.manage_users list

Passwords are only ever read from an interactive prompt. Database settings come
from the same configuration path as the app, and no secret or connection string
is printed.
"""
import argparse
import getpass
import sys

from dotenv import load_dotenv
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlmodel import Session, select

load_dotenv()
from services.runtime_secrets import load_runtime_secrets  # noqa: E402

load_runtime_secrets()

from db import get_engine  # noqa: E402
from models import User, UserSession  # noqa: E402
from services.auth_service import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, hash_password, utcnow  # noqa: E402

_EMAIL = TypeAdapter(EmailStr)


class UsageError(Exception):
    """A problem to show the operator as-is."""


def _normalize(address: str) -> str:
    try:
        return str(_EMAIL.validate_python(address.strip())).strip().casefold()
    except ValidationError as exc:
        raise UsageError("That is not a valid email address.") from exc


def _ask_new_password(prompt_password) -> str:
    password = prompt_password("Password: ")
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise UsageError(f"Password must be {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters.")
    if prompt_password("Confirm password: ") != password:
        raise UsageError("Passwords do not match.")
    return password


def _find(session: Session, address: str) -> User | None:
    return session.exec(select(User).where(User.email == address)).first()


def create_user(address: str, prompt_password, out) -> None:
    address = _normalize(address)
    with Session(get_engine()) as session:
        if _find(session, address):
            out(f"User {address} already exists; nothing changed.")
            return
        password = _ask_new_password(prompt_password)
        session.add(User(email=address, password_hash=hash_password(password), email_verified_at=utcnow()))
        session.commit()
    out(f"Created verified user {address}.")


def reset_password(address: str, prompt_password, out) -> None:
    address = _normalize(address)
    with Session(get_engine()) as session:
        user = _find(session, address)
        if not user:
            raise UsageError(f"No user {address}.")
        password = _ask_new_password(prompt_password)
        user.password_hash = hash_password(password)
        user.failed_login_count = 0
        user.locked_until = None
        session.add(user)
        now = utcnow()
        sessions = session.exec(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).all()
        for active in sessions:
            active.revoked_at = now
            session.add(active)
        session.commit()
    out(f"Password reset for {address}; revoked {len(sessions)} active session(s).")


def list_users(out) -> None:
    with Session(get_engine()) as session:
        users = session.exec(select(User).order_by(User.email)).all()
        for user in users:
            out(f"{user.email}\t{'verified' if user.email_verified_at else 'unverified'}")
    out(f"{len(users)} user(s).")


def main(argv=None, prompt_password=getpass.getpass, out=print) -> int:
    parser = argparse.ArgumentParser(prog="python -m scripts.manage_users", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("create", help="create a verified user").add_argument("email")
    commands.add_parser("reset", help="set a new password and revoke the user's sessions").add_argument("email")
    commands.add_parser("list", help="list emails and verified status")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            create_user(args.email, prompt_password, out)
        elif args.command == "reset":
            reset_password(args.email, prompt_password, out)
        else:
            list_users(out)
    except UsageError as exc:
        out(str(exc))
        return 1
    except Exception as exc:
        # Driver errors can embed connection details, so only the type is shown.
        out(f"Failed: {type(exc).__name__}. Check the database configuration.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
