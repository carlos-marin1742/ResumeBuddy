"""
resume_builder.py
-----------------
Generates a polished .docx resume from a structured resume dict.

The heavy lifting (layout, fonts, styles) is done by build_resume_docx.js
via a subprocess call. This module is the Python interface generate.py uses.

Public API:
    build_docx(resume_data: dict, output_path: Path | str) -> Path
        Writes a .docx file to output_path and returns the path.
        Raises ResumeBuilderError on any failure.
"""

import json
import subprocess
import sys
from pathlib import Path

# ── Path to the JS generator ───────────────────────────────────────────────
# Expects build_resume_docx.js to live alongside this file in services/
_JS_BUILDER = Path(__file__).resolve().parent / "build_resume_docx.js"


class ResumeBuilderError(Exception):
    """Raised when document generation fails."""


def build_docx(resume_data: dict, output_path: "Path | str") -> Path:
    """
    Generate a .docx resume from a structured resume dict.

    Args:
        resume_data:  Full resume dict (base_resume.json merged with tailored
                      content from claude_service.py). Expected keys:
                        contact, tailored_summary, skills, experience,
                        projects, education, certifications, ats_config,
                        skills_to_highlight (optional)
        output_path:  Destination path for the .docx file.
                      Parent directory must already exist.

    Returns:
        Path to the written .docx file.

    Raises:
        ResumeBuilderError: If the JS generator exits non-zero or the file
                            is not created.
        FileNotFoundError:  If build_resume_docx.js is missing.
    """
    output_path = Path(output_path)

    if not _JS_BUILDER.exists():
        raise FileNotFoundError(
            f"JS generator not found at {_JS_BUILDER}. "
            "Ensure build_resume_docx.js is in backend/services/."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    resume_json = json.dumps(resume_data, ensure_ascii=False)

    try:
        result = subprocess.run(
            ["node", str(_JS_BUILDER), str(output_path)],
            input=resume_json,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise ResumeBuilderError("Document generation timed out after 30 seconds.")
    except FileNotFoundError:
        raise ResumeBuilderError(
            "Node.js is not installed or not on PATH. "
            "Install Node.js 18+ to enable document generation."
        )

    if result.returncode != 0:
        raise ResumeBuilderError(
            f"Document generation failed (exit {result.returncode}).\n"
            f"stderr: {result.stderr.strip()}\n"
            f"stdout: {result.stdout.strip()}"
        )

    if not output_path.exists():
        raise ResumeBuilderError(
            f"JS generator exited successfully but {output_path} was not created."
        )

    return output_path


# ── Quick smoke test ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    sample = {
        "contact": {
            "name": "Carlos Marin",
            "location": "Houston, TX",
            "phone": "713-791-3494",
            "email": "carlosmarinjr1@gmail.com",
            "portfolio": "https://carlos-marin1742.github.io/my-portfolio/",
            "github": "https://github.com/carlos-marin1742",
            "linkedin": "https://www.linkedin.com/in/carlos-marin-90482b13b/",
        },
        "tailored_summary": (
            "AI-focused full-stack engineer with hands-on experience building RAG pipelines, "
            "LLM-integrated applications, and computer vision systems. Dual-certified by IBM."
        ),
        "skills": {
            "ai_ml":     ["LangChain", "RAG", "PyTorch", "LLMs", "Prompt Engineering"],
            "languages": ["Python", "JavaScript", "SQL"],
            "backend":   ["FastAPI", "Flask", "Node.js"],
            "frontend":  ["React", "Streamlit"],
        },
        "skills_to_highlight": ["Python", "LangChain", "FastAPI"],
        "experience": [
            {
                "company":    "Houston Methodist Hospital",
                "location":   "Houston, TX",
                "title":      "Clinical Research Coordinator",
                "start_date": "2023-04",
                "end_date":   "2025-09",
                "bullets": [
                    {"text": "Drove a 20% increase in enrollment throughput by re-engineering pre-screening workflows."},
                    {"text": "Cut data query resolution time by 30% via a structured weekly data review pipeline."},
                ],
            }
        ],
        "projects": [
            {
                "name":       "Agent Data Scientist",
                "tech_stack": ["Python", "FastAPI", "LangChain", "React"],
                "links":      {"github": "https://github.com/carlos-marin1742/AgentDataScientist"},
                "bullets": [
                    {"text": "Architected a full-stack AI app with a LangChain-Groq pipeline to automate EDA."},
                ],
            }
        ],
        "education": [
            {
                "institution":     "University of Houston — Downtown",
                "degree":          "BS",
                "field":           "Biological and Physical Sciences",
                "graduation_date": "2017-05",
            }
        ],
        "certifications": [
            {"name": "IBM AI Engineer", "issuer": "IBM", "type": "Professional Certificate", "date": "2026-04"},
        ],
        "ats_config": {
            "skills_order": ["ai_ml", "languages", "backend", "frontend"],
        },
    }

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        out = Path(f.name)

    build_docx(sample, out)
    print(f"✓ Generated: {out}  ({out.stat().st_size:,} bytes)")
