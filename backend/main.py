"""
main.py
-------
FastAPI application entry point for the ATS Resume Builder.

Registers:
  POST /api/extract-keywords  → routes/extract.py
  POST /api/generate-resume   → routes/generate.py
  GET  /api/download/{file}   → routes/generate.py
  GET  /health                → inline health check

Run locally:
  uvicorn main:app --reload --port 8000
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.extract import router as extract_router
from routes.generate import router as generate_router



load_dotenv()

# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ATS Resume Builder",
    description="Tailors resumes for specific job descriptions using Claude.",
    version="1.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────
# In dev, allow the React dev server (port 5173 for Vite, 3000 for CRA).
# In production, replace with your actual frontend domain.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://localhost:8000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(extract_router)
app.include_router(generate_router)

#──Added for Docker ────────────────────────────────────────────────────────────────
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_static_dir = Path(__file__).resolve().parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str):
    if full_path.startswith("api/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(_static_dir / "index.html")

# ── Health check ───────────────────────────────────────────────────────────
BASE_RESUME_PATH = Path(__file__).resolve().parent / "data" / "base_resume.json"

@app.get("/health", tags=["meta"])
def health():
    """
    Confirms the API is running and key dependencies are reachable.
    Returns 200 with a status dict; never raises — degraded state is reported
    in the payload so the frontend can surface warnings without a hard crash.
    """
    checks = {}

    # 1. Anthropic API key present
    checks["anthropic_api_key"] = bool(os.getenv("ANTHROPIC_API_KEY"))

    # 2. base_resume.json exists and is valid JSON
    if BASE_RESUME_PATH.exists():
        try:
            json.loads(BASE_RESUME_PATH.read_text())
            checks["base_resume"] = True
        except json.JSONDecodeError:
            checks["base_resume"] = "malformed"
    else:
        checks["base_resume"] = False

    # 3. outputs directory is writable
    outputs_dir = Path(__file__).resolve().parent / "outputs"
    outputs_dir.mkdir(exist_ok=True)
    checks["outputs_dir"] = os.access(outputs_dir, os.W_OK)

    overall = all(v is True for v in checks.values())
    return {"status": "ok" if overall else "degraded", "checks": checks}