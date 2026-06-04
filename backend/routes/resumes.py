"""
routes/resumes.py

GET /api/resumes
    Lists all available resume JSON files from backend/data/.
    Returns name, id (filename without extension), and metadata from the file.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class ResumeProfile(BaseModel):
    id: str           # filename without .json, used as resume_id in requests
    name: str         # display name — from meta.label or prettified filename
    target_roles: list[str]
    last_updated: str


class ResumesResponse(BaseModel):
    resumes: list[ResumeProfile]


@router.get("/api/resumes", response_model=ResumesResponse)
def list_resumes() -> ResumesResponse:
    """Return all resume JSON files in the data directory."""
    profiles = []

    for path in sorted(DATA_DIR.glob("*.json")):
        # Skip example/schema files
        if "example" in path.stem or "schema" in path.stem:
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

        meta = data.get("meta", {})

        # Display name: use meta.label if present, otherwise prettify filename
        # e.g. "base_resume" → "Base Resume", "clinical_resume" → "Clinical Resume"
        name = meta.get("label") or path.stem.replace("_", " ").title()

        profiles.append(ResumeProfile(
            id=path.stem,
            name=name,
            target_roles=meta.get("target_roles", []),
            last_updated=meta.get("last_updated", ""),
        ))

    if not profiles:
        raise HTTPException(
            status_code=404,
            detail="No resume profiles found in backend/data/. Add at least one JSON resume file."
        )

    return ResumesResponse(resumes=profiles)