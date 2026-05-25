# ResuméBuddy

An AI-powered resume tailoring tool built for engineers. Paste a job description, select the keywords that matter, and get a tailored single-page PDF resume generated in seconds using Claude.

Built as a portfolio project demonstrating full-stack AI engineering: FastAPI backend, React frontend, Anthropic API integration, and automated PDF generation via Playwright.

---

## How it works

1. **Paste a job description** — Claude extracts hard skills, tools, soft skills, and role signals, scores each by ATS weight, and flags gaps against your base resume
2. **Select your keywords** — review what's already in your resume vs. what's missing, then confirm the keywords you want to target
3. **Generate** — Claude rewrites your bullets to naturally incorporate your selected keywords, scores the result for ATS compatibility, and produces a polished single-page PDF

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| AI | Anthropic API (Claude Haiku) |
| PDF generation | Playwright (HTML/CSS → PDF) |
| Resume data | Structured JSON |

---

## Project structure

```
ResumeBuddy/
├── backend/
│   ├── main.py                   # FastAPI app, CORS, health check
│   ├── requirements.txt
│   ├── routes/
│   │   ├── extract.py            # POST /api/extract-keywords
│   │   └── generate.py           # POST /api/generate-resume, GET /api/download/{file}
│   ├── services/
│   │   ├── claude_service.py     # Keyword extraction, resume tailoring, ATS scoring
│   │   └── build_resume_pdf.py   # HTML/CSS resume template → PDF via Playwright
│   └── data/
│       ├── base_resume.json      # Your resume data (gitignored)
│       └── base_resume_schema.md # Schema reference
└── frontend/
    └── src/
        ├── App.jsx
        └── components/
            ├── JDInput.jsx          # Step 1: paste job description
            ├── KeywordSelector.jsx  # Step 2: review and select keywords
            └── ResumePreview.jsx    # Step 3: tailored preview + PDF download
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
{ "status": "ok", "checks": { "anthropic_api_key": true, "base_resume": true, "outputs_dir": true } }
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` with the backend running on port 8000.

---

## Environment variables

Create `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Resume setup

Your resume lives in `backend/data/base_resume.json` and is gitignored. See `base_resume_schema.md` for the full schema. Key sections:

- `contact` — name, email, phone, links
- `summary` — default text + role-specific variants (`ai_focused`, `backend_focused`, `ml_focused`)
- `skills` — categorized lists, render order set by `ats_config.skills_order`
- `experience` / `projects` — bullet objects with `text`, `keywords`, and `strength`
- `ats_config` — max bullets per section, keyword injection targets

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/api/extract-keywords` | Extract and score keywords from a job description |
| `POST` | `/api/generate-resume` | Tailor resume, score ATS compatibility, generate PDF |
| `GET` | `/api/download/{filename}` | Download a generated resume |

---

## License

MIT