# ResumeBuddy Decisions

This document records important choices and their rationale. It describes decisions already made, not future commitments.

## Separate master facts from application versions

The conceptual model distinguishes reusable career facts from job-specific generated resumes.

Why:

- Tailored language should not silently rewrite canonical work history.
- Users need a stable source of truth.
- Application-specific keywords and summaries are not universally appropriate.

Current consequence: tailored applications and reusable master resumes use separate database tables.

## Use one builder for manual and imported resumes

PDF/DOCX imports populate the same `ResumeBuilder` used for manual entry.

Why:

- Import is only another source of draft data.
- One editor prevents divergent schemas and validation.
- Users can correct parsing errors before saving.

## Require review before saving imported information

Parsing never directly stores the extracted profile. The user receives an editable draft and must explicitly select **Save draft**.

Why:

- Resume layouts are inconsistent.
- Dates, headings, columns, and employers can be misclassified.
- Imported text must not become trusted user data without confirmation.

## Parse uploads in memory

The import endpoint does not persist source documents.

Why:

- Resumes contain sensitive personal information.
- The application has no authentication or ownership controls.
- Source retention is unnecessary for the current review workflow.

The endpoint limits files to 5 MB and validates the extension and basic file signature.

## Use deterministic parsing before AI parsing

Contact patterns and recognized headings are mapped locally. Uncertain content remains available for manual review.

Why:

- Imports work without API keys.
- Personal documents are not sent to another provider.
- Tests remain deterministic.
- The parser avoids inventing facts.

Tradeoff: complex and heavily designed resumes require more correction.

## Reuse pypdf and standard-library DOCX extraction

PDF extraction uses the existing `pypdf` dependency. DOCX text is read from its ZIP/XML structure without adding a full document-processing library.

Why:

- It keeps dependency growth small.
- The current need is text extraction, not Word document editing.

`python-multipart` was added because FastAPI requires it for multipart uploads.

## Persist reviewed resumes separately

The Create Resume flow stores reviewed data in `MasterResumeRecord` and keeps the returned record in React state for immediate preview and editing.

Why:

- Master resumes and job-specific application history have different lifecycles.
- A separate table avoids overloading `TailoredResumeRecord`.
- JSON storage preserves the structured builder payload while its schema is still evolving.

Tradeoff: without authentication, records are local application data and cannot provide per-user privacy or ownership.

## Preview master resumes in the client

After a successful save, the client renders the persisted structured payload in a dedicated read-only preview.

Why:

- Preview should not require AI generation or a job description.
- Structured rendering is fast and keeps the persistence change independent from Playwright PDF generation.
- Users can return directly to editing the same database record.

Tradeoff: master-resume PDF export is not yet implemented.

## Keep runtime SQLite outside version control

`backend/data/resume_history.db` is ignored and must remain untracked.

Why:

- It contains personal resume and job-application data.
- Its contents are machine-specific runtime state and create noisy binary diffs.
- Tables and additive migrations are reproducible from the models and `init_db()`.

Adding a path to `.gitignore` does not remove an already tracked copy. Older clones must run `git rm --cached backend/data/resume_history.db` once and commit that index removal. This removes the file from Git without deleting the local database.

## Support repeatable named project links

Each project may contain zero or more `{name, url}` links.

Why:

- A project may have a GitHub repository, live demo, case study, or documentation.
- A label is more meaningful on a resume than exposing a raw URL.
- Projects without links remain valid.

## Preserve focused files and existing workflow contracts

Resume creation and parsing were added through focused components, services, and routes rather than rewriting the tailoring workflow.

Why:

- Existing profile tailoring remains backward compatible.
- New behavior is independently testable.
- The change does not overload `App.jsx` or existing generation services.
