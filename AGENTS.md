# Repository Guidelines

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
├── README.md / CLAUDE.md
└── AGENTS.md
```

`backend/main.py` registers the routers, initializes SQLite, configures CORS, and serves the built React app in production. Personal resume JSON, `backend/data/resume_history.db`, `backend/outputs/`, `client/node_modules/`, and build output are runtime artifacts and must not be committed.

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

## Data, Authentication, and Security

`TailoredResumeRecord` stores job metadata, selected keywords, structured resume JSON, ATS scores, optional cover-letter text, and cached PDF path in `backend/data/resume_history.db`. `init_db()` creates tables and applies the additive cover-letter migration.

There is currently **no authentication or authorization**; all API and history routes are open to any client that can reach the server. Do not imply per-user isolation. Preserve path validation, input limits, HTML escaping, and `Cache-Control: no-store` behavior.

Create root `.env` with `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, and optional comma-separated `ALLOWED_ORIGINS`. Keep secrets and personal resume data out of commits. Playwright requires Chromium.

## Development and Validation

```powershell
pip install -r backend/requirements.txt
pip install pytest
playwright install chromium
cd backend; fastapi dev main.py
cd client; npm install; npm run dev
cd client; npm test; npm run lint; npm run build
cd backend; pytest routes -v --deselect routes/test_generate.py::test_summary_variant_changes_only_the_default_summary
docker compose up --build
```

Vite runs on port 5175 and proxies `/api` to port 8000. Vitest uses jsdom, Testing Library, and `vite.config.js`; tests are colocated as `*.test.jsx`. Docker builds the frontend into `backend/static` and mounts `backend/data` and `backend/outputs`.

Pytest files are named `test_*.py` beside services or under `backend/routes/`. Mock Anthropic, Groq, filesystem, database, and Playwright boundaries; cover validation and failure paths. `backend/test_extract.py` is a credential-dependent smoke script, not a unit test. Full pytest collection currently has two known blockers: `test_claude_service.py` imports removed `limit_character_count`, and the smoke script name collides with `routes/test_extract.py`. Run focused test paths until those are resolved.

Frontend tests mock `fetch`, clipboard, and browser download boundaries. `CoverLetterStep.test.jsx` contains one `it.fails` regression: clearing the letter unmounts its textarea. Do not remove the marker without fixing and verifying the component. No coverage threshold is enforced.

## Coding and Contribution Conventions

Use four-space Python indentation, `snake_case` functions/modules, `PascalCase` classes, Pydantic request/response models, and FastAPI dependency injection for database sessions. React uses two spaces, `PascalCase` component files, `camelCase` props/functions, functional components, and colocated CSS. Follow ESLint and avoid adding dependencies without clear value.

Keep commits short and imperative, preferably under 72 characters. PRs should explain behavior, list validation commands, identify schema/configuration changes, link issues, and include screenshots for visible UI changes. Preserve unrelated work and never commit secrets, personal resumes, generated PDFs, or the runtime database.
