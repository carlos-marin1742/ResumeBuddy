"""
main.py
-------
FastAPI application entry point for the ATS Resume Builder.
"""

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from routes.extract import router as extract_router
from routes.generate import router as generate_router
from routes.preview import router as preview_router
from routes.resumes import router as resumes_router
from routes.history import router as history_router
from routes.cover_letter import router as cover_letter_router
from routes.regenerate import router as regenerate_router
from routes.resume_import import router as resume_import_router
from routes.master_resumes import router as master_resumes_router


load_dotenv()

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

# ── Rate limiting for AI-backed routes ────────────────────────────────────
# These endpoints call paid Groq/Claude APIs. There is no authentication, so
# without a limit any client that can reach the server can drive up API
# costs or exhaust provider rate limits with unlimited requests.
_RATE_LIMITED_PATHS = {
    "/api/extract-keywords",
    "/api/generate-resume",
    "/api/regenerate-section",
    "/api/generate-cover-letter",
}
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "300"))
_rate_limit_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit_ai_routes(request: Request, call_next):
    if request.method == "POST" and request.url.path in _RATE_LIMITED_PATHS:
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = _rate_limit_hits[client_ip]
        while hits and now - hits[0] > RATE_LIMIT_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a few minutes and try again."},
            )
        hits.append(now)
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


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
