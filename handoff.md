# ResumeBuddy Handoff

## Current State

ResumeBuddy supports its established job-tailoring workflow and now has the first resume-creation vertical slice.

### Implemented resume creation

- **Create a resume** appears above the existing profile list.
- The builder contains contact information, target role, professional summary, work experience, education, skills, projects, and certifications.
- Experience, education, projects, and certifications support repeatable entries.
- Projects support repeatable named links with validated URLs.
- Name and email are required before saving.
- Saving creates or updates a `MasterResumeRecord` in SQLite.
- A successful save opens a dedicated read-only resume preview.
- Users can return from the preview to edit and update the same record.

### Implemented resume import

- The builder accepts PDF and DOCX files.
- `POST /api/resumes/parse` validates extension, signature, empty input, and a 5 MB limit.
- PDF extraction uses `pypdf`.
- DOCX extraction uses ZIP/XML standard-library support.
- Source documents are processed in memory and are not retained.
- Parsed information autofills the builder.
- The user sees warnings and reviews the editable fields before selecting **Save draft**.
- Failed imports preserve the current draft.

### Existing application workflow

Static JSON profiles can still be selected and tailored through:

```text
Profile → Job details → Keywords → Resume → PDF → Cover letter
```

Job-specific resume and cover-letter history remains stored in SQLite.

## Important Boundaries

- There is no authentication or authorization.
- Master resumes are stored locally but are not associated with an authenticated owner.
- `backend/data/resume_history.db` is now listed in `.gitignore`, but it is still tracked in the current Git index.
- Saved master resumes are not yet listed after a refresh, despite remaining in SQLite.
- Imported source files are not stored.
- Scanned PDFs are unsupported because OCR is not implemented.
- Deterministic parsing is intentionally conservative and may need correction for complex layouts.
- Created drafts are not yet usable as tailoring profiles.

## Before the Next Commit

Remove the runtime database from Git tracking once:

```powershell
git rm --cached backend/data/resume_history.db
git status --short
git ls-files backend/data/resume_history.db
```

`git rm --cached` removes only the indexed copy; it keeps the local SQLite file. The final command should print nothing. After that index removal is committed, the `.gitignore` rule prevents future `git add .` commands from staging the database.

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
- Frontend tests: 29 passed and 1 existing expected failure.
- Frontend build: passed.
- ESLint: no errors; two existing hook-dependency warnings remain in `PDFPreview.jsx` and `ResumePreview.jsx`.
- `git diff --check`: passed.

The repository's known broader pytest collection blockers still apply.

## Recommended Next Step

Add authenticated ownership and a saved-resume list before connecting created or imported resumes to the tailoring workflow.

That work should define:

1. User ownership and authorization.
2. Ownership fields and an authorization migration for master resumes.
3. List and deletion APIs.
4. Autosave and recovery behavior.
5. Conversion from a confirmed master resume into the existing tailoring input.
6. Retention and deletion rules for personal data.

Continue to keep `TailoredResumeRecord` separate; it represents job-specific application history.

## Documentation Map

- `AGENTS.md`: how Codex should work in this repository.
- `architecture.md`: how the application is designed.
- `decisions.md`: why important choices were made.
- `backlog.md`: ideas that may be built.
- `handoff.md`: current implementation and next-step context.
