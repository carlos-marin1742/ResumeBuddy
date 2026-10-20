# Repository Guidelines

## Project Layout

```text
ResumeBuddy/
├── backend/
│   ├── main.py                 # FastAPI entry point and production static serving
│   ├── db.py / models.py       # SQLModel engine, migrations, and history model
│   ├── routes/                 # API handlers and route-level pytest tests
│   ├── services/               # AI, ATS, project selection, and PDF services/tests
│   ├── data/                   # Static-profile fixtures and private local inputs
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

`backend/main.py` registers the routers, validates PostgreSQL configuration at startup, configures CORS, and serves the built React app in production. PostgreSQL schema changes are owned by Alembic; generated PDFs, private profile inputs, `client/node_modules/`, and build output are runtime artifacts and must not be committed.

## Architecture and Important Modules

The UI flow is profile selection (`ResumePicker`) → job details (`JDInput`) → keywords (`KeywordSelector`) → editable resume (`ResumePreview`) → HTML/PDF preview (`PDFPreview`) → cover letter (`CoverLetterStep`). `ResumeHistory` is a separate history view. `App.jsx` owns cross-step state.

Backend responsibilities:

- `claude_service.py`: Groq keyword extraction, Claude tailoring/regeneration, skill filtering, and local ATS scoring.
- `project_selection.py`: caps projects at three using work-project priority (`created_at_work`) and job relevance.
- `build_resume_pdf.py`: resume HTML and Playwright PDF generation, including spacing overrides.
- `cover_letter_service.py`: LangChain/Anthropic generation and letter formatting.
- `build_cover_letter_pdf.py`: sanitized filenames and 12pt Times New Roman PDF rendering.
- `pdf_concurrency.py`: process-wide semaphore shared by every Chromium render (`PDF_MAX_CONCURRENCY`, default 2). Waiting longer than `PDF_QUEUE_TIMEOUT_SECONDS` (default 30) raises `PdfBusyError`, which `main.py` answers with 503 and `Retry-After`; routes that wrap PDF builds in `except Exception` must re-raise it first.
- `readiness.py`: the dependency checks behind `/health/ready`.
- `generate.py`: `_build_tailored_resume_dict`, persistence, the bounded in-memory `RESUME_STORE`, and the initial PDF render. The history record is persisted before rendering, so a busy PDF queue or render error returns the full result with `pdf_url: null` and `pdf_status: "pending"`; `ensure_record_pdf` renders on demand for `/api/download-history/{id}` and `/api/download/{filename}`.

## API Routes

- `GET /health`: liveness only (200 `{"status":"ok"}`, no dependency checks); the container `HEALTHCHECK` and compose healthcheck use it.
- `GET /health/ready`: readiness; `SELECT 1` against the database, the `chrome-headless-shell` binary that `chromium.launch()` runs (resolved through Playwright, no launch), and `base_resume.json` only when `STATIC_PROFILES_ENABLED` is true. Failure returns a generic 503. Neither health route is authenticated or rate limited.
- `GET /api/resumes`: available JSON profiles.
- `POST /api/extract-keywords`: extract and compare JD keywords with a profile.
- `POST /api/generate-resume`, `GET /api/download/{filename}`: tailor, score, persist, and download.
- `POST /api/preview-html`, `POST /api/download-custom`: merge user edits and preview/download with spacing controls.
- `POST /api/regenerate-section`: regenerate summary, experience, or project bullets in a session.
- `/api/history`: list/filter, fetch, delete, restore sessions, and download stored resume/cover-letter artifacts.
- `POST /api/generate-cover-letter`, `POST /api/download-cover-letter`: generate, persist, and render cover letters.
- `POST /api/resumes/parse`: temporarily parse a PDF or DOCX into a reviewable resume-builder draft.
- `POST /api/master-resumes`, `PUT/GET /api/master-resumes/{id}`: persist, update, and retrieve user-reviewed master resumes.

## Data, Authentication, and Security

`TailoredResumeRecord` stores job metadata, selected keywords, structured resume JSON, ATS scores, optional cover-letter text, and cached PDF paths. `MasterResumeRecord` separately stores user-reviewed builder data for editing and preview. Both use PostgreSQL, and Alembic owns their schema.

ResumeBuddy uses first-party email/password authentication: bcrypt password hashes, peppered-hash server-side sessions, and email verification. With secure cookies enabled, the browser receives the `__Host-resumebuddy_session` HttpOnly cookie; sessions have idle and absolute expiry. Global middleware protects `/api/*` except `/api/auth/*` and must read the authenticated user's scalar ID before the database session closes; persisted history and master-resume owner mismatches return 404. Keep the absence of account deletion, a password-reset UI, and cross-user isolation tests explicit.

Create root `.env` with `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `AUTH_TOKEN_PEPPER`, SMTP settings, and optional comma-separated `ALLOWED_ORIGINS`. `STATIC_PROFILES_ENABLED` defaults to false; only local development should set it true to expose checked-in static profiles. `db.py` creates its engine lazily, but startup and first real database use still require `DATABASE_URL` or `DATABASE_PASSWORD_FILE`. Keep secrets and personal resume data out of commits. Playwright requires Chromium. Optional `PDF_MAX_CONCURRENCY` (default 2) and `PDF_QUEUE_TIMEOUT_SECONDS` (default 30) bound simultaneous renders. The Docker image installs Chromium into `PLAYWRIGHT_BROWSERS_PATH=/opt/pw` so the non-root `appuser` can launch it, pins both base images to exact tags, and pins every `backend/requirements.txt` entry; update those pins deliberately.

## Development and Validation

```powershell
pip install -r backend/requirements.txt
pip install pytest
playwright install chromium
cd backend; fastapi dev main.py
cd client; npm install; npm run dev
cd client; npm test; npm run lint; npm run build
cd backend && python -m pytest -v
docker compose up --build
```

Vite runs on port 5175 and proxies `/api` to port 8000. Vitest uses jsdom, Testing Library, and `vite.config.js`; tests are colocated as `*.test.jsx`. Docker builds the frontend into `backend/static` and mounts `backend/data` and `backend/outputs`.

Pytest files are named `test_*.py` beside services, under `backend/routes/`, or at the backend package root. Mock Anthropic, Groq, filesystem, database, and Playwright boundaries; cover validation and failure paths. `backend/test_auth_middleware.py` exercises verified, absent, revoked, and unverified cookie-session middleware behavior. `backend/smoke_extract_keywords.py` is a credential-dependent smoke script, not a unit test. With no externally configured database and no private profile files, the latest backend run (inside the built container) was 258 passed, 28 skipped, and 0 failed; the frontend run was 81 passed plus one expected `it.fails`; PostgreSQL migration tests remain opt-in through `POSTGRES_TEST_DATABASE_URL`.

Frontend tests mock `fetch`, clipboard, and browser download boundaries. `CoverLetterStep.test.jsx` contains one `it.fails` regression: clearing the letter unmounts its textarea. Do not remove the marker without fixing and verifying the component. No coverage threshold is enforced.

Resume imports are parsed in memory and must not retain source files. Preserve the 5 MB limit, PDF/DOCX signature checks, review-before-save behavior, and explicit scanned-PDF limitation.

## Working Documents

- `architecture.md`: current system design, boundaries, data flows, and major components.
- `decisions.md`: important technical and product decisions with their rationale.
- `backlog.md`: candidate work that is not yet implemented or committed.
- `handoff.md`: current working state, validation evidence, limitations, and suggested next steps.

Update these documents when a change materially affects their subject. Keep confirmed behavior separate from future ideas.

## Coding and Contribution Conventions

Use four-space Python indentation, `snake_case` functions/modules, `PascalCase` classes, Pydantic request/response models, and FastAPI dependency injection for database sessions. React uses two spaces, `PascalCase` component files, `camelCase` props/functions, functional components, and colocated CSS. Follow ESLint and avoid adding dependencies without clear value.

Keep commits short and imperative, preferably under 72 characters. PRs should explain behavior, list validation commands, identify schema/configuration changes, link issues, and include screenshots for visible UI changes. Preserve unrelated work and never commit secrets, personal resumes, generated PDFs, or the runtime database.
