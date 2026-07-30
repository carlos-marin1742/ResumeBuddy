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
6. **Generate a cover letter** — create an editable letter grounded in the tailored resume, then download it as a 12pt Times New Roman PDF
7. **Resume History** — every generation is saved to SQLite with its job description, tailored resume, ATS result, and optional cover letter. Browse, search, preview, and download past artifacts

---

## Features

- **Multi-profile support** — separate resume profiles for tech, clinical research, and administrative roles, each with role-specific bullet strategies and skill categories
- **Dynamic resume loading** — profiles are discovered automatically from `backend/data/*.json` — add new profiles without touching code
- **Intelligent keyword extraction** — Groq free tier handles fast, structured keyword extraction from job descriptions
- **Skills injection engine** — Python-based lookup tables map selected keywords to the correct skill category with proper casing (e.g. `langchain` → `LangChain` → `ai_ml`)
- **Skills filtering** — irrelevant skill categories are hidden per role type; admin/clinical resumes show only their own categories, not tech stacks
- **Relevant project selection** — profiles with more than three projects are capped at the three most relevant to the job; projects marked `created_at_work: true` receive priority
- **Dynamic single-page enforcement** — profile-aware spacing engine with bidirectional feedback loop ensures the PDF always fills one page cleanly regardless of content density
- **Heuristic ATS scoring** — fast, deterministic, zero-cost scoring with keyword coverage, matched/missing keywords, and actionable suggestions
- **Inline resume editing** — edit summary bullets and experience bullets directly in the preview before generating your PDF
- **PDF preview with live sliders** — adjust font size, margins, entry spacing, and section spacing in a live iframe before generating your final PDF
- **Editable cover letters** — generate from the tailored resume, edit in place, copy to the clipboard, and download as PDF
- **Resume history** — SQLite-backed history with company, role, job description, ATS score, cached resume PDF, and stored cover letter; searchable and filterable by profile
- **Docker support** — fully containerized for consistent cross-platform behavior

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite |
| Frontend testing | Vitest, jsdom, Testing Library |
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
│   ├── models.py                     # Tailored and master resume SQLModel tables
│   ├── requirements.txt
│   ├── routes/
│   │   ├── resumes.py                # GET /api/resumes
│   │   ├── resume_import.py          # Parse PDF/DOCX into an editable draft
│   │   ├── master_resumes.py         # Create, fetch, and update reviewed resumes
│   │   ├── extract.py                # POST /api/extract-keywords
│   │   ├── generate.py               # POST /api/generate-resume, GET /api/download/{file}
│   │   ├── preview.py                # HTML preview and custom PDF download
│   │   ├── regenerate.py             # Regenerate an edited resume section
│   │   ├── cover_letter.py           # Generate, store, and download cover letters
│   │   ├── history.py                # History CRUD, restore, and artifact downloads
│   │   └── test_*.py                 # Route-level pytest tests
│   ├── services/
│   │   ├── claude_service.py         # Groq extraction, Claude tailoring, heuristic scoring
│   │   ├── project_selection.py      # Select up to three job-relevant projects
│   │   ├── cover_letter_service.py   # Grounded cover-letter generation and formatting
│   │   ├── build_cover_letter_pdf.py # 12pt Times New Roman letter PDF renderer
│   │   ├── build_resume_pdf.py       # HTML/CSS resume renderer → PDF via Playwright
│   │   ├── resume_parser.py          # Deterministic resume field extraction
│   │   └── test_*.py                 # Service-level pytest tests
│   └── data/                         # Private profiles and runtime data are gitignored
│       ├── base_resume.json          # Tech / AI profile
│       ├── base_resume_clinical.json # Clinical research profile
│       ├── base_resume_admin.json    # Administrative profile
│       ├── base_resume_schema.md     # Schema reference
│       └── resume_history.db         # SQLite database (auto-created on first run)
└── client/
    ├── vite.config.js                # Dev proxy and Vitest/jsdom configuration
    └── src/
        ├── App.jsx                   # Resume and cover-letter workflow state
        ├── App.test.jsx              # Workflow integration tests
        ├── test/setup.js             # Testing Library setup and cleanup
        └── components/
            ├── ResumePicker.jsx      # Step 0: select resume profile
            ├── ResumeBuilder.jsx     # Create/import, review, and save a master resume
            ├── MasterResumePreview.jsx # Read-only saved resume preview
            ├── JDInput.jsx           # Step 1: enter company, title, and job description
            ├── KeywordSelector.jsx   # Step 2: review and select keywords
            ├── ResumePreview.jsx     # Step 3: tailored preview + inline editing + ATS score
            ├── PDFPreview.jsx        # Step 4: live PDF preview with spacing sliders
            ├── CoverLetterStep.jsx   # Step 5: generate, edit, copy, and download
            ├── ResumeHistory.jsx     # History list, details, previews, and downloads
            └── *.test.jsx            # Colocated component tests
```

---

## Getting started

### Option 1 — Docker (recommended)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
git clone git@github.com:carlos-marin1742/ResumeBuddy.git
cd ResumeBuddy

# Create .env in the repository root and add the variables shown below

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

# Create ../.env and add ANTHROPIC_API_KEY and GROQ_API_KEY

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

Open `http://localhost:5175` with the backend running on port 8000.

---

## Testing and validation

Install backend test tooling separately because `pytest` is not in the runtime requirements:

```bash
pip install pytest
cd backend
pytest routes -v --deselect routes/test_generate.py::test_summary_variant_changes_only_the_default_summary
```

The credential-dependent `backend/smoke_extract_keywords.py` script is a manual smoke check and is not collected by pytest. A regression test documents that summary variants are currently ignored.

Frontend validation:

```bash
cd client
npm test
npm run lint
npm run build
```

Vitest currently reports one expected regression in `CoverLetterStep.test.jsx`: clearing the letter unmounts its editor.

---

## Environment variables

Create `.env` in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5175,http://localhost:3000
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
- `projects` — tech stack, links (GitHub + live demo), bullet objects, and optional `created_at_work` priority metadata
- `education` / `certifications` — degree and cert entries
- `ats_config` — `skills_order` array controlling which categories render

---

## Runtime data and Git

`backend/data/resume_history.db` is created locally by the backend and stores personal resume and application data. It is intentionally gitignored and must not be committed.

If the database was tracked before the ignore rule was added, remove it from the index once without deleting your local data:

```bash
git rm --cached backend/data/resume_history.db
git ls-files backend/data/resume_history.db
```

The second command should produce no output. Once that index removal is committed, `git add .` will respect the ignore rule for the database. Always review `git status --short` before committing.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/api/resumes` | List all available resume profiles |
| `POST` | `/api/resumes/parse` | Parse a PDF or DOCX into an editable resume draft |
| `POST` | `/api/master-resumes` | Save a reviewed master resume |
| `GET` | `/api/master-resumes/{id}` | Fetch a saved master resume |
| `PUT` | `/api/master-resumes/{id}` | Update a saved master resume |
| `POST` | `/api/extract-keywords` | Extract and score keywords from a job description (Groq) |
| `POST` | `/api/generate-resume` | Tailor resume, inject skills, score ATS, generate PDF (Claude Haiku) |
| `GET` | `/api/download/{filename}` | Download a generated PDF (auto-fit spacing) |
| `POST` | `/api/preview-html` | Get rendered HTML for iframe preview (instant, no Playwright) |
| `POST` | `/api/download-custom` | Generate PDF with user-specified spacing overrides |
| `POST` | `/api/regenerate-section` | Regenerate a summary, experience, or project section |
| `POST` | `/api/generate-cover-letter` | Generate and store a cover letter grounded in the tailored resume |
| `POST` | `/api/download-cover-letter` | Download the current cover letter as a 12pt Times New Roman PDF |
| `GET` | `/api/download-history-cover-letter/{id}` | Download a cover letter stored with a history record |
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
  "resume_id": "base_resume",
  "history_id": "abc12345",
  "person_name": "Candidate Name"
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
