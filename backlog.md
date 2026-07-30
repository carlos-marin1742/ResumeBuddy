# ResumeBuddy Backlog

These are candidate improvements, not committed scope. Prioritize them against user need, privacy, and implementation risk.

## Highest priority

- Integrate Auth0 Universal Login with the React SPA using Authorization Code Flow with PKCE.
- Validate Auth0 access tokens in FastAPI and expose a reusable authenticated-user dependency.
- Add `owner_id` fields based on the Auth0 `sub` claim and enforce ownership across master resumes, tailored history, cover letters, generated downloads, and in-memory sessions.
- Provide a one-time, non-public migration path that assigns existing local records to the developer's Auth0 account.
- Add rename, duplicate, and archive controls for listed master resumes.
- Add a dedicated master-resume HTML/PDF renderer and download path that does not require a job description.
- Share typography tokens and semantic formatting between `MasterResumePreview` and generated master-resume output while keeping margins and spacing independent.
- Cover the shared formatting contract with renderer and component tests.
- Add autosave and recovery after refresh.

## Import improvements

- Add an explicit field-by-field confidence and review state.
- Improve experience, education, date, and multi-column parsing.
- Parse multiple experience, project, education, and certification entries.
- Detect project links and distinguish GitHub, portfolio, and live-demo URLs.
- Add pasted-text import.
- Add OCR for scanned PDFs.
- Detect password-protected documents before extraction.
- Consider optional AI-assisted parsing only with clear consent and privacy disclosure.
- Define upload audit, retention, and deletion policies before retaining source files.

## Resume-builder improvements

- Break the long form into guided steps with progress.
- Add automatic draft saving.
- Add “currently employed” handling for experience dates.
- Add reorder controls for repeatable entries.
- Add section-level completion indicators.
- Add explicit imported, suggested, needs-review, and confirmed states.
- Provide accomplishment prompts without requiring fabricated metrics.
- Add AI-assisted bullet rewriting after factual information is collected.
- Support one-page and two-page resume options.
- Add template selection and accessibility checks.

## Product integration

- Allow users to promote an approved application fact back to a master resume.
- Compare master and application versions.
- Show which source fact supports each generated claim.
- Add multiple role-specific master resumes.
- Create a clearer resume home with create, import, and continue paths.

## Technical health

- Fix the `CoverLetterStep` textarea-clearing regression and remove `it.fails` only after verification.
- Resolve existing React hook dependency warnings in `PDFPreview.jsx` and `ResumePreview.jsx`.
- Add backend CI with Python, Chromium, and focused pytest commands.
- Add end-to-end browser coverage for create, import, review, save, tailor, and download.
- Define a versioned database migration strategy for schema changes beyond the current additive startup migrations.
