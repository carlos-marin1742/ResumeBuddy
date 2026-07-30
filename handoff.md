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
- Saving creates or updates a `MasterResumeRecord` in SQLite.
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

Static JSON profiles can still be selected and tailored through:

```text
Profile → Job details → Keywords → Resume → PDF → Cover letter
```

Job-specific resume and cover-letter history remains stored in SQLite.

Generated job-tailored HTML/PDF renders the requested job title directly below the candidate name. The saved master-resume title is only an identifier on the profile-selection page and does not render inside `MasterResumePreview`.

## Important Boundaries

- There is no authentication or authorization.
- Master resumes are stored locally but are not associated with an authenticated owner.
- Auth0 has been selected for future public multi-user authentication, but it is not yet integrated.
- The React SPA will use Authorization Code Flow with PKCE; FastAPI will validate access tokens and use the stable Auth0 `sub` claim as `owner_id`.
- `backend/data/resume_history.db` is listed in `.gitignore` and is no longer tracked in the current Git index.
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
- Frontend tests: 29 passed and 1 existing expected failure.
- Frontend build: passed.
- ESLint: no errors; two existing hook-dependency warnings remain in `PDFPreview.jsx` and `ResumePreview.jsx`.
- `git diff --check`: passed.

The former broader pytest collection blockers were resolved by removing obsolete `limit_character_count` tests and renaming the credential-dependent smoke script to `backend/smoke_extract_keywords.py`.

## Recommended Next Step

Integrate Auth0 authentication and authenticated ownership before connecting created or imported resumes to the tailoring workflow. Auth0 dashboard configuration is intentionally paused for now.

That work should define:

1. Auth0 Universal Login using email/password and Google login.
2. React Authorization Code Flow with PKCE and FastAPI access-token validation.
3. Ownership fields based on the Auth0 `sub` claim.
4. Authorization for master resumes, tailored history, cover letters, downloads, and in-memory sessions.
5. A one-time, non-public migration that assigns existing records to the developer's Auth0 account.
6. List and deletion APIs.
7. Autosave and recovery behavior.
8. Authorization coverage for the saved-master-resume selection and schema-adapter flow.
9. Retention and deletion rules for personal data.
10. A dedicated master-resume renderer whose typography matches `MasterResumePreview` while spacing and margins remain independently adjustable.

Continue to keep `TailoredResumeRecord` separate; it represents job-specific application history.

## Documentation Map

- `AGENTS.md`: how Codex should work in this repository.
- `architecture.md`: how the application is designed.
- `decisions.md`: why important choices were made.
- `backlog.md`: ideas that may be built.
- `handoff.md`: current implementation and next-step context.
