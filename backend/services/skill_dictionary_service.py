"""Stable hashing and safe lookup for per-master-resume skill dictionaries."""

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from services.claude_service import _call_claude
from services.master_resume_adapter import master_resume_to_profile
from services.profile_skills import normalize_profile_skills


SEED_FAILURE_BACKOFF = timedelta(hours=1)


def normalized_target_job_title(value: object) -> str:
    """Normalize the only role input that participates in a dictionary hash."""
    return " ".join(value.lower().split()) if isinstance(value, str) else ""


def compute_profile_hash(
    skill_category_keys: Iterable[str], target_job_title: object
) -> str:
    """Return a process-stable SHA-256 hash of category keys and target role."""
    payload = {
        "skill_category_keys": sorted(str(key) for key in skill_category_keys),
        "target_job_title": normalized_target_job_title(target_job_title),
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def profile_hash_for_resume(resume: dict) -> str:
    """Hash only the adapted resume fields that invalidate a dictionary."""
    groups = normalize_profile_skills(
        resume.get("skills", {}), resume.get("ats_config", {}).get("skills_order")
    )
    meta = resume.get("meta", {})
    occupation = meta.get("occupation", "") if isinstance(meta, dict) else ""
    return compute_profile_hash((group["key"] for group in groups), occupation)


def skill_dictionary_is_current(record) -> bool:
    """Whether a master record has a dictionary matching its current profile."""
    dictionary = getattr(record, "skill_dictionary", None)
    if not isinstance(dictionary, dict):
        return False
    profile = master_resume_to_profile(record.resume_data)
    return dictionary.get("profile_hash") == profile_hash_for_resume(profile)


def lookup_skill_dictionary_category(record, keyword: str) -> str | None:
    """Return a current dictionary category for a keyword, or no safe mapping."""
    dictionary = getattr(record, "skill_dictionary", None)
    if not isinstance(dictionary, dict) or not skill_dictionary_is_current(record):
        return None

    terms = dictionary.get("terms")
    if not isinstance(terms, dict) or not isinstance(keyword, str):
        return None

    profile = master_resume_to_profile(record.resume_data)
    category_names = {
        group["key"].lower(): group["key"]
        for group in normalize_profile_skills(profile.get("skills", {}))
    }
    keyword_lower = keyword.strip().lower()
    category = next(
        (value for term, value in terms.items()
         if isinstance(term, str) and term.lower() == keyword_lower),
        None,
    )
    if not isinstance(category, str):
        return None
    return category_names.get(category.lower())


def _seed_prompt(profile: dict) -> str:
    groups = normalize_profile_skills(profile.get("skills", {}))
    payload = {
        "target_job_title": profile.get("meta", {}).get("occupation", ""),
        "skill_categories": [{"key": group["key"], "label": group["label"]} for group in groups],
        "existing_skill_items": {group["key"]: group["items"] for group in groups},
        "summary": profile.get("summary", {}).get("default", ""),
        "project_names": [item.get("name", "") for item in profile.get("projects", [])],
        "certification_names": [item.get("name", "") for item in profile.get("certifications", [])],
        "experience_job_titles_may_describe_prior_or_unrelated_work": [
            item.get("title", "") for item in profile.get("experience", [])
            if isinstance(item, dict) and item.get("title", "")
        ],
    }
    return f"""Build a per-resume occupational vocabulary dictionary. Return 60-100 terms that are useful for the target role.

Experience job titles are explicitly possibly prior or unrelated work, especially for a career changer. Do not let them drive the vocabulary. Experience bullet text is intentionally unavailable.

Map every term only to one of the supplied skill category keys. Use every category where the occupation warrants it, not merely the most obvious categories. Return only terms you can confidently place; omit uncertain terms rather than guessing, because unplaced terms safely fall to Additional Skills later. Terms must be lowercased.

Return JSON only, with this exact shape: {{"terms": [{{"term": "lowercased occupational term", "category": "category_key"}}]}}. If a term repeats, the last entry wins.

Resume context:
{json.dumps(payload, ensure_ascii=False)}"""


def _validated_terms(raw: str, category_keys: set[str]) -> dict[str, str]:
    parsed = json.loads(raw)
    entries = parsed.get("terms") if isinstance(parsed, dict) else None
    if isinstance(entries, dict):
        entries = [{"term": term, "category": category} for term, category in entries.items()]
    if not isinstance(entries, list):
        raise ValueError("Dictionary response has no terms list.")
    terms: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        term, category = entry.get("term"), entry.get("category")
        if not isinstance(term, str) or not isinstance(category, str):
            continue
        term = term.strip().lower()
        if term and category in category_keys:
            terms[term] = category  # duplicate terms are deliberately last-wins
    return terms


def seed_skill_dictionary(record, now: datetime | None = None) -> dict:
    """Seed a record's dictionary, preserving a working dictionary on failure."""
    current_time = now or datetime.now(timezone.utc)
    attempted_at = current_time.isoformat()
    profile = master_resume_to_profile(record.resume_data)
    category_keys = {group["key"] for group in normalize_profile_skills(profile.get("skills", {}))}
    try:
        terms = _validated_terms(_call_claude(
            "You classify occupational vocabulary into supplied resume skill categories.",
            _seed_prompt(profile),
        ), category_keys)
        if not terms:
            raise ValueError("Dictionary response yielded no valid terms.")
    except Exception:
        existing = dict(record.skill_dictionary or {})
        existing.update({"last_attempt_at": attempted_at, "last_attempt_failed": True})
        record.skill_dictionary = existing
        return {"status": "failed"}
    record.skill_dictionary = {
        "terms": terms,
        "profile_hash": profile_hash_for_resume(profile),
        "seeded_at": attempted_at,
        "last_attempt_at": attempted_at,
        "last_attempt_failed": False,
    }
    return {"status": "seeded", "term_count": len(terms)}


def seed_backoff_active(dictionary: object, now: datetime | None = None) -> bool:
    if not isinstance(dictionary, dict) or not dictionary.get("last_attempt_failed"):
        return False
    attempted_at = dictionary.get("last_attempt_at")
    if not isinstance(attempted_at, str):
        return False
    try:
        attempt_time = datetime.fromisoformat(attempted_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (now or datetime.now(timezone.utc)) - attempt_time < SEED_FAILURE_BACKOFF
