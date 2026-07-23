# base_resume.json — Schema Reference

This document describes the structure of `base_resume.json`, the foundational data layer for the ATS Resume Builder. All downstream services (tailoring, generation, ATS scoring) read from this file.

---

## Top-Level Structure

```
base_resume.json
├── meta
├── contact
├── summary
├── skills
├── projects
├── experience
├── education
├── certifications
└── ats_config
```

---

## `meta`

Bookkeeping block. Not rendered in the output resume.

| Field | Type | Description |
|---|---|---|
| `version` | string | Schema version number |
| `last_updated` | string (YYYY-MM-DD) | Date the file was last modified |
| `target_roles` | string[] | Role types this resume is optimized for |

---

## `contact`

Personal and professional contact information.

| Field | Type | Description |
|---|---|---|
| `name` | string | Full name |
| `location` | string | City, State |
| `phone` | string | Phone number |
| `email` | string | Email address |
| `portfolio` | string | Portfolio URL |
| `github` | string | GitHub profile URL |
| `linkedin` | string | LinkedIn profile URL |

> **To update links:** Replace the placeholder strings (`"Portfolio"`, `"GitHub"`, `"LinkedIn"`) with full URLs, e.g. `"https://github.com/yourusername"`.

---

## `summary`

Professional summary block with role-specific variants.

| Field | Type | Description |
|---|---|---|
| `default` | string | Fallback summary used when no variant matches the JD |
| `variants` | object | Named summaries keyed by role type |

### `summary.variants`

| Key | When to use |
|---|---|
| `ai_focused` | JD emphasizes LLMs, RAG, AI engineering |
| `backend_focused` | JD emphasizes APIs, backend services, Python |
| `ml_focused` | JD emphasizes model training, CV, data science |

> **To add a variant:** Add a new key under `variants` with a string value, e.g. `"devops_focused": "..."`.

---

## `skills`

Categorized skills list. Each category is a string array.

| Category | Description |
|---|---|
| `languages` | Programming languages |
| `ai_ml` | AI/ML frameworks, tools, and techniques |
| `backend` | Backend frameworks and server technologies |
| `frontend` | Frontend frameworks and UI libraries |
| `databases_cloud` | Databases, data tools, and cloud platforms |
| `tools` | Developer tooling and utilities |

The render order is controlled by `ats_config.skills_order`.

> **To add a skill:** Append a string to the appropriate category array.

---

## `projects`

Array of technical project entries.

### Project Object

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (kebab-case) |
| `name` | string | Display name of the project |
| `created_at_work` | boolean | Optional. Set to `true` for a project created as part of professional work; these projects receive selection priority |
| `tech_stack` | string[] | Technologies used |
| `links.github` | string | GitHub repo URL |
| `links.preview` | string | Live demo or deployment URL |
| `bullets` | Bullet[] | Achievement bullets (see below) |

### Bullet Object

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique bullet identifier |
| `text` | string | Full bullet text as it appears on the resume |
| `metrics` | object | Optional. Quantified results extracted from the bullet |
| `metrics.impact` | string | Primary metric, e.g. `"80% reduction in processing time"` |
| `keywords` | string[] | ATS-relevant terms this bullet targets |
| `strength` | `"high"` \| `"medium"` \| `"low"` | Priority signal for tailoring logic |

> **Bullet selection logic:** When tailoring for a JD, the service ranks bullets by keyword overlap and `strength`, then caps output at `ats_config.max_bullets_per_project`.

> **Project selection logic:** When more than three projects are present, the service selects three before tailoring. Projects with `created_at_work: true` are considered first, then projects are ranked by overlap with the job description and candidate-selected keywords. Original order breaks ties.

---

## `experience`

Array of professional work experience entries.

### Experience Object

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (kebab-case) |
| `company` | string | Employer name |
| `location` | string | City, State |
| `title` | string | Job title |
| `start_date` | string (YYYY-MM) | Start date |
| `end_date` | string (YYYY-MM) or `"present"` | End date |
| `bullets` | Bullet[] | Achievement bullets (same structure as project bullets) |

---

## `education`

Array of educational credentials.

| Field | Type | Description |
|---|---|---|
| `institution` | string | School name |
| `degree` | string | Degree type (e.g. `"BS"`, `"MS"`) |
| `field` | string | Field of study |
| `graduation_date` | string (YYYY-MM) | Month and year of graduation |

---

## `certifications`

Array of professional certifications.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (kebab-case) |
| `name` | string | Certification name |
| `issuer` | string | Issuing organization |
| `type` | string | e.g. `"Professional Certificate"` |
| `date` | string (YYYY-MM) | Date earned |
| `keywords` | string[] | ATS-relevant terms this certification signals |

---

## `ats_config`

Control block for tailoring and generation behavior. Read by `claude_service.py` and `resume_builder.py`.

| Field | Type | Description |
|---|---|---|
| `keyword_injection_targets` | string[] | Sections where keywords are injected during tailoring |
| `max_bullets_per_project` | number | Max bullets rendered per project |
| `max_bullets_per_role` | number | Max bullets rendered per experience role |
| `preferred_bullet_strength` | string | Minimum strength threshold (`"high"` filters out `"medium"` and `"low"`) |
| `skills_order` | string[] | Order in which skill categories are rendered on the resume |

---

## Adding New Content

| Task | What to edit |
|---|---|
| Add a new project | Append an object to the `projects` array |
| Add a new job | Append an object to the `experience` array |
| Add a new skill | Append a string to the relevant `skills` category |
| Add a summary variant | Add a key/value pair under `summary.variants` |
| Update contact links | Edit string values in the `contact` block |
| Tune output length | Adjust `max_bullets_per_project` / `max_bullets_per_role` in `ats_config` |
