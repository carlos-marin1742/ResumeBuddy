# ResuméBuddy

An AI-powered resume tailoring tool built for job seekers across tech, clinical, and administrative roles. Paste a job description, select the keywords that matter, and get a tailored single-page PDF resume generated in seconds.

Built as a portfolio project demonstrating full-stack AI engineering: FastAPI backend, React frontend, Groq + Anthropic API integration, automated PDF generation via Playwright, SQLite persistence, and Docker containerization.

---

## How it works

1. **Select your resume profile** — choose from Tech, Clinical Research, or Administrative. Profiles are loaded dynamically from JSON files in `backend/data/`
2. **Paste a job description** — enter the company name, job title, and description. Groq (Llama 3.3 70B) extracts hard skills, tools, soft skills, and role signals, scores each by ATS weight, and flags gaps against your base resume
3. **Select your keywords** — review what's already in your resume vs. what's missing, then confirm the keywords you want to target
4. **Generate** — Claude Haiku rewrites your bullets to naturally incorporate your selected keywords, injects missing skills into the correct categories, scores the result with a heuristic ATS engine, and produces a polished single-page PDF
5. **Preview & adjust** — inline-edit your tailored resume, then fine-tune font size, page margins, entry spacing, and section spacing with live sliders before downloading your custom PDF
6. **Resume History** — every generation is saved to SQLite. Browse, search, re-preview, and re-download past resumes from the history view at any time

---

## Features

- **Multi-profile support** — separate resume profiles for tech, clinical research, and administrative roles, each with role-specific bullet strategies and skill categories
- **Dynamic resume loading** — profiles are discovered automatically from `backend/data/*.json` — add new profiles without touching code
- **Intelligent keyword extraction** — Groq free tier handles fast, structured keyword extraction from job descriptions
- **Skills injection engine** — Python-based lookup tables map selected keywords to the correct skill category with proper casing (e.g. `langchain` → `LangChain` → `ai_ml`)
- **Skills filtering** — irrelevant skill categories are hidden per role type; admin/clinical resumes show only their own categories, not tech stacks
- **Dynamic single-page enforcement** — profile-aware spacing engine with bidirectional feedback loop ensures the PDF always fills one page cleanly regardless of content density
- **Heuristic ATS scoring** — fast, deterministic, zero-cost scoring with keyword coverage, matched/missing keywords, and actionable suggestions
- **Inline resume editing** — edit summary bullets and experience bullets directly in the preview before generating your PDF
- **PDF preview with live sliders** — adjust font size, margins, entry spacing, and section spacing in a live iframe before generating your final PDF
- **Resume history** — SQLite-backed history of every generation with company, role, ATS score, and cached PDF; searchable and filterable by profile
- **Docker support** — fully containerized for consistent cross-platform behavior

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| Keyword extraction | Groq API (Llama 3.3 70B — free tier) |
| Resume tailoring | Anthropic API (Claude Haiku) |
| ATS scoring | Heuristic Python function (no API) |
| PDF generation | Playwright (HTML/CSS → PDF) + pypdf |
| Persistence | SQLite via SQLModel |
| Resume data | Structured JSON (multi-profile) |
| Containerization | Docker, Docker Compose |

---

## Project structure

```
ResumeBuddy/
├── Dockerfile
├── docker-compose.yml
├── .env                              # gitignored — create manually
├── backend/
│   ├── main.py                       # FastAPI app, CORS, routers, static serving, health check
│   ├── db.py                         # SQLite engine setup via SQLModel
│   ├── models.py                     # TailoredResumeRecord SQLModel table
│   ├── requirements.txt
│   ├── routes/
│   │   ├── resumes.py                # GET /api/resumes
│   │   ├── extract.py                # POST /api/extract-keywords
│   │   ├── generate.py               # POST /api/generate-resume, GET /api/download/{file}
│   │   ├── preview.py                # POST /api/preview-html, POST /api/download-custom
│   │   └── history.py                # GET|DELETE /api/history, restore + download endpoints
│   ├── services/
│   │   ├── claude_service.py         # Groq extraction, Claude tailoring, heuristic scoring
│   │   └── build_resume_pdf.py       # HTML/CSS resume renderer → PDF via Playwright
│   └── data/                         # gitignored
│       ├── base_resume.json          # Tech / AI profile
│       ├── base_resume_clinical.json # Clinical research profile
│       ├── base_resume_admin.json    # Administrative profile
│       ├── base_resume_schema.md     # Schema reference
│       └── resume_history.db         # SQLite database (auto-created on first run)
└── client/
    └── src/
        ├── App.jsx                   # 5-step flow orchestration + state management
        └── components/
            ├── ResumePicker.jsx      # Step 0: select resume profile
            ├── JDInput.jsx           # Step 1: enter company, title, and job description
            ├── KeywordSelector.jsx   # Step 2: review and select keywords
            ├── ResumePreview.jsx     # Step 3: tailored preview + inline editing + ATS score
            ├── PDFPreview.jsx        # Step 4: live PDF preview with spacing sliders
            └── ResumeHistory.jsx     # History view: searchable list + detail + re-preview
```

---

## Getting started

### Option 1 — Docker (recommended)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone git@github.com:carlos-marin1742/ResumeBuddy.git
cd ResumeBuddy

# Create your environment file
cp .env.example .env
# Fill in your API keys (see Environment variables below)

# Add your resume JSON files to backend/data/
# (see Resume setup below)

# Build and run
docker compose up --build
```

Open `http://localhost:8000` — frontend and backend served from the same port.

**Rebuilding after code changes:**
```bash
docker compose up --build
```

**After changing only JSON resume files** (no rebuild needed — mounted as volume):
```bash
docker compose restart
```

---

### Option 2 — Local development

**Prerequisites:** Python 3.11+, Node.js 18+, Anthropic API key, Groq API key

**Backend**

```bash
cd backend
pip install -r requirements.txt
playwright install chromium

# Set up environment
cp .env.example .env
# Add ANTHROPIC_API_KEY and GROQ_API_KEY

# Start
fastapi dev main.py
```

Verify health:
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

Create `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5173,http://localhost:3000
```

Get a free Groq API key at [console.groq.com](https://console.groq.com).

---

## Resume setup

Resume profiles live in `backend/data/` and are gitignored. Profiles are discovered automatically — any `*.json` file in the data directory appears in the resume picker.

| File | Profile |
|---|---|
| `base_resume.json` | Tech / AI / Full-Stack |
| `base_resume_clinical.json` | Clinical Research |
| `base_resume_admin.json` | Administrative |

See `base_resume_schema.md` for the full JSON schema. Key sections:

- `meta` — `label`, `target_roles`, `last_updated` (shown in the resume picker)
- `contact` — name, email, phone, links (portfolio, GitHub, LinkedIn)
- `summary` — default text + optional role-specific variants
- `skills` — categorized lists; render order set by `ats_config.skills_order`
- `experience` — bullet objects with `text` and `keywords`
- `projects` — tech stack, links (GitHub + live demo), bullet objects
- `education` / `certifications` — degree and cert entries
- `ats_config` — `skills_order` array controlling which categories render

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/api/resumes` | List all available resume profiles |
| `POST` | `/api/extract-keywords` | Extract and score keywords from a job description (Groq) |
| `POST` | `/api/generate-resume` | Tailor resume, inject skills, score ATS, generate PDF (Claude Haiku) |
| `GET` | `/api/download/{filename}` | Download a generated PDF (auto-fit spacing) |
| `POST` | `/api/preview-html` | Get rendered HTML for iframe preview (instant, no Playwright) |
| `POST` | `/api/download-custom` | Generate PDF with user-specified spacing overrides |
| `GET` | `/api/history` | List all saved resume generations, newest first |
| `GET` | `/api/history/{id}` | Get a single history record |
| `DELETE` | `/api/history/{id}` | Delete a history record |
| `POST` | `/api/history/{id}/restore` | Load a history record into session for re-preview |
| `GET` | `/api/download-history/{id}` | Re-download the cached PDF for a history record |

### POST /api/extract-keywords

```json
{
  "job_description": "string",
  "resume_id": "base_resume"
}
```

### POST /api/generate-resume

```json
{
  "job_description": "string",
  "selected_keywords": ["keyword1", "keyword2"],
  "resume_id": "base_resume",
  "summary_variant": null
}
```

### Response

```json
{
  "summary": "tailored summary text",
  "experiences": [...],
  "projects": [...],
  "skills_to_highlight": [...],
  "skills_added": { "ai_ml": ["LangGraph"] },
  "ats": {
    "overall_score": 78,
    "keyword_coverage": 0.82,
    "matched_keywords": [...],
    "missing_keywords": [...],
    "suggestions": [...]
  },
  "pdf_url": "/api/download/resume_20260601_123456_abc123.pdf",
  "session_id": "a1b2c3d4e5f6...",
  "generated_at": "2026-06-01T12:34:56Z",
  "resume_id": "abc12345"
}
```

### POST /api/preview-html

```json
{
  "session_id": "a1b2c3d4e5f6...",
  "overrides": {
    "font_size": 8.5,
    "margin": 0.4,
    "entry_spacing": 5.0,
    "section_spacing": 6.0
  }
}
```

### POST /api/download-custom

Same body as `/api/preview-html`. Returns a PDF file with the exact spacing overrides applied.

---

## Cost model

| Step | Service | Cost |
|---|---|---|
| Keyword extraction | Groq (Llama 3.3 70B) | Free |
| Resume tailoring | Claude Haiku | ~$0.01/generation |
| ATS scoring | Heuristic (local) | Free |
| PDF preview | Playwright (local) | Free |
| Custom PDF download | Playwright (local) | Free |

Typical cost: **~$0.01 per resume generated.**

---

## License

MIT
