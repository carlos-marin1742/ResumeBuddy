# Repository Guidelines

## Project Structure & Module Organization

`backend/` contains the FastAPI application. API endpoints live in `backend/routes/`, business and AI/PDF logic in `backend/services/`, and shared models and database setup in `models.py` and `db.py`. Runtime resume data belongs under `backend/data/`.

`client/` is the React/Vite frontend. Put reusable UI in `client/src/components/`, bundled assets in `client/src/assets/`, and directly served files in `client/public/`. Backend unit tests live beside their target service, for example `backend/services/test_claude_service.py`.

## Build, Test, and Development Commands

- `pip install -r backend/requirements.txt` installs Python dependencies; also install `pytest` for tests.
- `playwright install chromium` installs the browser used for PDF generation.
- `cd backend; fastapi dev main.py` starts the API on port 8000.
- `cd client; npm install; npm run dev` starts Vite at `http://localhost:5175`.
- `cd client; npm run build` creates the production frontend bundle.
- `cd client; npm run lint` runs ESLint across frontend source.
- `cd backend/services; pytest test_claude_service.py -v` runs mocked backend unit tests without API keys.
- `docker compose up --build` builds and runs the containerized application.

## Coding Style & Naming Conventions

Use four-space indentation and `snake_case` for Python functions, variables, and modules; use `PascalCase` for classes. In React, use two-space indentation, `PascalCase` component filenames (such as `ResumePicker.jsx`), and `camelCase` for functions and props. Keep component-specific CSS beside its JSX file and follow ESLint.

## Testing Guidelines

Use pytest and name files `test_*.py`, classes `Test*`, and functions `test_*`. Mock Anthropic, Groq, filesystem, and browser boundaries in unit tests. Add focused regression tests for service changes. There is no enforced coverage threshold; prioritize route validation, response parsing, keyword logic, and failure paths. Treat direct scripts such as `backend/test_extract.py` as credential-dependent smoke tests, not unit tests.

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries (for example, `updated readme and claude file`). Keep subjects specific, preferably under 72 characters, and group related changes. Pull requests should explain the behavior change, list validation commands, link relevant issues, and call out configuration or schema changes. Include screenshots for visible UI updates and never include secrets or personal resume data.

## Security & Configuration

Store `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, and `ALLOWED_ORIGINS` in a local `.env`. Keep frontend origin changes synchronized among Vite, backend CORS defaults, and documentation.
