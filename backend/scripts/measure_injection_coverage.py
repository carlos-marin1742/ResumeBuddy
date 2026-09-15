"""Report how selected job-description keywords are routed into profile skills.

Run from backend with: python scripts/measure_injection_coverage.py
This standalone report deliberately lives outside pytest's ``test_*.py`` naming
convention, so it is not collected by the documented pytest command.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = BACKEND_DIR / "data" / "fixtures"
sys.path.insert(0, str(BACKEND_DIR))

from services.claude_service import (  # noqa: E402
    PREFERRED_SKILL_CASING,
    SKILL_TO_CATEGORY,
    determine_skills_to_add,
)
from services.profile_skills import normalize_profile_skills  # noqa: E402


OUTCOMES = ("SKIPPED", "MAPPED", "MAPPED_MISSING", "UNMAPPED")

# Platform Engineer. Vocabulary: common Platform Engineer postings emphasizing
# cloud infrastructure, CI/CD, observability, and service reliability.
# Items marked "already present" deliberately exercise the skip branch.
TECH_KEYWORDS = [
    "Python",  # already present
    "FastAPI",  # already present
    "React",  # already present
    "Docker",  # already present
    "Git",  # already present
    "JavaScript",
    "SQL",
    "RAG",
    "Kubernetes",
    "PostgreSQL",
    "AWS",
    "Terraform",
    "GitHub Actions",
    "CI/CD",
    "Linux",
    "Prometheus",
    "Grafana",
    "Kafka",
    "Observability",
    "Incident response",
]

# Clinical Laboratory Technician. Vocabulary: common laboratory-technician
# postings emphasizing specimen workflow, quality, safety, and lab systems.
# Items marked "already present" deliberately exercise the skip branch.
CLINICAL_KEYWORDS = [
    "Venipuncture",  # already present
    "Vital signs",  # already present
    "CPR/AED",  # already present
    "Good Laboratory Practice",
    "Standard operating procedures",
    "Clinical data management",
    "Phlebotomy",
    "Specimen processing",
    "Laboratory information systems",
    "CLIA",
    "CAP accreditation",
    "Quality control",
    "Quality assurance",
    "Infection control",
    "Personal protective equipment",
    "Centrifugation",
    "Medical terminology",
    "Patient identification",
    "Blood collection",
    "HIPAA",
]

# Industrial Electrician. Vocabulary: common industrial-electrician postings
# emphasizing electrical installation, controls, diagnostics, and safety.
# Items marked "already present" deliberately exercise the skip branch.
TRADES_KEYWORDS = [
    "Motor controls",  # already present
    "OSHA-10",  # already present
    "Lockout/tagout",  # already present
    "Electrical troubleshooting",
    "Programmable logic controllers",
    "Variable frequency drives",
    "Blueprint reading",
    "NFPA 70E",
    "National Electrical Code",
    "Arc flash analysis",
    "Preventive maintenance",
    "Control panels",
    "Three-phase systems",
    "Conduit installation",
    "Cable pulling",
    "Electrical schematics",
    "Multimeters",  # already present
    "Industrial automation",
    "Root cause analysis",
    "Job hazard analysis",
]


MEASUREMENTS = [
    {
        "fixture": "tech_fixture",
        "occupation": "Platform Engineer",
        "keywords": TECH_KEYWORDS,
        "skill_dictionary": {
            "terms": {
                "kubernetes": "tools",
                "postgresql": "backend",
                "aws": "tools",
                "terraform": "tools",
                "github actions": "tools",
                "ci/cd": "tools",
                "linux": "tools",
                "prometheus": "tools",
                "grafana": "tools",
                "kafka": "backend",
                "observability": "backend",
                "incident response": "tools",
            }
        },
        "human_categories": {
            "Kubernetes": "tools",
            "PostgreSQL": "backend",
            "AWS": "tools",
            "Terraform": "tools",
            "GitHub Actions": "tools",
            "CI/CD": "tools",
            "Linux": "tools",
            "Prometheus": "tools",
            "Grafana": "tools",
            "Kafka": "backend",
            "Observability": "backend",
            "Incident response": "tools",
        },
    },
    {
        "fixture": "clinical_fixture",
        "occupation": "Clinical Laboratory Technician",
        "keywords": CLINICAL_KEYWORDS,
        "skill_dictionary": {
            "terms": {
                "good laboratory practice": "clinical_skills",
                "standard operating procedures": "clinical_skills",
                "clinical data management": "systems",
                "phlebotomy": "clinical_skills",
                "specimen processing": "clinical_skills",
                "laboratory information systems": "systems",
                "clia": "certifications_licenses",
                "cap accreditation": "certifications_licenses",
                "quality control": "clinical_skills",
                "quality assurance": "clinical_skills",
                "infection control": "clinical_skills",
                "personal protective equipment": "clinical_skills",
                "centrifugation": "clinical_skills",
                "medical terminology": "patient_care",
                "patient identification": "patient_care",
                "blood collection": "clinical_skills",
                "hipaa": "certifications_licenses",
            }
        },
        "human_categories": {
            "Good Laboratory Practice": "clinical_skills",
            "Standard operating procedures": "clinical_skills",
            "Clinical data management": "systems",
            "Phlebotomy": "clinical_skills",
            "Specimen processing": "clinical_skills",
            "Laboratory information systems": "systems",
            "CLIA": "certifications_licenses",
            "CAP accreditation": "certifications_licenses",
            "Quality control": "clinical_skills",
            "Quality assurance": "clinical_skills",
            "Infection control": "clinical_skills",
            "Personal protective equipment": "clinical_skills",
            "Centrifugation": "clinical_skills",
            "Medical terminology": "patient_care",
            "Patient identification": "patient_care",
            "Blood collection": "clinical_skills",
            "HIPAA": "certifications_licenses",
        },
    },
    {
        "fixture": "trades_fixture",
        "occupation": "Industrial Electrician",
        "keywords": TRADES_KEYWORDS,
        "skill_dictionary": {
            "terms": {
                "electrical troubleshooting": "technical_skills",
                "programmable logic controllers": "technical_skills",
                "variable frequency drives": "technical_skills",
                "blueprint reading": "technical_skills",
                "nfpa 70e": "safety_compliance",
                "national electrical code": "safety_compliance",
                "arc flash analysis": "safety_compliance",
                "preventive maintenance": "technical_skills",
                "control panels": "equipment",
                "three-phase systems": "technical_skills",
                "conduit installation": "technical_skills",
                "cable pulling": "technical_skills",
                "electrical schematics": "technical_skills",
                "industrial automation": "technical_skills",
                "root cause analysis": "technical_skills",
                "job hazard analysis": "safety_compliance",
            }
        },
        "human_categories": {
            "Electrical troubleshooting": "technical_skills",
            "Programmable logic controllers": "technical_skills",
            "Variable frequency drives": "technical_skills",
            "Blueprint reading": "technical_skills",
            "NFPA 70E": "safety_compliance",
            "National Electrical Code": "safety_compliance",
            "Arc flash analysis": "safety_compliance",
            "Preventive maintenance": "technical_skills",
            "Control panels": "equipment",
            "Three-phase systems": "technical_skills",
            "Conduit installation": "technical_skills",
            "Cable pulling": "technical_skills",
            "Electrical schematics": "technical_skills",
            "Multimeters": "equipment",
            "Industrial automation": "technical_skills",
            "Root cause analysis": "technical_skills",
            "Job hazard analysis": "safety_compliance",
        },
    },
]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def classify_keywords(
    skills: list[dict], keywords: list[str], skill_dictionary: dict | None = None
) -> list[tuple[str, str]]:
    """Classify the four current determine_skills_to_add branches."""
    groups = normalize_profile_skills(skills)
    existing_skills = {
        item.lower()
        for group in groups
        for item in group["items"]
        if isinstance(item, str)
    }
    category_names = {group["key"].lower() for group in groups}
    dictionary_terms = (
        skill_dictionary.get("terms", {}) if isinstance(skill_dictionary, dict) else {}
    )
    classifications = []

    for keyword in keywords:
        keyword_lower = keyword.strip().lower()
        if keyword_lower in existing_skills:
            outcome = "SKIPPED"
        elif isinstance(dictionary_terms, dict) and keyword_lower in dictionary_terms:
            outcome = (
                "MAPPED"
                if dictionary_terms[keyword_lower].lower() in category_names
                else "MAPPED_MISSING"
            )
        elif keyword_lower in SKILL_TO_CATEGORY:
            outcome = (
                "MAPPED"
                if SKILL_TO_CATEGORY[keyword_lower].lower() in category_names
                else "MAPPED_MISSING"
            )
        else:
            outcome = "UNMAPPED"
        classifications.append((keyword, outcome))

    return classifications


def fallback_rendered_keyword(keyword: str) -> str:
    return PREFERRED_SKILL_CASING.get(keyword.strip().lower(), keyword.strip())


def print_result(
    resume: dict, measurement: dict, label: str, skill_dictionary: dict | None = None
) -> float:
    keywords = measurement["keywords"]
    # This direct call is the behavior under measurement; it makes no network calls.
    skills_to_add = determine_skills_to_add(
        resume["skills"], keywords, skill_dictionary
    )
    classifications = classify_keywords(resume["skills"], keywords, skill_dictionary)
    counts = Counter(outcome for _, outcome in classifications)
    non_skipped = len(keywords) - counts["SKIPPED"]
    mapped_coverage = counts["MAPPED"] / non_skipped * 100 if non_skipped else 0.0

    print(label)
    print("OUTCOME          COUNT  PERCENT")
    for outcome in OUTCOMES:
        count = counts[outcome]
        print(f"{outcome:<16} {count:>5}  {count / len(keywords) * 100:>6.1f}%")
    print(
        "COVERAGE         "
        f"{counts['MAPPED']}/{non_skipped} non-skipped keywords reached a real "
        f"profile category ({mapped_coverage:.1f}%)"
    )
    print("ADDITIONAL_SKILLS (current result -> human profile category)")
    fallback_keywords = [
        keyword
        for keyword, outcome in classifications
        if outcome in {"MAPPED_MISSING", "UNMAPPED"}
    ]
    for keyword in fallback_keywords:
        rendered = fallback_rendered_keyword(keyword)
        landed = rendered in skills_to_add.get("additional_skills", [])
        status = "additional_skills" if landed else "not returned"
        print(f"- {keyword} -> {status} -> {measurement['human_categories'][keyword]}")
    return mapped_coverage


def print_measurement(measurement: dict) -> None:
    resume = load_fixture(measurement["fixture"])
    print(f"{measurement['fixture']} - {measurement['occupation']}")
    without_dictionary = print_result(resume, measurement, "WITHOUT DICTIONARY")
    with_dictionary = print_result(
        resume,
        measurement,
        "WITH HAND-SEEDED DICTIONARY",
        measurement["skill_dictionary"],
    )
    print(
        "HEADLINE         "
        f"{without_dictionary:.1f}% without a dictionary, "
        f"{with_dictionary:.1f}% with one"
    )
    print()


def main() -> None:
    for measurement in MEASUREMENTS:
        print_measurement(measurement)


if __name__ == "__main__":
    main()
