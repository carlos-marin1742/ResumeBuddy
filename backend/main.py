"""
main.py
-------
FastAPI application entry point for the ATS Resume Builder.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from db import init_db

from routes.extract import router as extract_router
from routes.generate import router as generate_router
from routes.preview import router as preview_router
from routes.resumes import router as resumes_router
from routes.history import router as history_router
from routes.cover_letter import router as cover_letter_router


load_dotenv()

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(
    title="ATS Resume Builder",
    description="Tailors resumes for specific job descriptions using Claude.",
    version="1.0.0",
    lifespan=lifespan
)

_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8000"
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resumes_router)
app.include_router(extract_router)
app.include_router(generate_router)
app.include_router(preview_router)
app.include_router(history_router)
app.include_router(cover_letter_router)
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