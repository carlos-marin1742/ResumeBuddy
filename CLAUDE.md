# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Layout

```text
ResumeBuddy/
├── backend/
│   ├── main.py                 # FastAPI entry point and production static serving
│   ├── db.py / models.py       # SQLModel engine, migrations, and history model
│   ├── routes/                 # API handlers and route-level pytest tests
│   ├── services/               # AI, ATS, project selection, and PDF services/tests
│   ├── data/                   # Resume schema, private profiles, and SQLite history
│   ├── outputs/                # Generated PDFs (gitignored)
│   └── requirements.txt
├── client/
│   ├── src/
│   │   ├── App.jsx             # Multi-step workflow and shared client state
│   │   ├── components/         # React components, colocated CSS, and *.test.jsx
│   │   ├── test/setup.js       # Vitest/Testing Library global cleanup and matchers
│   │   └── assets/
│   ├── public/                 # Directly served static assets
│   ├── package.json
│   └── vite.config.js          # Vite dev proxy and Vitest jsdom configuration
├── Dockerfile / docker-compose.yml
├── README.md / CLAUDE.md / architecture.md
├── decisions.md / backlog.md / handoff.md
└── AGENTS.md
```

`backend/main.py` registers the routers, initializes SQLite, configures CORS, and serves the built React app in production. Personal resume JSON, `backend/data/resume_history.db`, `backend/outputs/`, `client/node_modules/`, and build output are runtime artifacts and must not be committed.

The SQLite ignore rule only affects untracked files. If `backend/data/resume_history.db` is already tracked, run `git rm --cached backend/data/resume_history.db` once and commit the index removal; the local database remains intact. Verify `git ls-files backend/data/resume_history.db` returns no output before using broad staging commands.

## Architecture and Important Modules

The UI flow is profile selection (`ResumePicker`) → job details (`JDInput`) → keywords (`KeywordSelector`) → editable resume (`ResumePreview`) → HTML/PDF preview (`PDFPreview`) → cover letter (`CoverLetterStep`). `ResumeHistory` is a separate history view. `App.jsx` owns cross-step state.

Backend responsibilities:

- `claude_service.py`: Groq keyword extraction, Claude tailoring/regeneration, skill filtering, and local ATS scoring.
- `project_selection.py`: caps projects at three using work-project priority (`created_at_work`) and job relevance.
- `build_resume_pdf.py`: resume HTML and Playwright PDF generation, including spacing overrides.
- `cover_letter_service.py`: LangChain/Anthropic generation and letter formatting.
- `build_cover_letter_pdf.py`: sanitized filenames and 12pt Times New Roman PDF rendering.
- `generate.py`: `_build_tailored_resume_dict`, persistence, the bounded in-memory `RESUME_STORE`, and initial PDF generation.

## API Routes

- `GET /health`, `GET /api/resumes`: readiness and available JSON profiles.
- `POST /api/extract-keywords`: extract and compare JD keywords with a profile.
- `POST /api/generate-resume`, `GET /api/download/{filename}`: tailor, score, persist, and download.
- `POST /api/preview-html`, `POST /api/download-custom`: merge user edits and preview/download with spacing controls.
- `POST /api/regenerate-section`: regenerate summary, experience, or project bullets in a session.
- `/api/history`: list/filter, fetch, delete, restore sessions, and download stored resume/cover-letter artifacts.
- `POST /api/generate-cover-letter`, `POST /api/download-cover-letter`: generate, persist, and render cover letters.
- `POST /api/resumes/parse`: parse PDF or DOCX content into a reviewable builder draft without retaining the source file.
- `POST /api/master-resumes`, `PUT/GET /api/master-resumes/{id}`: persist, update, and retrieve reviewed master resumes. Each skill group is `{key, category, items[]}`; the adapter uses `key` as the profile skill-dict key, falling back to an underscore slug of `category`, then `skill_{index}`. `items` accepts an array (passed through unchanged) or a string on input; a string is split server-side by `split_skill_items` in `services/master_resume_adapter.py` — newline anywhere splits on lines with commas kept literal, otherwise splits on commas except commas nested inside `()`/`[]`, trimming each item and dropping blanks. The array shape is always what gets persisted.

## Data, Authentication, and Security

`TailoredResumeRecord` stores job-specific generation history. `MasterResumeRecord` stores reviewed resume-builder data for editing and preview. Both use `backend/data/resume_history.db`. `init_db()` creates tables and applies the additive cover-letter migration.

There is currently **no authentication or authorization**; all API and history routes are open to any client that can reach the server. Do not imply per-user isolation. Preserve path validation, input limits, HTML escaping, and `Cache-Control: no-store` behavior.

Because there is no auth, `main.py` rate-limits the AI-backed POST routes (`/api/extract-keywords`, `/api/generate-resume`, `/api/regenerate-section`, `/api/generate-cover-letter`) per client IP via an in-memory sliding window (`RATE_LIMIT_MAX_REQUESTS`, default 20; `RATE_LIMIT_WINDOW_SECONDS`, default 300; both env-overridable), returning 429 once exceeded. Add any new paid-API route to `_RATE_LIMITED_PATHS` in `main.py`. A second middleware adds `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` headers to every response; do not remove either middleware.

Create root `.env` with `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, and optional comma-separated `ALLOWED_ORIGINS`. Keep secrets and personal resume data out of commits. Playwright requires Chromium.

Tailoring derives its occupation descriptor from optional `meta.occupation`, then `meta.target_roles`, then the resume title, with a neutral fallback; do not branch the persona on fixed role types.

## Development and Validation

```bash
pip install -r backend/requirements.txt
pip install pytest
playwright install chromium
cd backend && fastapi dev main.py
cd client && npm install && npm run dev
cd client && npm test && npm run lint && npm run build
cd backend && python -m pytest -v --deselect routes/test_generate.py::test_summary_variant_changes_only_the_default_summary
docker compose up --build
```

Vite runs on port 5175 and proxies `/api` to port 8000. Vitest uses jsdom, Testing Library, and `vite.config.js`; tests are colocated as `*.test.jsx`. Docker builds the frontend into `backend/static` and mounts `backend/data` and `backend/outputs`.

To run a single test: `cd backend && pytest routes/test_master_resumes.py::test_create_and_fetch_master_resume -v` (must run from `backend/` — imports like `from models import ...` assume it's on `sys.path`) or `cd client && npx vitest run src/components/ResumeBuilder.test.jsx -t "adds and saves labeled skill categories"`.

Pytest files are named `test_*.py` beside services, under `backend/routes/`, or at the backend package root (e.g. `backend/test_main.py`, which covers the rate-limit and security-header middleware) — plain `pytest` from `backend/` collects all of them. Mock Anthropic, Groq, filesystem, database, and Playwright boundaries; cover validation and failure paths. `backend/smoke_extract_keywords.py` is a credential-dependent smoke script, not a unit test.

Profile-fixture skills HTML goldens live in `backend/services/golden/`; regenerate them deliberately (never during a normal test run) with `cd backend && $env:UPDATE_SKILLS_HTML_GOLDENS=1; python -m pytest services/test_profile_skills_golden.py`.

Frontend tests mock `fetch`, clipboard, and browser download boundaries. `CoverLetterStep.test.jsx` contains one `it.fails` regression: clearing the letter unmounts its textarea. Do not remove the marker without fixing and verifying the component. No coverage threshold is enforced.

Resume imports (`POST /api/resumes/parse`) are parsed in memory and must not retain the source file. Preserve the 5 MB upload limit (`MAX_UPLOAD_BYTES` in `resume_import.py`), PDF/DOCX signature checks, review-before-save behavior, and the explicit scanned-PDF limitation.

## Working Documents

- `architecture.md`: current system design, boundaries, data flows, and major components.
- `decisions.md`: important technical and product decisions with their rationale.
- `backlog.md`: candidate work that is not yet implemented or committed.
- `handoff.md`: current working state, validation evidence, limitations, and suggested next steps.

Update these documents when a change materially affects their subject. Keep confirmed behavior separate from future ideas.

## Coding and Contribution Conventions

Use four-space Python indentation, `snake_case` functions/modules, `PascalCase` classes, Pydantic request/response models, and FastAPI dependency injection for database sessions. React uses two spaces, `PascalCase` component files, `camelCase` props/functions, functional components, and colocated CSS. Follow ESLint and avoid adding dependencies without clear value.

Keep commits short and imperative, preferably under 72 characters. PRs should explain behavior, list validation commands, identify schema/configuration changes, link issues, and include screenshots for visible UI changes. Preserve unrelated work and never commit secrets, personal resumes, generated PDFs, or the runtime database.
