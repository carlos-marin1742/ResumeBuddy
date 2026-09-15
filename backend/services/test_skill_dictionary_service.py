"""Unit tests for per-master-resume skill dictionary hashing and lookup."""

import os
import subprocess
import sys

import pytest

from models import MasterResumeRecord
from services import claude_service
from services.claude_service import tailor_resume
from services.master_resume_adapter import master_resume_to_profile
from services.skill_dictionary_service import (
    compute_profile_hash,
    lookup_skill_dictionary_category,
    profile_hash_for_resume,
    seed_skill_dictionary,
    learn_static_skill_placements,
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


def test_seed_validates_terms_hashes_profile_and_avoids_experience_bullets(monkeypatch):
    record = _record(_builder_resume())
    prompt = {}
    def call_model(system, user):
        prompt["text"] = user
        return '{"terms":[{"term":"venipuncture","category":"clinical"},{"term":"elisa","category":"instruments"}]}'
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", call_model)

    result = seed_skill_dictionary(record)

    assert result == {"status": "seeded", "term_count": 2}
    assert record.skill_dictionary["terms"] == {"venipuncture": "clinical", "elisa": "instruments"}
    assert record.skill_dictionary["profile_hash"] == profile_hash_for_resume(master_resume_to_profile(record.resume_data))
    assert '"key": "clinical"' in prompt["text"]
    assert '"label": "Clinical Skills"' in prompt["text"]
    assert "Clinical Laboratory Technician" in prompt["text"]
    assert "Prepared samples." not in prompt["text"]
    assert "possibly prior or unrelated work" in prompt["text"]


def test_seed_drops_invalid_empty_and_duplicate_terms_last_wins(monkeypatch):
    record = _record()
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: '''{"terms":[
      {"term":"valid","category":"clinical"}, {"term":"VALID","category":"instruments"},
      {"term":"bad","category":"not-sent"}, {"term":" ","category":"clinical"}
    ]}''')

    seed_skill_dictionary(record)

    assert record.skill_dictionary["terms"] == {"valid": "instruments"}


@pytest.mark.parametrize("response", ["not json", '{"terms": []}'])
def test_seed_unparseable_or_empty_response_records_failure_without_terms(monkeypatch, response):
    record = _record()
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: response)

    assert seed_skill_dictionary(record) == {"status": "failed"}
    assert record.skill_dictionary["last_attempt_failed"] is True
    assert "terms" not in record.skill_dictionary


def test_failed_reseed_preserves_existing_terms_and_hash(monkeypatch):
    record = _record()
    original = _dictionary(record, {"venipuncture": "clinical"})
    record.skill_dictionary = original
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: "broken")

    seed_skill_dictionary(record)

    assert record.skill_dictionary["terms"] == original["terms"]
    assert record.skill_dictionary["profile_hash"] == original["profile_hash"]
    assert record.skill_dictionary["last_attempt_failed"] is True


def test_seeded_dictionary_drives_a_generation_category(monkeypatch):
    record = _record()
    monkeypatch.setattr(
        "services.skill_dictionary_service._call_claude",
        lambda *_: '{"terms":[{"term":"specimen accessioning","category":"clinical"}]}',
    )
    assert seed_skill_dictionary(record)["status"] == "seeded"
    monkeypatch.setattr(
        "services.claude_service._call_claude",
        lambda *_args, **_kwargs: '{"summary":"", "experiences":[], "projects":[], "skills_to_highlight":[]}',
    )

    generated = tailor_resume(
        master_resume_to_profile(record.resume_data), "Clinical laboratory role", ["Specimen Accessioning"], record.skill_dictionary,
    )

    assert generated.skills_to_add == {"clinical": ["Specimen Accessioning"]}


def test_learning_records_only_real_static_category_placements():
    record = _record(_builder_resume(categories=[{"key": "backend", "category": "Backend", "items": ["Python"]}]))
    record.skill_dictionary = _dictionary(record, {"seeded": "backend"})
    assert learn_static_skill_placements(record, master_resume_to_profile(record.resume_data)["skills"], ["FastAPI", "Python", "React", "Event Sourcing"])
    assert record.skill_dictionary["terms"]["fastapi"] == "backend"
    assert record.skill_dictionary["learned"] == ["fastapi"]
    assert "python" not in record.skill_dictionary["terms"]
    assert "react" not in record.skill_dictionary["terms"]
    assert "event sourcing" not in record.skill_dictionary["terms"]


def test_learning_never_overwrites_or_uses_stale_dictionary():
    record = _record(_builder_resume(categories=[{"key": "backend", "category": "Backend", "items": []}]))
    record.skill_dictionary = _dictionary(record, {"fastapi": "other"})
    assert not learn_static_skill_placements(record, master_resume_to_profile(record.resume_data)["skills"], ["FastAPI"])
    assert record.skill_dictionary["terms"]["fastapi"] == "other"
    record.skill_dictionary["profile_hash"] = "stale"
    assert not learn_static_skill_placements(record, master_resume_to_profile(record.resume_data)["skills"], ["FastAPI"])


def test_stale_dictionary_does_not_learn_a_new_static_term():
    record = _record(_builder_resume(categories=[{"key": "backend", "category": "Backend", "items": []}]))
    record.skill_dictionary = _dictionary(record, {})
    record.skill_dictionary["profile_hash"] = "stale"
    assert not learn_static_skill_placements(record, master_resume_to_profile(record.resume_data)["skills"], ["FastAPI"])
    assert record.skill_dictionary["terms"] == {}


def test_reseed_preserves_learned_but_seeded_term_wins(monkeypatch):
    record = _record()
    record.skill_dictionary = _dictionary(record, {"learned-only": "clinical", "conflict": "instruments"})
    record.skill_dictionary["learned"] = ["learned-only", "conflict"]
    monkeypatch.setattr("services.skill_dictionary_service._call_claude", lambda *_: '{"terms":[{"term":"conflict","category":"clinical"},{"term":"seeded","category":"instruments"}]}')
    seed_skill_dictionary(record)
    assert record.skill_dictionary["terms"] == {"learned-only": "clinical", "conflict": "clinical", "seeded": "instruments"}
    assert record.skill_dictionary["learned"] == ["learned-only"]


def test_learned_term_drives_the_second_generation_after_static_mapping_is_removed(monkeypatch):
    record = _record(_builder_resume(categories=[{"key": "backend", "category": "Backend", "items": []}]))
    record.skill_dictionary = _dictionary(record, {"seeded": "backend"})
    profile = master_resume_to_profile(record.resume_data)
    monkeypatch.setattr(
        "services.claude_service._call_claude",
        lambda *_args, **_kwargs: '{"summary":"", "experiences":[], "projects":[], "skills_to_highlight":[]}',
    )

    first = tailor_resume(profile, "Backend role", ["FastAPI"], record.skill_dictionary)
    assert first.skills_to_add == {"backend": ["FastAPI"]}  # branch 3
    assert learn_static_skill_placements(record, profile["skills"], ["FastAPI"])

    monkeypatch.delitem(claude_service.SKILL_TO_CATEGORY, "fastapi")
    second = tailor_resume(profile, "Backend role", ["FastAPI"], record.skill_dictionary)

    assert second.skills_to_add == {"backend": ["FastAPI"]}  # branch 2; static branch is unavailable
