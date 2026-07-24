# ResumeBuddy Backlog

These are candidate improvements, not committed scope. Prioritize them against user need, privacy, and implementation risk.

## Highest priority

- Add authentication and authorization.
- List, rename, duplicate, edit, archive, and delete master resumes.
- Connect a confirmed master resume to the existing tailoring workflow.
- Add a general resume PDF download path that does not require a job description.
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

- Complete the one-time removal of `backend/data/resume_history.db` from the Git index, then verify it no longer appears in `git ls-files`.
- Resolve the removed `limit_character_count` import in `test_claude_service.py`.
- Rename or isolate the credential-dependent `backend/test_extract.py` smoke script to avoid pytest collection collision.
- Fix the `CoverLetterStep` textarea-clearing regression and remove `it.fails` only after verification.
- Resolve existing React hook dependency warnings in `PDFPreview.jsx` and `ResumePreview.jsx`.
- Add backend CI with Python, Chromium, and focused pytest commands.
- Add end-to-end browser coverage for create, import, review, save, tailor, and download.
- Define a versioned database migration strategy for schema changes beyond the current additive startup migrations.
