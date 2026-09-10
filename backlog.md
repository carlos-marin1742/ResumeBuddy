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

## Skills data-shape follow-ons

- `SKILL_TO_CATEGORY` still reaches no clinical or trades category, so non-tech
  users receive most selected keywords in Additional Skills rather than in
  their own categories. Per-profile classification is the next problem; do not
  invent tech categories in the meantime.

- `POST /api/resumes/parse` still emits each skill group's `items` as a comma-joined string (no `key`), not the builder's array shape. The frontend tolerates this on load (it normalizes both shapes), so this was left alone in the array/key pass; parsing should eventually emit split items directly.
- The hand-authored JSON profiles in `backend/data/` still represent skills as a keyed object (`{category_key: [items]}`) rather than the builder's `[{key, category, items[]}]` array shape. Reconciling the two shapes (or writing a converter) is separate follow-on work.
- Fixed: the `SkillCategoryInput.items` validator previously wrapped a raw comma string into a single array element instead of splitting it, so a saved skill like `"React, TypeScript, Vite"` persisted as one item and silently failed exact-match gap detection in `/api/extract-keywords` (see `decisions.md`, "The server owns skills splitting"). Checked `backend/data/resume_history.db`'s `master_resumes` table for existing records with a comma-joined single-element `items` array (the symptom of the old bug): the table currently has 0 rows, so no affected record exists in this deployment today. If one is ever created before this fix ships elsewhere, it will keep mis-matching until the record is re-saved through the fixed validator (e.g. via a no-op `PUT`); this pass does not add a backfill for that case.

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
# Profile skills data migration

- `CATEGORY_KEYWORDS` remains a tech-only supplemental relevance signal, so
  tech profiles have a signal that other occupations may not. This is a known
  asymmetry, not a bug to fix by hand-authoring clinical or trades vocabulary:
  direct matching against a profile category's own items is the
  occupation-neutral signal.

Real profiles under `backend/data/` remain on the legacy keyed-dictionary
shape with `ats_config.skills_order`. They continue to load through the
read-time compatibility shim in `backend/services/profile_skills.py`; migrate
them separately when their private data can be reviewed.
