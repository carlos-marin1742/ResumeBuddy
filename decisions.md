# ResumeBuddy Decisions

This document records important choices and their rationale. It describes decisions already made, not future commitments.

## Use Auth0 for public multi-user authentication

ResumeBuddy will use Auth0 Universal Login for a future public multi-user application. The React SPA will use Authorization Code Flow with PKCE, send short-lived access tokens to FastAPI, and use the token's stable `sub` claim as the application-level owner identifier.

Why:

- Authentication, password storage, password reset, email verification, and social login should not be implemented locally.
- Auth0 supports the existing React SPA and FastAPI API boundary without requiring a database-platform migration.
- OAuth 2.0 and OpenID Connect provide a standard architecture suitable for a public application.

FastAPI remains responsible for authorization. Every query for master resumes, tailored history, cover letters, generated files, and generation sessions must be scoped to the authenticated owner. Hiding records in the client is not an authorization control.

The initial scope is individual accounts using email/password and Google login. Organizations, team sharing, roles, and an administrative UI are deferred. Existing unowned local records require an explicit one-time assignment to the developer's Auth0 `sub`; the application must not provide a public "claim unowned data" endpoint.

No Auth0 client secret belongs in the browser bundle. The application must not claim multi-user isolation until token validation, record ownership, download authorization, and session isolation are all implemented and tested.

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

The builder's `targetRole` field currently serves as the saved resume's user-defined title. It is retained for identifying the resume in the resume-selection UI and is not part of the rendered master-resume document. Resume imports leave this field blank so the user can name the saved resume explicitly.

## Preview master resumes in the client

After a successful save, the client renders the persisted structured payload in a dedicated read-only preview.

Why:

- Preview should not require AI generation or a job description.
- Structured rendering is fast and keeps the persistence change independent from Playwright PDF generation.
- Users can return directly to editing the same database record.

Tradeoff: master-resume PDF export is not yet implemented.

## Share master-resume typography between preview and generated output

The saved master-resume preview and its future generated HTML/PDF output will use the same semantic formatting contract. This includes font families, font sizes, weights, italics, colors, capitalization, section rules, date formatting, link treatment, and field ordering.

Page-fitting controls remain independent. PDF margins, paper padding, section spacing, entry spacing, and line spacing may differ from the browser preview and may be adjusted without changing the resume's visual identity.

The master-resume schema differs from the existing tailored-resume schema, so master resumes will use a dedicated HTML renderer rather than being forced through `build_resume_pdf.py` unchanged. Shared typography tokens and equivalent semantic markup should keep `MasterResumePreview` and generated output aligned.

Why:

- Manual entry and uploaded resumes already converge on the same reviewed master-resume data.
- The browser preview should accurately communicate the typography and hierarchy users will receive.
- Separating typography from page fitting preserves a consistent design while allowing one-page PDF optimization.
- A dedicated renderer avoids fragile conversions between master-resume fields and job-tailored fields.

## Keep runtime SQLite outside version control

`backend/data/resume_history.db` is ignored and must remain untracked.

Why:

- It contains personal resume and job-application data.
- Its contents are machine-specific runtime state and create noisy binary diffs.
- Tables and additive migrations are reproducible from the models and `init_db()`.

Adding a path to `.gitignore` does not remove an already tracked copy. Older clones must run `git rm --cached backend/data/resume_history.db` once and commit that index removal. This removes the file from Git without deleting the local database.

## Use same-origin API requests in the client

Browser requests use relative `/api` paths. Vite supplies the development proxy, while FastAPI serves the API and built frontend from the same origin in production.

Why:

- A hard-coded loopback address points to the browser user's machine after deployment.
- Same-origin requests avoid unnecessary CORS and mixed-content failures.
- The same client build works in local, Docker, and production environments.

## Support repeatable named project links

Each project may contain zero or more `{name, url}` links.

Why:

- A project may have a GitHub repository, live demo, case study, or documentation.
- A label is more meaningful on a resume than exposing a raw URL.
- Projects without links remain valid.

## Store skills as labeled categories

New master resumes represent skills as repeatable `{key, category, items}` entries, with `items` as an array of individual skill strings rather than a comma-joined string. Imports preserve labels such as `Frontend`, `AI & LLMs`, and `Backend & Cloud`, and the saved-resume preview renders those labels in bold.

The persistence API continues accepting the original plain string shape (both the whole-`skills`-as-string legacy form and a per-group string `items` value) so existing saved records remain compatible; both are normalized to the array shape before anything is persisted.

Splitting a skills textarea value into individual items happens once, in `ResumeBuilder`, on the way out of the component at save time — never in the backend and never while typing. A newline anywhere in the value means one skill per line, with commas inside those lines kept literal; with no newline, the value splits on commas that are not enclosed in `()` or `[]`, so a value like `Microsoft Office (Word, Excel, Outlook)` survives as one item. A skill whose only comma is unbracketed (e.g. `Phlebotomy, adult and pediatric`) still requires the newline escape to stay intact — this is a known limitation, not a bug, and the textarea placeholder calls it out.

## Builder skill keys remain stable in the adapted profile

`master_resume_to_profile` uses a builder skill group's stable `key` as the adapted profile's skill-dict key. For legacy or incomplete groups it falls back to an underscore slug of `category`, then `skill_{index}`; duplicate derived keys receive numeric suffixes. Positional `builder_{index}` keys were removed because a reorder or deletion changed downstream identifiers despite the builder already preserving a stable key.

The adapter no longer writes `ats_config.skill_labels`. No consumer read that side channel: PDF rendering maintains its own display-label mapping and reads `skills_order`, so retaining the adapter write would only preserve stale, unused data.

## The server owns skills splitting; the frontend splitter is UI feedback only

`backend/routes/master_resumes.py`'s `SkillCategoryInput.normalize_items` validator is the authoritative place a raw skills string becomes an array of items. It delegates to `split_skill_items` in `backend/services/master_resume_adapter.py`: a newline anywhere means split on lines with commas kept literal on those lines; with no newline, split on commas except commas nested inside `()` or `[]`; each item is trimmed and blanks are dropped. An already-array payload passes through unchanged. `master_resume_adapter.py::_skill_items` delegates to the same function for its string branch, so there is exactly one comma-splitting rule in the Python codebase.

`ResumeBuilder.jsx`'s `splitSkillItems` implements the identical rule in JavaScript and is kept deliberately, for immediate feedback while typing in the builder UI — it is not the source of truth and must not be removed. Because the boundary between the two is JS/Python, not a shared module, the two implementations are pinned together by an identical fixture list asserted in both test suites (`SKILL_ITEMS_FIXTURES` in `backend/services/test_master_resume_adapter.py` and `client/src/components/ResumeBuilder.test.jsx`) rather than by sharing code.

Why: before this decision, the validator only wrapped a raw string into a single-element array instead of splitting it. A payload like `"React, TypeScript, Vite"` persisted as one item, `_skill_items`'s list branch stripped but never split it, and `/api/extract-keywords` gap-matching compared it as one string against JD keywords like `react` — an exact-match failure. Skills that were genuinely on the resume silently reported as missing, with no exception and no log line. This is reachable via `PUT /api/master-resumes/{id}` on a legacy or hand-posted record, not only through the builder UI, so the server has to be the one that gets it right.

## Give each skill category a stable key

Each skill group carries a `key` alongside its user-facing `category` label. The key is generated once, at save, by slugifying the category name at that moment; once a group has a key it is never regenerated, even if the category is later renamed. Collisions get a numeric suffix, and a group with an empty category still gets a usable key.

Why: a later pass will cache keyword-to-category classifications, and that cache has to point at something stable. The `category` field is a user-facing display label the user can rename at any time (`Frontend` → `Front-end Development`); if a cache were keyed on the label, every rename would silently orphan its cached data. The key exists specifically so category renames are free. Do not collapse `key` and `category` back into a single field — that reintroduces the exact problem this decision solves.

## Derive the tailoring persona from profile data

The tailoring system prompt identifies the writer using the profile's optional `meta.occupation`; when that is absent, it uses the first `meta.target_roles` value, then the resume title. If none is available, it uses a neutral `professional` descriptor.

Why:

- The product supports occupations beyond technology and must not assign an unrecognized profile a technology persona.
- This data-driven chain avoids a fixed role-type branch and works for static profiles and reviewed builder resumes alike.
- The neutral fallback keeps tailoring industry-agnostic when profile metadata is incomplete.

## Preserve focused files and existing workflow contracts

Resume creation and parsing were added through focused components, services, and routes rather than rewriting the tailoring workflow.

Why:

- Existing profile tailoring remains backward compatible.
- New behavior is independently testable.
- The change does not overload `App.jsx` or existing generation services.
