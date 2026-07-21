# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Local development

**Backend** (Python 3.11+, runs on port 8000):
```bash
cd backend
pip install -r requirements.txt
playwright install chromium
fastapi dev main.py
```

**Frontend** (Node.js 18+, runs on port 5175 in dev):
```bash
cd client
npm install
npm run dev
```

**Lint frontend:**
```bash
cd client && npm run lint
```

**Run backend unit tests** (no API keys needed — all external calls are mocked):
```bash
cd backend/services && pytest test_claude_service.py -v
```

**Smoke-test AI services directly** (requires `.env` with API keys):
```bash
cd backend && python services/claude_service.py        # resume tailoring
cd backend && python test_extract.py                   # keyword extraction
```

### Docker (production-like)
```bash
docker compose up --build        # build and start
docker compose restart           # after changing only JSON resume files
```
Production serves frontend + backend together on port 8000.

### Environment setup
Create `.env` in the project root:
```
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5175
```

## Architecture

This is a full-stack AI resume tailoring app. The frontend is a 5-step wizard (steps 0–4); the backend orchestrates two LLMs, SQLite persistence, and PDF generation via Playwright.

### Request flow

1. **Step 0 — Profile selection**: `GET /api/resumes` discovers all `backend/data/*.json` files dynamically.
2. **Step 1 → 2 — Keyword extraction**: `POST /api/extract-keywords` calls Groq (Llama 3.3 70B, free tier) to extract and ATS-score keywords from the job description.
3. **Step 2 → 3 — Resume generation**: `POST /api/generate-resume` calls Claude Haiku to rewrite bullets, then runs the heuristic ATS scorer. The tailored resume dict is stored in `RESUME_STORE` (in-memory, max 50 entries) keyed by `session_id`. Playwright generates the PDF. The record is also persisted to SQLite.
4. **Step 3 — Tailored preview**: `POST /api/preview-html` renders HTML instantly (no Playwright) with a red page-boundary indicator (`show_boundary=True`). Used for live iframe preview. Inline edits made here are held in `editedResumeData` state in `App.jsx` and forwarded to step 4.
5. **Step 4 — PDF with sliders**: `POST /api/download-custom` runs Playwright with exact user-specified spacing overrides to produce the final PDF.

### Key backend files

- `backend/main.py` — FastAPI app, CORS, router wiring, static file serving (frontend built to `backend/static/` in Docker), health check, `init_db()` call on startup.
- `backend/db.py` — SQLite engine setup via SQLModel. DB lives at `backend/data/resume_history.db` (gitignored). Provides `get_session()` FastAPI dependency.
- `backend/models.py` — `TailoredResumeRecord` SQLModel table: captures company, job_title, profile, JD, selected_keywords, tailored_resume dict, ATS scores, and optional pdf_path per generation.
- `backend/services/claude_service.py` — All core AI logic via direct Anthropic SDK: `extract_keywords()` (Groq), `tailor_resume()` (Claude Haiku), `score_resume()` (heuristic), `regenerate_summary()` / `regenerate_bullets()` (HITL re-generation with user feedback). Also contains `SKILL_TO_CATEGORY` and `PREFERRED_SKILL_CASING` lookup tables, and `determine_skills_to_add()` / `determine_skills_to_show()` helpers that map JD keywords to the correct resume skill categories.
- `backend/services/cover_letter_service.py` — Cover letter generation via **LangChain** (`langchain_anthropic`, `langchain_core`). Uses Claude Haiku; note this is the only place in the backend that uses LangChain rather than the direct Anthropic SDK.
- `backend/services/build_resume_pdf.py` — Renders resume dict → HTML/CSS string (`_render_html`) and then → PDF via Playwright (`build_pdf`, `build_pdf_with_overrides`). Contains the single-page enforcement logic (bidirectional spacing feedback loop). The `show_boundary` flag injects a red line for iframe preview only — never in PDFs.
- `backend/routes/resumes.py` — `GET /api/resumes`. Discovers all `backend/data/*.json` profiles.
- `backend/routes/extract.py` — `POST /api/extract-keywords`. Loads the selected resume JSON, calls `claude_service.extract_keywords()`, cross-references results against the resume to flag gaps, and returns structured `Keyword` objects with `ats_weight` and `present_in_resume`.
- `backend/routes/generate.py` — `POST /api/generate-resume`, `GET /api/download/{filename}`. Owns `RESUME_STORE` (session dict, max 50 entries). `_build_tailored_resume_dict()` merges Claude's response back into the base resume structure and writes to SQLite.
- `backend/routes/regenerate.py` — `POST /api/regenerate-section`. HITL endpoint: accepts `session_id`, `section` (`"summary"` | `"experience"` | `"project"`), optional `target` name, and free-text `feedback`. Mutates `RESUME_STORE` in place and returns updated bullets/summary + fresh ATS score.
- `backend/routes/preview.py` — `POST /api/preview-html`, `POST /api/download-custom`. Reads from `RESUME_STORE` and optionally applies user edits from the frontend before re-rendering.
- `backend/routes/history.py` — `GET /api/history`, `GET /api/history/{id}`, `DELETE /api/history/{id}`, `GET /api/download-history/{id}`, `POST /api/history/{id}/restore`. The restore endpoint loads a SQLite record's `tailored_resume` into `RESUME_STORE` under a fresh `session_id`, allowing `PDFPreview` to re-render and re-download any past generation.
- `backend/routes/cover_letter.py` — `POST /api/generate-cover-letter`. Accepts the tailored resume payload plus job context and delegates to `cover_letter_service`.

### Key frontend files

- `client/src/App.jsx` — Step state machine (steps 0–4), all API calls, data flow between components. `editedResumeData` holds user inline edits from `ResumePreview`; it's forwarded to `PDFPreview` for custom PDF generation. The `API` constant (`http://127.0.0.1:8000`) is passed as `apiBase` prop to every component that needs it.
- `client/src/components/` — One component per step: `ResumePicker` (step 0), `JDInput` (step 1 — captures company name, job title, and JD text), `KeywordSelector` (step 2), `ResumePreview` (step 3 — also drives HITL regeneration via `POST /api/regenerate-section` with per-section feedback), `PDFPreview` (step 4). Also `ResumeHistory` — a full-page history view; clicking a row opens a detail page with "Preview Resume" / "Download PDF" actions that lazily call the restore endpoint then render `PDFPreview`. `PDFPreview` accepts `topOffset` (px, default 64) so it positions its sticky topbar correctly whether rendered inside the wizard or from history. `CoverLetterStep.jsx` exists for cover letter generation (calls `POST /api/generate-cover-letter`) but is not yet wired into the App.jsx step router.

### Resume data format

Profiles live in `backend/data/*.json` (gitignored). Each file is auto-discovered. Key top-level keys:
- `meta` — `label`, `target_roles`, `last_updated`
- `contact`, `summary`, `skills`, `experience`, `projects`, `education`, `certifications`
- `ats_config.skills_order` — array controlling which skill categories render and in what order

Skills categories for tech resumes: `languages`, `ai_ml`, `backend`, `frontend`, `databases_cloud`, `tools`. Non-tech resumes (clinical, admin) use different category names, and the `determine_skills_to_show()` function detects this via `STANDARD_TECH_CATEGORIES` to skip tech-specific filtering.

### PDF spacing system

`_render_html()` accepts `overrides` dict: `font_size` (pt), `margin`/`side_margin` (in), `entry_spacing`/`section_spacing` (pt). `build_pdf()` runs a bidirectional feedback loop — shrinking or expanding spacing to ensure content fills exactly one letter-size page. `build_pdf_with_overrides()` skips the loop and applies exact values.

### AI models

- Keyword extraction: `llama-3.3-70b-versatile` via Groq (`GROQ_MODEL` constant in `claude_service.py`)
- Resume tailoring: `claude-haiku-4-5-20251001` via Anthropic (`CLAUDE_MODEL` constant in `claude_service.py`)
- ATS scoring: local heuristic, no API call
