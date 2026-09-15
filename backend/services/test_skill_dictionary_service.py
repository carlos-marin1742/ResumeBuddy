"""Unit tests for per-master-resume skill dictionary hashing and lookup."""

import os
import subprocess
import sys

from models import MasterResumeRecord
from services.master_resume_adapter import master_resume_to_profile
from services.skill_dictionary_service import (
    compute_profile_hash,
    lookup_skill_dictionary_category,
    profile_hash_for_resume,
)


def _builder_resume(*, categories=None, title="Clinical Laboratory Technician"):
    return {
        "targetJobTitle": title,
        "summary": "Careful laboratory professional.",
        "skills": categories or [
            {"key": "clinical", "category": "Clinical Skills", "items": ["Pipetting"]},
            {"key": "instruments", "category": "Instruments", "items": ["ELISA"]},
        ],
        "experience": [{"highlights": "Prepared samples."}],
    }


def _record(resume=None, dictionary=None):
    return MasterResumeRecord(
        name="Avery Example",
        target_role="Clinical Laboratory Technician",
        resume_data=resume or _builder_resume(),
        skill_dictionary=dictionary,
    )


def _dictionary(record, terms):
    profile = master_resume_to_profile(record.resume_data)
    return {
        "terms": terms,
        "profile_hash": profile_hash_for_resume(profile),
        "seeded_at": "2026-09-15T00:00:00Z",
        "last_attempt_at": None,
        "last_attempt_failed": False,
    }


def test_profile_hash_is_stable_across_separate_python_processes():
    keys = ["clinical", "instruments"]
    expected = compute_profile_hash(keys, " Clinical   Laboratory Technician ")
    script = (
        "from services.skill_dictionary_service import compute_profile_hash; "
        "print(compute_profile_hash(['clinical', 'instruments'], "
        "' Clinical   Laboratory Technician '))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
    )
    assert result.stdout.strip() == expected


def test_profile_hash_ignores_bullets_but_changes_for_categories_and_role():
    original = _builder_resume()
    original_profile = master_resume_to_profile(original)
    original_hash = profile_hash_for_resume(original_profile)

    edited_bullet = _builder_resume()
    edited_bullet["experience"][0]["highlights"] = "Edited ordinary bullet."
    assert profile_hash_for_resume(master_resume_to_profile(edited_bullet)) == original_hash

    added = _builder_resume(categories=original["skills"] + [{"key": "quality", "category": "Quality", "items": []}])
    renamed = _builder_resume(categories=[{"key": "clinical_renamed", "category": "Clinical Skills", "items": []}, original["skills"][1]])
    removed = _builder_resume(categories=[original["skills"][0]])
    changed_role = _builder_resume(title="Medical Laboratory Scientist")
    for changed in (added, renamed, removed, changed_role):
        assert profile_hash_for_resume(master_resume_to_profile(changed)) != original_hash


def test_profile_hash_normalizes_title_whitespace_and_case():
    assert compute_profile_hash(["clinical"], "  Clinical   Scientist ") == compute_profile_hash(
        ["clinical"], "clinical scientist"
    )


def test_lookup_returns_current_dictionary_category_case_insensitively():
    record = _record()
    record.skill_dictionary = _dictionary(record, {"venipuncture": "clinical"})
    assert lookup_skill_dictionary_category(record, "VENIPUNCTURE") == "clinical"


def test_lookup_returns_none_for_null_stale_or_deleted_category():
    record = _record()
    assert lookup_skill_dictionary_category(record, "venipuncture") is None

    record.skill_dictionary = _dictionary(record, {"venipuncture": "clinical"})
    record.skill_dictionary["profile_hash"] = "stale"
    assert lookup_skill_dictionary_category(record, "venipuncture") is None

    record.skill_dictionary = _dictionary(record, {"venipuncture": "deleted_category"})
    assert lookup_skill_dictionary_category(record, "venipuncture") is None
