 # ResuméBuddy

An AI-powered resume tailoring tool built for job seekers across tech, clinical, and administrative roles. Paste a job description, select the keywords that matter, and get a tailored single-page PDF resume generated in seconds using Claude.

Built as a portfolio project demonstrating full-stack AI engineering: FastAPI backend, React frontend, Anthropic API integration, automated PDF generation via Playwright, and Docker containerization.

---

## How it works

1. **Paste a job description** — Claude extracts hard skills, tools, soft skills, and role signals, scores each by ATS weight, and flags gaps against your base resume
2. **Select your keywords** — review what's already in your resume vs. what's missing, then confirm the keywords you want to target
3. **Generate** — Claude rewrites your bullets to naturally incorporate your selected keywords, injects missing skills into the appropriate skills categories, scores the result for ATS compatibility, and produces a polished single-page PDF

---

## Features

- **Multi-profile support** — separate resume profiles for tech, clinical research, and administrative roles, each with role-specific bullet strategies and skill categories
- **Intelligent skills injection** — missing keywords selected by the user are automatically added to the most relevant skills category in the generated resume
- **Dynamic single-page enforcement** — profile-aware spacing engine ensures the PDF always fills one page cleanly regardless of content density
- **ATS scoring** — every generated resume is scored for keyword coverage and compatibility with actionable improvement suggestions
- **Docker support** — fully containerized for consistent cross-platform behavior (eliminates Windows/macOS Playwright conflicts)

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| AI | Anthropic API (Claude Haiku) |
| PDF generation | Playwright (HTML/CSS → PDF) |
| Resume data | Structured JSON (multi-profile) |
| Containerization | Docker, Docker Compose |

---

## Project structure

```
ResumeBuddy/
├── Dockerfile
├── docker-compose.yml
├── .env                          # gitignored — create manually
├── backend/
│   ├── main.py                   # FastAPI app, CORS, static frontend serving, health check
│   ├── requirements.txt
│   ├── routes/
│   │   ├── extract.py            # POST /api/extract-keywords
│   │   └── generate.py           # POST /api/generate-resume, GET /api/download/{file}
│   ├── services/
│   │   ├── claude_service.py     # Keyword extraction, resume tailoring, ATS scoring
│   │   └── build_resume_pdf.py   # Profile-aware HTML/CSS resume template → PDF via Playwright
│   └── data/
│       ├── base_resume.json          # Resume profile (gitignored)
│       └── base_resume_schema.md     # Schema reference
└── client/
    └── src/
        ├── App.jsx
        └── components/
            ├── JDInput.jsx          # Step 1: paste job description
            ├── KeywordSelector.jsx  # Step 2: review and select keywords
            └── ResumePreview.jsx    # Step 3: tailored preview + PDF download
```

---

## Getting started

### Option 1 — Docker (recommended)

The fastest way to run ResumeBuddy on any machine with no Python or Node setup required.

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone git@github.com:carlos-marin1742/ResumeBuddy.git
cd ResumeBuddy

# Create your environment file
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
echo "ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8000" >> .env

# Add your resume data (see Resume setup below)

# Build and run
docker compose up --build
```

Open `http://localhost:8000` — the frontend and backend are served from the same port.

---

### Option 2 — Local development

**Prerequisites:** Python 3.10+, Node.js 18+, an [Anthropic API key](https://console.anthropic.com/)

**Backend**

```bash
cd backend

# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Set up environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Add your resume data
# Copy base_resume.example.json → data/base_resume.json and fill it in

# Start
uvicorn main:app --reload --port 8000
```

Verify everything is healthy:
```
GET http://127.0.0.1:8000/health
```
```json
{
  "status": "ok",
  "checks": {
    "anthropic_api_key": true,
    "base_resume": true,
    "outputs_dir": true
  }
}
```

**Frontend**

```bash
cd client
npm install
npm run dev
```

Open `http://localhost:5173` with the backend running on port 8000.

---

## Environment variables

Create `.env` in the project root (Docker) or `backend/.env` (local dev):

```
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5173,http://localhost:3000
```

---

## Resume setup

Your resume data lives in `backend/data/` and is gitignored. Three profiles are supported:

| File | Profile | Activated by |
|---|---|---|
| `base_resume.json` | Tech / AI / Full-Stack | `profile: "tech"` |
| `base_resume_clinical.json` | Clinical Research | `profile: "clinical"` |
| `base_resume_admin.json` | Administrative | `profile: "admin"` |

See `base_resume_schema.md` for the full schema. Key sections:

- `contact` — name, email, phone, links
- `summary` — default text + role-specific variants
- `skills` — categorized lists, render order set by `ats_config.skills_order`
- `experience` / `projects` — bullet objects with `text`, `keywords`, and `strength`
- `ats_config` — max bullets per section, keyword injection targets

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/api/extract-keywords` | Extract and score keywords from a job description |
| `POST` | `/api/generate-resume` | Tailor resume, inject skills, score ATS compatibility, generate PDF |
| `GET` | `/api/download/{filename}` | Download a generated resume PDF |

### Request: POST /api/generate-resume

```json
{
  "job_description": "string",
  "selected_keywords": ["keyword1", "keyword2"],
  "profile": "tech | clinical | admin",
  "summary_variant": "ai_focused | backend_focused | ml_focused | null"
}
```

### Response

```json
{
  "summary": "tailored summary text",
  "experiences": [...],
  "skills_to_highlight": [...],
  "skills_added": { "tools": ["Docker", "Tailwind CSS"] },
  "ats": {
    "overall_score": 78,
    "keyword_coverage": 0.82,
    "matched_keywords": [...],
    "missing_keywords": [...],
    "suggestions": [...]
  },
  "pdf_url": "/api/download/resume_20260528_123456_abc123.pdf",
  "generated_at": "2026-05-28T12:34:56Z",
  "resume_id": "abc12345"
}
```

---

## License

MIT