"""Server-only primitives for passwords, opaque sessions, and one-time links."""
import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import bcrypt
from fastapi import HTTPException, Request, status
from sqlmodel import Session, select

from models import AuthToken, User, UserSession

SESSION_COOKIE = "__Host-resumebuddy_session" if os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true" else "resumebuddy_session"
SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "30"))
SESSION_ABSOLUTE_HOURS = int(os.getenv("SESSION_ABSOLUTE_HOURS", "12"))
TOKEN_TTL_MINUTES = int(os.getenv("AUTH_TOKEN_TTL_MINUTES", "30"))
MAX_LOGIN_FAILURES = int(os.getenv("MAX_LOGIN_FAILURES", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))


def utcnow(): return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive timestamps despite timezone=True; normalize at boundary."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def digest(value: str) -> str:
    pepper = os.getenv("AUTH_TOKEN_PEPPER")
    if not pepper:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    return hashlib.sha256(f"{pepper}:{value}".encode()).hexdigest()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise HTTPException(status_code=422, detail="Password must be 12 to 128 characters.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, encoded: str) -> bool:
    try: return bcrypt.checkpw(password.encode(), encoded.encode())
    except ValueError: return False


def issue_token(db: Session, user: User, purpose: str) -> str:
    now = utcnow()
    for old in db.exec(select(AuthToken).where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))).all():
        old.used_at = now; db.add(old)
    raw = secrets.token_urlsafe(32)
    db.add(AuthToken(user_id=user.id, token_hash=digest(raw), purpose=purpose, expires_at=now + timedelta(minutes=TOKEN_TTL_MINUTES)))
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> User:
    token = db.exec(select(AuthToken).where(AuthToken.token_hash == digest(raw), AuthToken.purpose == purpose)).first()
    if not token or token.used_at or as_utc(token.expires_at) <= utcnow() or not (user := db.get(User, token.user_id)):
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")
    token.used_at = utcnow(); db.add(token)
    return user


def create_session(db: Session, user: User) -> str:
    now = utcnow(); raw = secrets.token_urlsafe(32)
    db.add(UserSession(user_id=user.id, token_hash=digest(raw), last_seen_at=now, expires_at=now + timedelta(hours=SESSION_ABSOLUTE_HOURS)))
    return raw


def get_current_user(request: Request, db: Session) -> User:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    session = db.exec(select(UserSession).where(UserSession.token_hash == digest(raw))).first(); now = utcnow()
    if not session or session.revoked_at or as_utc(session.expires_at) <= now or as_utc(session.last_seen_at) + timedelta(minutes=SESSION_IDLE_MINUTES) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Please sign in again.")
    user = db.get(User, session.user_id)
    if not user or not user.email_verified_at: raise HTTPException(status_code=403, detail="Email verification required.")
    session.last_seen_at = now; db.add(session); db.commit()
    return user


def send_email(recipient: str, subject: str, url: str) -> None:
    host, sender = os.getenv("SMTP_HOST"), os.getenv("SMTP_FROM")
    if not host or not sender: raise HTTPException(status_code=503, detail="Email delivery is not configured.")
    message = EmailMessage(); message["From"] = sender; message["To"] = recipient; message["Subject"] = subject
    message.set_content(f"Use this one-time link: {url}\n\nIf you did not request this, ignore this email.")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        if os.getenv("SMTP_STARTTLS", "true").lower() == "true": smtp.starttls()
        if os.getenv("SMTP_USERNAME") and os.getenv("SMTP_PASSWORD"): smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)
