# ResuméBuddy

An AI-powered resume tailoring tool built for engineers targeting specific roles. Paste a job description, review the extracted keywords, and get a tailored single-page PDF resume — generated in seconds using Claude.

Built as a portfolio project demonstrating full-stack AI engineering: FastAPI backend, React frontend, Anthropic API integration, and automated PDF generation.

---

## What it does

1. **Extracts keywords** from a job description using Claude — hard skills, tools, soft skills, and role signals, each scored by ATS weight and checked against your base resume
2. **Tailors your resume** — rewrites bullets to naturally incorporate your selected keywords without fabricating experience
3. **Scores the output** — runs an ATS compatibility check and surfaces missing keywords and suggestions
4. **Generates a PDF** — single-page, pixel-perfect output via WeasyPrint

---

## Tech stack

| Layer | Stack |
|---|---|
| Frontend | React, Vite |
| Backend | Python, FastAPI |
| AI | Anthropic API (Claude Haiku) |
| PDF generation | WeasyPrint (HTML/CSS → PDF) |
| Resume data | Structured JSON |

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
│   │   ├── claude_service.py     # Keyword extraction, resume tailoring, ATS scoring
│   │   └── build_resume_pdf.py   # HTML/CSS resume template → PDF via WeasyPrint
│   └── data/
│       ├── base_resume.json      # Your resume data (gitignored)
│       └── base_resume_schema.md # Schema reference
└── frontend/
    └── src/
        ├── App.jsx               # Step state, API calls
        └── components/
            ├── JDInput.jsx       # Step 1: paste job description
            ├── KeywordSelector.jsx  # Step 2: review and select keywords
            └── ResumePreview.jsx    # Step 3: tailored preview + PDF download
```

---

## Getting started

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Backend

```bash
cd backend

# Install dependencies
pip install fastapi uvicorn anthropic python-dotenv pydantic weasyprint

# macOS only — WeasyPrint requires Pango for text rendering
brew install pango

# Set up environment
cp .env.example .env
# → Add your ANTHROPIC_API_KEY

# Add your resume data
# Copy base_resume.example.json → data/base_resume.json and fill it in

# Start
uvicorn main:app --reload --port 8000
```

Verify:
```
GET http://127.0.0.1:8000/health
→ { "status": "ok", "checks": { "anthropic_api_key": true, "base_resume": true, "outputs_dir": true } }
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

`backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

## Base resume setup

Your resume lives in `backend/data/base_resume.json` and is gitignored — it never leaves your machine unless you deploy it. See `base_resume_schema.md` for the full schema.

Key sections:

- `contact` — name, email, phone, links
- `summary` — default + role variants (`ai_focused`, `backend_focused`, `ml_focused`)
- `skills` — categorized lists, render order controlled by `ats_config.skills_order`
- `experience` / `projects` — bullet objects with `text`, `keywords`, and `strength`
- `ats_config` — max bullets per section, keyword injection targets

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/api/extract-keywords` | Extract and score keywords from a JD |
| `POST` | `/api/generate-resume` | Tailor, score, and generate PDF |
| `GET` | `/api/download/{filename}` | Download a generated resume |

---

## License

MIT