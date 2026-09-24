"""
main.py
-------
FastAPI application entry point for the ATS Resume Builder.
"""

import json
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()


def load_runtime_secrets() -> None:
    """Load Docker/Kubernetes file-mounted secrets without logging their values."""
    for name in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "AUTH_TOKEN_PEPPER", "SMTP_USERNAME", "SMTP_PASSWORD"):
        secret_file = os.getenv(f"{name}_FILE")
        if secret_file and not os.getenv(name):
            try:
                os.environ[name] = Path(secret_file).read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise RuntimeError(f"Required secret {name} is unavailable.") from exc


load_runtime_secrets()

from routes.extract import router as extract_router
from routes.generate import router as generate_router
from routes.preview import router as preview_router
from routes.resumes import router as resumes_router
from routes.history import router as history_router
from routes.cover_letter import router as cover_letter_router
from routes.regenerate import router as regenerate_router
from routes.resume_import import router as resume_import_router
from routes.master_resumes import router as master_resumes_router
from routes.auth import router as auth_router
from db import get_session
from services.auth_service import get_current_user
from services.security_logging import audit, configure_logging

SECURITY_LOG = configure_logging()
REQUIRE_HTTPS = os.getenv("REQUIRE_HTTPS", "false").lower() == "true"

if os.getenv("APP_ENV") == "production":
    required_settings = ("AUTH_TOKEN_PEPPER", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "SMTP_HOST", "SMTP_FROM")
    missing = [name for name in required_settings if not os.getenv(name)]
    if missing or not REQUIRE_HTTPS or os.getenv("SESSION_COOKIE_SECURE", "true").lower() != "true":
        raise RuntimeError("Production security configuration is incomplete.")

app = FastAPI(
    title="ATS Resume Builder",
    description="Tailors resumes for specific job descriptions using Claude.",
    version="1.0.0",
)

_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5175,http://localhost:3000,http://localhost:8000"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_JSON_BODY_BYTES = 1 * 1024 * 1024
MAX_UPLOAD_BODY_BYTES = 5 * 1024 * 1024 + 64 * 1024


@app.middleware("http")
async def validate_request_envelope(request: Request, call_next):
    """Reject oversized bodies and unexpected encodings before route parsing."""
    if request.method in {"POST", "PUT", "PATCH"}:
        content_type = request.headers.get("content-type", "").lower()
        is_upload = request.url.path == "/api/resumes/parse"
        is_bodyless_action = (
            request.url.path == "/api/auth/logout"
            or request.url.path.endswith("/restore")
            or request.url.path.endswith("/seed-dictionary")
        )
        expected_type = "multipart/form-data" if is_upload else "application/json"
        if not is_bodyless_action and not content_type.startswith(expected_type):
            return JSONResponse(status_code=415, content={"detail": f"Expected {expected_type}."})
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        max_size = MAX_UPLOAD_BODY_BYTES if is_upload else MAX_JSON_BODY_BYTES
        if content_length > max_size:
            return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    return await call_next(request)

# Every application API is authenticated. Authentication endpoints and health
# checks are intentionally the only public API surface. Cookie sessions are
# HttpOnly, so neither the SPA nor third-party JavaScript can read credentials.
_PUBLIC_API_PATHS = {"/health"}

@app.middleware("http")
async def require_authenticated_api(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/auth/"):
        # State-changing browser requests must come from an allowed origin.
        # SameSite=Lax is defense in depth; this blocks cross-site form CSRF too.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin and origin not in ALLOWED_ORIGINS:
                audit(SECURITY_LOG, logging.WARNING, "untrusted_origin_rejected", method=request.method, path=path)
                return JSONResponse(status_code=403, content={"detail": "Untrusted request origin."})
        try:
            with next(get_session()) as db:
                user = get_current_user(request, db)
            request.state.user_id = user.id
            is_ai_request = request.method == "POST" and (
                path in _RATE_LIMITED_PATHS
                or (
                    path.startswith("/api/master-resumes/")
                    and path.endswith("/seed-dictionary")
                )
            )
            if is_ai_request and _limit_exceeded(
                _ai_user_rate_limit_hits, user.id, AI_USER_RATE_LIMIT_MAX_REQUESTS,
                RATE_LIMIT_WINDOW_SECONDS,
            ):
                audit(SECURITY_LOG, logging.WARNING, "ai_user_rate_limit_exceeded", user_id=user.id, path=path)
                return _rate_limited_response()
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        except RuntimeError:
            return JSONResponse(status_code=503, content={"detail": "Authentication is not configured."})
    return await call_next(request)

# ── Rate limiting for AI-backed routes ────────────────────────────────────
# These authenticated endpoints call paid Groq/Claude APIs. Limit requests to
# contain cost and protect provider capacity if an account or browser is abused.
_RATE_LIMITED_PATHS = {
    "/api/extract-keywords",
    "/api/generate-resume",
    "/api/regenerate-section",
    "/api/generate-cover-letter",
}
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300"))
_rate_limit_hits: dict[str, deque] = defaultdict(deque)
API_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("API_RATE_LIMIT_MAX_REQUESTS", "120"))
API_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("API_RATE_LIMIT_WINDOW_SECONDS", "60"))
READ_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("READ_RATE_LIMIT_MAX_REQUESTS", "60"))
AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS", "10"))
AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS", "5"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900"))
AI_USER_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("AI_USER_RATE_LIMIT_MAX_REQUESTS", "10"))
_api_rate_limit_hits: dict[str, deque] = defaultdict(deque)
_read_rate_limit_hits: dict[str, deque] = defaultdict(deque)
_auth_rate_limit_hits: dict[str, deque] = defaultdict(deque)
_ai_user_rate_limit_hits: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT_MAX_KEYS = 10_000


def _limit_exceeded(
    buckets: dict[str, deque], key: str, limit: int, window_seconds: int,
) -> bool:
    """Apply a bounded sliding-window limit without retaining request content."""
    now = time.monotonic()
    hits = buckets[key]
    while hits and now - hits[0] > window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    if len(buckets) > _RATE_LIMIT_MAX_KEYS:
        buckets.pop(next(iter(buckets)), None)
    return False


def _rate_limited_response() -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait and try again."},
        headers={"Retry-After": str(RATE_LIMIT_WINDOW_SECONDS)},
    )
_suspicious_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_ai_routes(request: Request, call_next):
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"
    if path.startswith("/api/"):
        if _limit_exceeded(
            _api_rate_limit_hits, client_ip, API_RATE_LIMIT_MAX_REQUESTS,
            API_RATE_LIMIT_WINDOW_SECONDS,
        ):
            audit(SECURITY_LOG, logging.WARNING, "api_rate_limit_exceeded", client_ip=client_ip, path=path)
            return _rate_limited_response()
        if request.method == "GET" and _limit_exceeded(
            _read_rate_limit_hits, client_ip, READ_RATE_LIMIT_MAX_REQUESTS,
            API_RATE_LIMIT_WINDOW_SECONDS,
        ):
            audit(SECURITY_LOG, logging.WARNING, "scraping_rate_limit_exceeded", client_ip=client_ip, path=path)
            return _rate_limited_response()
        auth_limit = {
            "/api/auth/login": AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS,
            "/api/auth/register": AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS,
            "/api/auth/password-reset": AUTH_REGISTER_RATE_LIMIT_MAX_REQUESTS,
            "/api/auth/verify-email": AUTH_LOGIN_RATE_LIMIT_MAX_REQUESTS,
        }.get(path)
        if auth_limit and _limit_exceeded(
            _auth_rate_limit_hits, f"{path}:{client_ip}", auth_limit,
            AUTH_RATE_LIMIT_WINDOW_SECONDS,
        ):
            audit(SECURITY_LOG, logging.WARNING, "authentication_rate_limit_exceeded", client_ip=client_ip, path=path)
            return _rate_limited_response()
    is_dictionary_seed = (
        path.startswith("/api/master-resumes/")
        and path.endswith("/seed-dictionary")
    )
    if request.method == "POST" and (
        path in _RATE_LIMITED_PATHS or is_dictionary_seed
    ):
        if _limit_exceeded(
            _rate_limit_hits, client_ip, RATE_LIMIT_MAX_REQUESTS,
            RATE_LIMIT_WINDOW_SECONDS,
        ):
            audit(SECURITY_LOG, logging.WARNING, "ai_ip_rate_limit_exceeded", client_ip=client_ip, path=path)
            return _rate_limited_response()
    return await call_next(request)


@app.middleware("http")
async def enforce_transport_and_log(request: Request, call_next):
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    client_ip = request.client.host if request.client else "unknown"
    if REQUIRE_HTTPS and request.headers.get("x-forwarded-proto", request.url.scheme) != "https":
        audit(SECURITY_LOG, logging.WARNING, "insecure_transport_rejected", method=request.method, path=request.url.path, client_ip=client_ip, request_id=request_id)
        return JSONResponse(status_code=400, content={"detail": "HTTPS is required."})
    try:
        response = await call_next(request)
    except Exception:
        audit(SECURITY_LOG, logging.ERROR, "api_exception", method=request.method, path=request.url.path, client_ip=client_ip, request_id=request_id)
        raise
    status_code = response.status_code
    level = logging.ERROR if status_code >= 500 else logging.INFO
    audit(SECURITY_LOG, level, "api_request", method=request.method, path=request.url.path, status=status_code, client_ip=client_ip, request_id=request_id, user_id=getattr(request.state, "user_id", None))
    if status_code in {401, 403, 404, 429}:
        now = time.monotonic()
        hits = _suspicious_hits[client_ip]
        while hits and now - hits[0] > 300:
            hits.popleft()
        hits.append(now)
        if len(_suspicious_hits) > _RATE_LIMIT_MAX_KEYS:
            _suspicious_hits.pop(next(iter(_suspicious_hits)), None)
        if len(hits) == 10:
            audit(SECURITY_LOG, logging.WARNING, "suspicious_client_pattern", client_ip=client_ip, request_id=request_id)
    return response


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if REQUIRE_HTTPS:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth_router)
app.include_router(resumes_router)
app.include_router(extract_router)
app.include_router(generate_router)
app.include_router(preview_router)
app.include_router(history_router)
app.include_router(cover_letter_router)
app.include_router(regenerate_router)
app.include_router(resume_import_router)
app.include_router(master_resumes_router)
BASE_RESUME_PATH = Path(__file__).resolve().parent / "data" / "base_resume.json"

@app.get("/health", tags=["meta"])
def health():
    checks = {}
    checks["anthropic_api_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))
    if BASE_RESUME_PATH.exists():
        try:
            json.loads(BASE_RESUME_PATH.read_text())
            checks["base_resume"] = True
        except json.JSONDecodeError:
            checks["base_resume"] = "malformed"
    else:
        checks["base_resume"] = False
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    checks["outputs_dir"] = os.access(outputs_dir, os.W_OK)
    overall = all(v is True for v in checks.values())
    return {"status": "ok" if overall else "degraded", "checks": checks}

_static_dir = Path(__file__).resolve().parent / "static"

if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        return FileResponse(_static_dir / "index.html")
