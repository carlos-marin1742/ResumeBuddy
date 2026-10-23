# ResumeBuddy Handoff

## Current State

ResumeBuddy supports its established job-tailoring workflow and now has the first resume-creation vertical slice.

### Implemented resume creation

- **Create a resume** appears above the existing profile list.
- The builder contains contact information, target role, professional summary, work experience, education, skills, projects, and certifications.
- Skills support repeatable labeled categories, and category names render in bold in the saved preview.
- Experience, education, projects, and certifications support repeatable entries.
- Projects support repeatable named links with validated URLs.
- Name and email are required before saving.
- Saving creates or updates a PostgreSQL-backed `MasterResumeRecord` managed by Alembic.
- A successful save opens a dedicated read-only resume preview.
- Users can return from the preview to edit and update the same record.
- The builder's resume title is saved for identification in the future resume-selection list, but it is not rendered inside the resume document. Imports leave the title blank for the user to supply.
- Client API requests use relative `/api` paths so Save & Preview works through the Vite development proxy and FastAPI production hosting.

### Implemented resume import

- The builder accepts PDF and DOCX files.
- `POST /api/resumes/parse` validates extension, signature, empty input, and a 5 MB limit.
- PDF extraction uses `pypdf`.
- DOCX extraction uses ZIP/XML standard-library support.
- Source documents are processed in memory and are not retained.
- Parsed information autofills the builder.
- Labeled skill groups from the provided Carlos Marin sample are preserved during import.
- PDF parsing now handles the research-resume layout where experience headers and dates are separate, multiple skill bullets share a text line, education combines institution and degree, and certifications/systems share a section.
- The user sees warnings and reviews the editable fields before selecting **Save draft**.
- Failed imports preserve the current draft.

### Existing application workflow

With `STATIC_PROFILES_ENABLED=true` for local development, static JSON profiles can be selected and tailored through:

```text
Profile → Job details → Keywords → Resume → PDF → Cover letter
```

Job-specific resume and cover-letter history is stored in PostgreSQL.

Generated job-tailored HTML/PDF renders the requested job title directly below the candidate name. The saved master-resume title is only an identifier on the profile-selection page and does not render inside `MasterResumePreview`.

## Important Boundaries

- API access requires a verified email/password account. Passwords are bcrypt hashes and sessions are opaque, peppered-hash, HttpOnly server-side records with idle and absolute expiry; secure-cookie deployments use the `__Host-resumebuddy_session` cookie.
- Master resumes and tailored history are associated with an authenticated owner and are scoped by that owner in persistence routes.
- SMTP configuration and `AUTH_TOKEN_PEPPER` are required backend environment values for verification and password-reset links; no auth secret is exposed to the SPA.
- PostgreSQL data is outside the repository and Alembic owns schema changes. `db.py` creates its engine lazily, while startup and first database use still require `DATABASE_URL` or `DATABASE_PASSWORD_FILE`.
- Saved master resumes are listed after refresh and can be selected for keyword extraction, tailoring, and generated PDF output.
- Saved master resumes can be deleted from the profile page after inline confirmation; static JSON profiles are intentionally not deletable there.
- Imported source files are not stored.
- Scanned PDFs are unsupported because OCR is not implemented.
- Deterministic parsing is intentionally conservative and may need correction for complex layouts.
- Created drafts are not yet usable as tailoring profiles.
- Saved master resumes currently have a browser preview but no general HTML/PDF generation path.
- The existing tailored-resume PDF renderer uses a different schema and visual treatment from `MasterResumePreview`.

### Planned master-resume output

Manual entry and uploads already converge on the same saved master-resume schema. A dedicated master-resume renderer should consume that schema directly and match the preview's typography and semantic formatting, including fonts, sizes, weights, italics, colors, capitalization, section rules, date formatting, links, and field order.

PDF margins, paper padding, section spacing, entry spacing, and line spacing are intentionally excluded from the matching requirement so page fitting can remain independent.

## Files Added for the Current Feature

- `client/src/components/ResumeBuilder.jsx`
- `client/src/components/ResumeBuilder.css`
- `client/src/components/ResumeBuilder.test.jsx`
- `client/src/components/MasterResumePreview.jsx`
- `client/src/components/MasterResumePreview.css`
- `client/src/components/MasterResumePreview.test.jsx`
- `backend/routes/resume_import.py`
- `backend/routes/test_resume_import.py`
- `backend/services/resume_parser.py`
- `backend/services/test_resume_parser.py`
- `backend/routes/master_resumes.py`
- `backend/routes/test_master_resumes.py`

Related modifications include `client/src/App.jsx`, `ResumePicker`, `backend/main.py`, and `backend/requirements.txt`.

## Dependencies and Setup

`python-multipart` was added for FastAPI multipart uploads.

```powershell
pip install -r backend/requirements.txt
playwright install chromium
cd client; npm install
```

## Latest Validation

Successfully run:

```powershell
cd backend
python -m pytest services/test_resume_parser.py routes/test_resume_import.py -v

cd client
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

Observed results:

- Focused backend master-resume/import/parser tests: 13 passed.
- Full backend suite with no externally configured database or private profile files, run inside the built container: 258 passed, 28 skipped, 0 failed. The test fixture supplies SQLite only after collection.
- Frontend tests: 81 passed and 1 existing expected failure.
- Frontend build: passed.
- ESLint: no errors; two existing hook-dependency warnings remain in `PDFPreview.jsx` and `ResumePreview.jsx`.
- `git diff --check`: passed.

The former broader pytest collection blockers were resolved by removing obsolete `limit_character_count` tests and renaming the credential-dependent smoke script to `backend/smoke_extract_keywords.py`.

## Deployment Readiness (2026-10-19)

- Image: exact-tag bases, fully pinned dependencies, non-root `appuser`, Chromium in `/opt/pw`, Liberation fonts, `.dockerignore` excluding secrets, tests, fixtures, and golden files. PDFs rendered in the container wrap line-for-line like the Windows host (Arial vs Liberation Sans, same Chromium build).
- Health: `/health` (liveness, used by `HEALTHCHECK`) and `/health/ready` (database, headless-shell binary, static profiles when enabled).
- PDF limits: `PDF_MAX_CONCURRENCY` (2), `PDF_QUEUE_TIMEOUT_SECONDS` (30), and `PDF_RENDER_TIMEOUT_SECONDS` (45; a hung render is killed and answered with 503, verified against real Chromium in the container with no processes or zombies left). Six concurrent renders at `-m 1g`: all succeeded, 381 MiB peak with the default limit, 804 MiB without it.
- Generation persists before rendering; a busy queue returns `pdf_status: "pending"` and the download routes render on demand.
- Client: fetch timeouts (120 s generate, 60 s others) and plain-language 503/429/timeout messages, all in `client/src/api.js`.
- Not yet verified: the production `docker-compose.yml` (needs `./secrets/*` and `PUBLIC_APP_HOST`), Render's request timeout against the 30 s queue wait.

## Private-Deploy Batch 1 (2026-10-22)

- Registration modes (`REGISTRATION_MODE` closed/allowlist/open, default closed; `REGISTRATION_ALLOWLIST`), `GET /api/auth/config`, and an `AuthGate` that hides registration unless the server says it is open.
- Admin script: `python -m scripts.manage_users create|reset|list`. In a deployed service run it in that service's shell (for example `docker compose exec resumebuddy python -m scripts.manage_users list`, or the platform's remote shell) so it sees the same environment; it never prints connection strings or secrets and `reset` revokes the user's sessions.
- `read_secret` accepts `NAME` or `NAME_FILE` (both set fails startup), `DATABASE_URL` accepts `postgres://` and `postgresql://`, the container binds `$PORT`, and `FORWARDED_ALLOW_IPS` replaces the hardcoded `*` (default `127.0.0.1`; the value for the hosting platform is still to be chosen by the operator).
- Validation (Docker, `rb-test` image with the working tree mounted, against a throwaway `postgres:16`): backend 433 passed with PostgreSQL; 336 passed and 97 skipped without it. Frontend: 91 passed plus the one expected failure; ESLint 0 errors, 2 existing warnings. The baseline quoted in the task (377 and 299/78) was stale; the tree measured 383 and 304/79 before any change.
- Existing HTTP auth tests now set `REGISTRATION_MODE=open` themselves.
- Known gap: open-registration hardening is pending: per-account login throttling, and an Origin check that currently lets requests with no Origin header through.
- Not verified then: a full `docker build` and a deploy on the hosting platform (the production image build and boot are covered in batch 2 below; a real hosting deploy is not).

## Private-Deploy Batch 2 (2026-10-22): local production rehearsal

- Built the real production Dockerfile (2.09 GB, 120 s with layer cache) and booted it against a throwaway `postgres:16` with env vars only: `DATABASE_URL` in `postgres://` form, `PORT=8080`, `APP_ENV=production`, closed registration, no SMTP. It reached healthy; `/health`, `/health/ready` and the Dockerfile HEALTHCHECK worked on 8080.
- Rehearsal found that production startup demanded SMTP and `REQUIRE_HTTPS` and that a missing SMTP setting made register and password-reset answer 503 for real addresses only (an address oracle). Fixed in four commits: SMTP (and `PUBLIC_APP_URL`) are required only when `REGISTRATION_MODE` is not closed or `SMTP_HOST`/`SMTP_FROM` is set; startup errors name the settings; send failures are caught, logged as one generic `email_delivery_failed` event, and answered with the normal 202 (a failed registration is rolled back so a retry works); `PUBLIC_APP_URL` must be `https://` and not localhost when email can be sent; the pepper must be at least 32 characters. All in `services/production_config.py` and `routes/auth.py`.
- Also fixed: `auth_http_support.py` (a test helper) was being copied into the image; it is now in `.dockerignore`, with a test.
- Exact first-deploy env list: see "First deploy on a platform that injects plain env vars" in the README. Required: `APP_ENV=production`, `REQUIRE_HTTPS=true`, `DATABASE_URL`, `AUTH_TOKEN_PEPPER` (32+ chars), `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `ALLOWED_ORIGINS` (https origins).
- Admin script, login, cookie flags (`__Host-` name, Secure, HttpOnly, SameSite=lax, Path=/), `/api/auth/me`, `/api/master-resumes`, logout and revocation, and `/api/auth/config` (`registration_open` false) were exercised against the running container; a closed-mode register returned the generic 202 and created no row.
- Proxy evidence (nginx in front, six registrations with six different `X-Forwarded-For` values): with `FORWARDED_ALLOW_IPS=127.0.0.1` all six counted against the proxy's address (sixth got 429) and logs showed the proxy IP; with `*` each got its own bucket and logs showed the forwarded address. With `*` and a directly reachable port, a client can spoof `X-Forwarded-For` and evade the per-IP limit. The right value for the hosting platform is still to be chosen by the operator.
- Audits: `pip-audit` of `backend/requirements.txt` (with `--no-deps`, so only listed pins) found nothing; `npm audit --omit=dev` found 0 vulnerabilities.
- In production `/docs`, `/redoc` and `/openapi.json` are disabled but answer 200 with the SPA's `index.html` because of the catch-all route; no schema is exposed.
- Origin guard check (production image, env vars only, logged in as an admin-created user, POST `/api/extract-keywords` with fake AI keys): with `ALLOWED_ORIGINS` unset the default is the three localhost origins, so `Origin: https://example.test` got 403 `Untrusted request origin.` (the real public origin would be rejected, and a same-origin browser POST always sends Origin); with `ALLOWED_ORIGINS=https://example.test` it got past the guard (404 from the route) and `http://localhost:8000` got 403. Production startup now requires `ALLOWED_ORIGINS` (non-empty, every entry a bare `https://host[:port]`, no localhost/loopback, wildcard, path or userinfo), naming the setting without echoing the value. Only `main.py` reads the list: the Origin guard in `require_authenticated_api` and `CORSMiddleware(allow_origins=...)`; there is no other CSRF logic. The guard does not cover `/api/auth/*`, and requests with no Origin header still pass (still open).
- Still open: per-account login throttling and the Origin check (including requests with no Origin header) before opening registration; an SMTP timeout (10 s) holds a worker thread during a send.

## Recommended Next Step

Cross-user isolation is covered by `backend/test_isolation_http_postgres.py` (real registration, verification and login for two users over HTTP against a migrated disposable PostgreSQL database; external services mocked). It attacks every resource-bearing route as the other user, requires 404 identical to a nonexistent ID, and fails if a new route is neither covered nor explicitly exempt. Next: add an account-deletion route and password-reset UI.

The `DetachedInstanceError` in authenticated middleware was present at `7cbac04^` before the lazy-engine change (`d28b773`): both revisions accessed `user.id` after `get_current_user()` had committed and its session had closed. The middleware now reads the scalar ID while the session remains open.

Known gaps to preserve explicitly:

1. There is no account deletion or password-reset UI.
2. `RESUME_STORE` is in memory and generated PDFs remain on local disk (they are re-rendered on demand when missing).
3. Login throttling is per client IP only (per-account throttling is pending before registration is opened).
4. Migration `e5b2c8f1a9d3` deletes pre-authentication rows that have no owner. Any database with unowned rows that matter needs them assigned to a user before upgrading.
5. Production still needs a unique `AUTH_TOKEN_PEPPER`, `PUBLIC_APP_URL`, SMTP configuration, and secure cookies behind HTTPS.
6. Commit `0adb688` moved the user-controlled occupation out of the tailoring system prompt to prevent prompt injection. Commit `a294d65` restored occupation-aware tailoring through the `candidate_target_occupation` field in the untrusted resume-data block.

Continue to keep `TailoredResumeRecord` separate; it represents job-specific application history.

## Documentation Map

- `AGENTS.md`: how Codex should work in this repository.
- `architecture.md`: how the application is designed.
- `decisions.md`: why important choices were made.
- `backlog.md`: ideas that may be built.
- `handoff.md`: current implementation and next-step context.
