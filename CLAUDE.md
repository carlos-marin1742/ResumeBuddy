# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

`backend/main.py` registers routers, configures CORS, and serves the built React app in production. PostgreSQL schema changes are owned by Alembic; the Docker entrypoint runs `alembic upgrade head` before starting the app.

## Architecture and Important Modules

The UI flow is profile selection (`ResumePicker`) → job details (`JDInput`) → keywords (`KeywordSelector`) → editable resume (`ResumePreview`) → HTML/PDF preview (`PDFPreview`) → cover letter (`CoverLetterStep`). `ResumeHistory` is a separate history view. `App.jsx` owns cross-step state.

The read-only master-resume preview intentionally mirrors the generated PDF typography contract: same Arial stack, black text, #555 secondary text, uppercase section rules, and 8.5pt-based sizing on the 816x1056 Letter page. Browser margins remain separate from the generated PDF page fit, but the semantic formatting remains aligned.

Backend responsibilities:

- `claude_service.py`: Groq keyword extraction, Claude tailoring/regeneration, skill filtering, and local ATS scoring.
- `project_selection.py`: caps projects at three using work-project priority (`created_at_work`) and job relevance.
- `build_resume_pdf.py`: resume HTML and Playwright PDF generation, including spacing overrides.
- `cover_letter_service.py`: LangChain/Anthropic generation and letter formatting.
- `build_cover_letter_pdf.py`: sanitized filenames and 12pt Times New Roman PDF rendering.
- `pdf_concurrency.py`: process-wide semaphore shared by every Chromium render (`PDF_MAX_CONCURRENCY`, default 2). Waiting longer than `PDF_QUEUE_TIMEOUT_SECONDS` (default 30) raises `PdfBusyError`, which `main.py` answers with 503 and `Retry-After`; routes that wrap PDF builds in `except Exception` must re-raise it first. Each render also runs under a watchdog (`PDF_RENDER_TIMEOUT_SECONDS`, default 45): a hung Chromium tree is killed (Linux only) and `PdfRenderTimeoutError`, a `PdfBusyError` subclass, yields the same 503.
- `readiness.py`: the dependency checks behind `/health/ready`.
- `prompt_safety.py`: wraps untrusted resume/JD content in `<untrusted_data>` boundaries (`untrusted_json`) with `UNTRUSTED_DATA_RULE`; route all user-derived text through it when building LLM prompts. `scripts/measure_injection_coverage.py` measures this coverage.
- `ownership.py`: `get_owned_record` fetches by primary key and owner in one query; use it for any user-owned resource so owner mismatches return 404.
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
- `POST /api/resumes/parse`: parse PDF or DOCX content into a reviewable builder draft without retaining the source file.
- `POST /api/master-resumes`, `PUT/GET /api/master-resumes/{id}`: persist, update, and retrieve reviewed master resumes. Each skill group is `{key, category, items[]}`; the adapter uses `key` as the profile skill-dict key, falling back to an underscore slug of `category`, then `skill_{index}`. `items` accepts an array (passed through unchanged) or a string on input; a string is split server-side by `split_skill_items` in `services/master_resume_adapter.py` — newline anywhere splits on lines with commas kept literal, otherwise splits on commas except commas nested inside `()`/`[]`, trimming each item and dropping blanks. The array shape is always what gets persisted.

## Data, Authentication, and Security

Master-resume saves use two stages: `POST /api/master-resumes/{id}/seed-dictionary` runs after persistence to enrich a per-resume skill dictionary. It calls Claude Haiku through the shared `CLAUDE_MODEL` constant (currently `claude-haiku-4-5-20251001`), skips current dictionaries, and uses a one-hour failure backoff. A seed failure or timeout never rolls back or blocks the completed resume save.

Current dictionaries also learn accepted branch-3 static skill placements during generation. `skill_dictionary.learned` records lowercased terms added this way; they share `terms` for lookup.

`TailoredResumeRecord` stores job-specific generation history. `MasterResumeRecord` stores reviewed resume-builder data for editing and preview. Both use PostgreSQL, and Alembic owns their schema. `MasterResumeRecord.skill_dictionary` is nullable JSONB with `{ "terms": {"lowercased term": "category_key"}, "profile_hash": "...", "seeded_at": "ISO timestamp", "last_attempt_at": "ISO timestamp or null", "last_attempt_failed": false }`; this storage-only change leaves it unpopulated until commit 2 adds seeding.

ResumeBuddy uses first-party email/password authentication with bcrypt hashes, email verification, and peppered-hash server-side sessions. When secure cookies are enabled, the session is carried in the `__Host-resumebuddy_session` HttpOnly cookie, with idle and absolute expiry. Global middleware protects `/api/*` except `/api/auth/*`; it must read the authenticated user's scalar ID while its database session is open, before `get_current_user()`'s committed ORM object is detached. History and master-resume owner mismatches return 404. Deleting a user cascades to their resumes, sessions, and tokens (tested), but there is no account-deletion route or password-reset UI. `test_isolation_http_postgres.py` logs two users in over HTTP and attacks every ID-bearing route, and `test_every_route_is_covered_or_explicitly_exempt` fails when a new route is in none of its `ISOLATION_COVERED`, `STATELESS_AUTHENTICATED` or `PUBLIC` sets.

`main.py` rate-limits registration, login, verification, and password-reset requests per client IP. AI-backed POST routes (`/api/extract-keywords`, `/api/generate-resume`, `/api/regenerate-section`, `/api/generate-cover-letter`) are limited by both client IP and authenticated user. Add any new paid-API route to `_RATE_LIMITED_PATHS` in `main.py`. A second middleware adds `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy` headers to every response; do not remove either middleware.

Create root `.env` with `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `AUTH_TOKEN_PEPPER`, SMTP settings, and optional comma-separated `ALLOWED_ORIGINS`. `STATIC_PROFILES_ENABLED` defaults to false; set it true only for local development that intentionally exposes static JSON profiles. `db.py` defers engine creation until use, but application startup and first database use still require `DATABASE_URL` or `DATABASE_PASSWORD_FILE`. Keep secrets and personal resume data out of commits. Playwright requires Chromium. Optional `PDF_MAX_CONCURRENCY` (default 2), `PDF_QUEUE_TIMEOUT_SECONDS` (default 30) and `PDF_RENDER_TIMEOUT_SECONDS` (default 45) bound simultaneous and individual renders. The Docker image installs Chromium into `PLAYWRIGHT_BROWSERS_PATH=/opt/pw` so the non-root `appuser` can launch it, pins both base images to exact tags, and pins every `backend/requirements.txt` entry; update those pins deliberately.

Tailoring derives its occupation descriptor from optional `meta.occupation`, then `meta.target_roles`, then the resume title, with a neutral fallback; do not branch on fixed role types. The resolved occupation reaches the model as `candidate_target_occupation` in untrusted resume data, not as a system persona. The builder separately asks for an optional target job title, distinct from its `targetRole` filing label: the title identifies the saved resume and is not printed, while the target job title feeds `meta.occupation` and therefore the tailoring data.

## Development and Validation

```bash
pip install -r backend/requirements.txt
pip install pytest
playwright install chromium
cd backend && fastapi dev main.py
cd client && npm install && npm run dev
cd client && npm test && npm run lint && npm run build
cd backend && python -m pytest -v
docker compose up --build
docker compose -f docker-compose.local.yml up --build   # standalone local stack; needs POSTGRES_PASSWORD in .env
```

The root `Caddyfile` is the production reverse proxy (`$PUBLIC_APP_HOST` → `resumebuddy:8000`).

Alembic migration-chain and ORM persistence tests are opt-in: set `POSTGRES_TEST_DATABASE_URL` to a reachable PostgreSQL database whose role can create databases and run the normal backend pytest command. Do not assume the Windows host's `localhost:5432` is the Compose service; when it is not, run validation inside the Compose network. They create and drop UUID-named disposable databases; persistence tests use the Alembic-created PostgreSQL schema rather than SQLite. Latest measured, in the container: 266 passed and 32 skipped without Postgres, 298 passed and 0 skipped with it; frontend 83 passed plus the one expected `it.fails`. Run the Postgres tests inside the Compose network with `POSTGRES_TEST_DATABASE_URL` pointing at the `postgres` service (role `resumebuddy`, `postgresql+psycopg://`), because the host's `localhost:5432` often is not the Compose database. Route tests call route functions directly, so they must pass `http_request=owner_request` and seed owners with `postgres_user`; both fixtures come from `backend/postgres_test_support.py` (loaded with `pytest_plugins = ("postgres_test_support",)`, which also provides `disposable_postgres_database` and `schema_drift`). Without a request, `user_id` is `None` and inserts violate NOT NULL. `routes/test_generate_pdf_pending.py`, `services/test_auth_service.py` and `test_auth_middleware.py` build SQLite schemas with `create_all`; SQLite does not enforce the foreign keys or cascade, so do not treat them as evidence for those behaviours.

Schema and ownership rules: every user-owned table (`master_resumes`, `tailored_resumes`, `auth_tokens`, `user_sessions`) has a NOT NULL `user_id` with an `ON DELETE CASCADE` foreign key to `users.id`, declared in both the models and Alembic. `test_schema_drift_postgres.py` migrates a disposable database to head and fails, listing every difference, if it differs from the models (the `alembic check` comparison, including `ondelete` and nullability), so a model change needs a new revision in the same commit. FK names live only in the migration, so renamed constraints are not detected. Never edit an applied revision; add a new one. Migration `e5b2c8f1a9d3` deletes pre-authentication rows that have no owner.

Vite runs on port 5175 and proxies `/api` to port 8000. Vitest uses jsdom, Testing Library, and `vite.config.js`; tests are colocated as `*.test.jsx`. Docker builds the frontend into `backend/static` and mounts `backend/data` and `backend/outputs`.

PostgreSQL 16 runs as the Compose `postgres` service and persists to `postgres_data`. From `backend/`, run `alembic upgrade head` to apply migrations and `alembic revision --autogenerate -m "describe schema change"` to generate a reviewed revision. SQLite is gone.

## PDF fitting

Chromium renders are bounded by `pdf_concurrency.py`; both resume workers close the browser and delete temp PDFs in `try/finally`. A busy queue during generation never discards the paid result (see `generate.py` above).

Resume fitting compresses spacing but never reduces the requested font size. Dense resumes can remain multi-page after spacing reaches its floor; the PDF is still produced and the backend reports its page count and whether it fit on one page. Custom-download responses provide the same metadata in `X-PDF-Page-Count` and `X-PDF-Fitted-To-One-Page` headers.

To run a single test: `cd backend && pytest routes/test_master_resumes.py::test_create_and_fetch_master_resume -v` (must run from `backend/` — imports like `from models import ...` assume it's on `sys.path`) or `cd client && npx vitest run src/components/ResumeBuilder.test.jsx -t "adds and saves labeled skill categories"`.

Pytest files are named `test_*.py` beside services, under `backend/routes/`, or at the backend package root (e.g. `backend/test_main.py`, which covers the rate-limit and security-header middleware, and `backend/test_auth_middleware.py`, which covers verified, absent, revoked, and unverified cookie sessions) — plain `pytest` from `backend/` collects all of them. Mock Anthropic, Groq, filesystem, database, and Playwright boundaries; cover validation and failure paths. `backend/smoke_extract_keywords.py` is a credential-dependent smoke script, not a unit test.

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
