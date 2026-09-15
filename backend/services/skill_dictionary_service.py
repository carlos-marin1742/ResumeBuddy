"""Stable hashing and safe lookup for per-master-resume skill dictionaries."""

import hashlib
import json
from collections.abc import Iterable

from services.master_resume_adapter import master_resume_to_profile
from services.profile_skills import normalize_profile_skills


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
