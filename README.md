# ResuméBuddy

An AI-powered resume tailoring tool that takes a job description and your base resume, extracts the keywords that matter most for ATS systems, rewrites your bullets to match, and exports a polished single-page `.docx` — ready to submit.

Built with FastAPI, React, and the Anthropic API (Claude).

---

## How it works

**Step 1 — Paste the job description**
Drop in any job posting. Claude extracts hard skills, soft skills, tools, and role signals, then ranks them by ATS weight and flags gaps against your base resume.

**Step 2 — Select your keywords**
Review the extracted keywords grouped by category. Green = already in your resume. Yellow = gaps to address. Priority keywords are pre-selected; you control the final list.

**Step 3 — Generate & download**
Claude rewrites your resume bullets to naturally incorporate your selected keywords, generates a targeted summary, and scores the result against the JD. Download a formatted `.docx` immediately.

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React + Vite |
| Backend | Python, FastAPI |
| AI | Anthropic API (Claude Haiku) |
| Document generation | Node.js (`docx` library) |
| Resume data | Structured JSON schema |

---

## Project structure

```
ResumeBuddy/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, health check
│   ├── routes/
│   │   ├── extract.py            # POST /api/extract-keywords
│   │   └── generate.py           # POST /api/generate-resume, GET /api/download/{file}
│   ├── services/
│   │   ├── claude_service.py     # Anthropic API — extraction, tailoring, scoring
│   │   ├── resume_builder.py     # Python wrapper for docx generation
│   │   └── build_resume_docx.js  # Node.js document renderer
│   ├── data/
│   │   ├── base_resume.json      # Your resume data (gitignored)
│   │   └── base_resume_schema.md # Schema reference
│   └── outputs/                  # Generated .docx files (gitignored)
└── frontend/
    └── src/
        ├── App.jsx               # Root component, step state, API calls
        └── components/
            ├── JDInput.jsx       # Step 1: job description input
            ├── KeywordSelector.jsx  # Step 2: keyword review & selection
            └── ResumePreview.jsx    # Step 3: tailored preview + download
```

---

## Getting started

### Prerequisites

- Python 3.10+
- Node.js 18+
- An [Anthropic API key](https://console.anthropic.com/)

### Backend

```bash
cd backend

# Install Python dependencies
pip install fastapi uvicorn anthropic python-dotenv pydantic

# Install Node dependencies for the docx builder
cd services && npm install && cd ..

# Create your .env file
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

# Add your resume data
# Copy base_resume.example.json → data/base_resume.json and fill it in

# Start the server
uvicorn main:app --reload --port 8000
```

Verify everything is healthy:
```
GET http://127.0.0.1:8000/health
```

Expected response:
```json
{ "status": "ok", "checks": { "anthropic_api_key": true, "base_resume": true, "outputs_dir": true } }
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` — the backend must be running on port `8000`.

---

## Environment variables

Create `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Base resume setup

Your resume lives in `backend/data/base_resume.json` and is **gitignored** — it never leaves your machine unless you deploy it.

Use `backend/data/base_resume_schema.md` as a reference for the full schema. The key sections are:

- `contact` — name, email, phone, links
- `summary` — default + role-specific variants (`ai_focused`, `backend_focused`, `ml_focused`)
- `skills` — categorized skill lists
- `experience` — roles with bullet objects containing `text`, `keywords`, and `strength`
- `projects` — same bullet structure as experience
- `education` + `certifications`
- `ats_config` — controls max bullets, skills render order, keyword injection targets

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/api/extract-keywords` | Extract and categorize keywords from a JD |
| `POST` | `/api/generate-resume` | Tailor resume, score it, generate .docx |
| `GET` | `/api/download/{filename}` | Download a generated resume file |

### `POST /api/extract-keywords`

```json
{ "job_description": "string" }
```

### `POST /api/generate-resume`

```json
{
  "job_description": "string",
  "selected_keywords": ["Python", "FastAPI", "LangChain"],
  "summary_variant": "ai_focused"
}
```

---

## License

MIT