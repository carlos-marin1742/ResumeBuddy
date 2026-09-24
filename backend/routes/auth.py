import os
import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select
from db import get_session
from models import User, UserSession
from services.auth_service import (LOGIN_LOCK_MINUTES, MAX_LOGIN_FAILURES, SESSION_COOKIE, as_utc, consume_token, create_session, digest, hash_password, issue_token, send_email, utcnow, verify_password)
from services.security_logging import audit

router = APIRouter(prefix="/api/auth", tags=["authentication"])
SECURITY_LOG = logging.getLogger("resumebuddy.security")
PUBLIC_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:5175").rstrip("/")
class Credentials(BaseModel): email: EmailStr; password: str = Field(min_length=1, max_length=128)
class EmailRequest(BaseModel): email: EmailStr
class TokenRequest(BaseModel): token: str = Field(min_length=20, max_length=200)
class ResetRequest(TokenRequest): password: str = Field(min_length=1, max_length=128)
class Message(BaseModel): detail: str
class CurrentUser(BaseModel): email: EmailStr
def email(value): return str(value).strip().casefold()
def set_cookie(response, raw): response.set_cookie(SESSION_COOKIE, raw, httponly=True, secure=os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true", samesite="lax", max_age=int(os.getenv("SESSION_ABSOLUTE_HOURS", "12"))*3600, path="/")

@router.post("/register", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def register(payload: Credentials, db: Session = Depends(get_session)):
    address = email(payload.email)
    if db.exec(select(User).where(User.email == address)).first(): return Message(detail="If this address can register, a verification email has been sent.")
    user = User(email=address, password_hash=hash_password(payload.password)); db.add(user); db.flush()
    token = issue_token(db, user, "verify_email"); send_email(address, "Verify your ResumeBuddy email", f"{PUBLIC_URL}/verify-email?token={token}"); db.commit()
    return Message(detail="If this address can register, a verification email has been sent.")

@router.post("/verify-email", response_model=Message)
def verify_email(payload: TokenRequest, db: Session = Depends(get_session)):
    user = consume_token(db, payload.token, "verify_email"); user.email_verified_at = utcnow(); db.add(user); db.commit(); return Message(detail="Email verified. You can now sign in.")

@router.post("/login", response_model=Message)
def login(payload: Credentials, response: Response, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == email(payload.email))).first(); now = utcnow()
    if not user or (user.locked_until and as_utc(user.locked_until) > now) or not verify_password(payload.password, user.password_hash):
        if user and (not user.locked_until or as_utc(user.locked_until) <= now):
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_LOGIN_FAILURES: user.failed_login_count = 0; user.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
            db.add(user); db.commit()
        audit(SECURITY_LOG, logging.WARNING, "login_failed")
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.email_verified_at:
        audit(SECURITY_LOG, logging.WARNING, "login_unverified", user_id=user.id)
        raise HTTPException(status_code=403, detail="Verify your email before signing in.")
    user.failed_login_count = 0; user.locked_until = None; db.add(user); raw = create_session(db, user); db.commit(); set_cookie(response, raw)
    audit(SECURITY_LOG, logging.INFO, "login_succeeded", user_id=user.id)
    return Message(detail="Signed in.")

@router.post("/password-reset", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def request_reset(payload: EmailRequest, db: Session = Depends(get_session)):
    user = db.exec(select(User).where(User.email == email(payload.email))).first()
    if user:
        token = issue_token(db, user, "password_reset"); send_email(user.email, "Reset your ResumeBuddy password", f"{PUBLIC_URL}/reset-password?token={token}"); db.commit()
    return Message(detail="If an account exists, a reset email has been sent.")

@router.post("/password-reset/confirm", response_model=Message)
def confirm_reset(payload: ResetRequest, db: Session = Depends(get_session)):
    user = consume_token(db, payload.token, "password_reset"); user.password_hash = hash_password(payload.password); user.failed_login_count = 0; user.locked_until = None; db.add(user)
    for session in db.exec(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).all(): session.revoked_at = utcnow(); db.add(session)
    db.commit(); return Message(detail="Password reset. Please sign in.")

@router.post("/logout", response_model=Message)
def logout(request: Request, response: Response, db: Session = Depends(get_session)):
    if raw := request.cookies.get(SESSION_COOKIE):
        if session := db.exec(select(UserSession).where(UserSession.token_hash == digest(raw))).first(): session.revoked_at = utcnow(); db.add(session); db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/"); return Message(detail="Signed out.")

@router.get("/me", response_model=CurrentUser)
def me(request: Request, db: Session = Depends(get_session)):
    from services.auth_service import get_current_user
    return CurrentUser(email=get_current_user(request, db).email)
