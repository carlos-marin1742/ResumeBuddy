# ResumeBuddy Architecture

## System Overview

ResumeBuddy is a React and FastAPI application for creating, importing, tailoring, previewing, and exporting resumes and cover letters.

```text
React client
  ├─ Resume creation and import review
  ├─ Job-tailoring workflow
  └─ Resume history
          │
          ▼
FastAPI application
  ├─ Resume profile and import routes
  ├─ Keyword extraction and tailoring routes
  ├─ Preview and PDF routes
  ├─ Cover-letter routes
  └─ History routes
          │
          ├─ Anthropic and Groq
          ├─ Playwright and pypdf
          ├─ Static JSON resume profiles
          └─ SQLite tailored-resume history
```

In development, Vite runs on port 5175 and proxies `/api` to FastAPI on port 8000. In production, the React build is served from `backend/static` by FastAPI.

## Frontend

`client/src/App.jsx` owns shared workflow state and selects the active view.

### Resume creation

`ResumePicker` displays available static profiles and provides the **Create a resume** entry point.

`ResumeBuilder` supports:

- Contact information
- Target role
- Professional summary
- Repeatable work experience
- Repeatable education
- Repeatable skill categories with a display label and comma-separated values
- Repeatable projects with repeatable named links
- Repeatable certifications
- PDF or DOCX import
- Review and editing before an explicit database save
- A read-only resume preview after saving

Created resumes are persisted as `MasterResumeRecord` rows and remain in React state for immediate editing and preview. They are listed alongside static profiles after refresh. A schema adapter converts the reviewed builder payload into the existing tailoring and PDF schema when selected.

### Job-tailoring workflow

```text
ResumePicker
    ↓
JDInput
    ↓
KeywordSelector
    ↓
ResumePreview
    ↓
PDFPreview
    ↓
CoverLetterStep
```

`ResumeHistory` is a separate view for previously generated application resumes.

## Backend

`backend/main.py` initializes SQLite, configures CORS, registers routers, exposes health information, and serves the production frontend.

The client uses same-origin `/api` paths. Vite proxies those paths to FastAPI during development, and FastAPI serves both the built client and API in production. Do not hard-code a loopback backend address in browser code because it breaks deployed, containerized, and remote-client usage.

### Resume profiles

`GET /api/resumes` discovers valid JSON profiles under `backend/data`. These profiles are the source material for the existing tailoring workflow.

### Resume import

`POST /api/resumes/parse` accepts one multipart PDF or DOCX file.

```text
Browser file selection
    ↓
Extension, size, and signature validation
    ↓
In-memory text extraction
    ↓
Conservative section mapping
    ↓
Reviewable builder draft
    ↓
User edits and explicitly saves session draft
```

PDF text extraction uses `pypdf`. DOCX extraction reads `word/document.xml` through Python's ZIP and XML standard libraries. Source documents are not written to disk. Scanned PDFs are not supported because there is no OCR layer.

Skill lines such as `Frontend: React, TypeScript` are preserved as structured category/value pairs. The category remains editable and renders in bold. Unlabeled legacy skill strings remain supported when older records are loaded.

`backend/services/resume_parser.py` separates extraction and mapping from HTTP concerns. `backend/routes/resume_import.py` owns request validation and response handling.

### Tailoring and generation

- `claude_service.py` handles Groq keyword extraction, Anthropic tailoring and regeneration, skill filtering, and local ATS scoring.
- `project_selection.py` limits projects using work-project priority and job relevance.
- `generate.py` merges generated content, maintains bounded `RESUME_STORE` session state, persists application history, and creates the initial PDF.
- `preview.py` merges user edits and renders HTML or custom PDFs.

### Documents

- `build_resume_pdf.py` renders resume HTML and uses Playwright for PDF output.
- `cover_letter_service.py` generates and formats cover-letter text.
- `build_cover_letter_pdf.py` renders cover-letter PDFs.

The current `build_resume_pdf.py` contract targets job-tailored resume data and does not directly match `MasterResumeRecord.resume_data`. A future master-resume HTML/PDF renderer will consume the saved master schema directly.

`MasterResumePreview` and that renderer must share equivalent typography and semantic presentation: fonts, sizes, weights, italics, colors, heading capitalization and rules, date formatting, links, and field order. Layout density remains renderer-specific; PDF margins, page padding, section spacing, entry spacing, and line spacing may be adjusted independently for page fitting.

## Persistence

`TailoredResumeRecord` stores job-specific generation history in `backend/data/resume_history.db`.

It includes:

- Job and profile metadata
- Job description and selected keywords
- Structured tailored resume
- ATS scores
- Optional cover letter
- Optional cached PDF path

`MasterResumeRecord` stores a reviewed builder payload, display name, target role, and created/updated timestamps in the same SQLite database. It is separate from job-specific history.

The existing `targetRole` payload and `target_role` column represent the user-facing saved-resume title. The title is intended for resume selection and does not render inside `MasterResumePreview`; imported document headings do not populate it automatically.

Because there is no authentication, these records are application-local rather than securely user-owned. Static JSON profiles, master resumes, and tailored history remain three distinct concepts.

`backend/data/resume_history.db` is local runtime state, not a source artifact. The schema is defined by the SQLModel classes and `init_db()`, so each environment can create its own database. The database is gitignored and must be untracked; older clones that tracked it require a one-time `git rm --cached backend/data/resume_history.db`.

## Security Boundaries

There is no authentication or authorization. All clients that can reach the server can reach the API and history routes.

The selected future authentication architecture is Auth0 Universal Login. The React SPA will use Authorization Code Flow with PKCE and send an access token to FastAPI. FastAPI will validate the token signature, issuer, audience, and expiration, then use the stable `sub` claim as `owner_id`.

Authentication alone is insufficient. FastAPI must include `owner_id` in database lookups and enforce ownership for master resumes, tailored history, cover letters, generated downloads, and bounded in-memory sessions. Initial accounts will support email/password and Google login; organization and role-based access are out of the first implementation.

Required protections include:

- File type, signature, and size validation
- In-memory import processing
- Path validation
- Input limits
- HTML escaping
- `Cache-Control: no-store` where already used
- No secrets, personal profiles, runtime databases, or generated documents in commits

The application must not claim per-user privacy or ownership until authentication and authorization are implemented.

## Testing

Frontend behavior is tested with Vitest, jsdom, and Testing Library. Tests are colocated with components.

Backend route and service tests use pytest and mock AI, filesystem, database, and Playwright boundaries. Import tests cover extraction, mapping, supported formats, and invalid input.
