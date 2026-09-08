"""Convert reviewed builder resumes into the tailoring/rendering schema."""

import re

from services.profile_skills import normalize_profile_skills


def _lines(value: str) -> list[str]:
    return [
        re.sub(r"^[\s•●▪◦*-]+", "", line).strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]


def split_skill_items(value) -> list[str]:
    """Split a raw skills string into individual items.

    Rule (shared with the frontend's splitSkillItems, pinned by a fixture
    list in tests rather than shared code across the JS/Python boundary):
    a newline anywhere means split on lines, with commas on those lines kept
    literal; with no newline, split on commas except commas nested inside
    ( ) or [ ]. Each item is trimmed and blanks are dropped. A non-string
    value yields [].
    """
    if not isinstance(value, str):
        return []
    if "\n" in value:
        parts = value.splitlines()
    else:
        parts = []
        current: list[str] = []
        depth = 0
        for char in value:
            if char in "([":
                depth += 1
            elif char in ")]":
                depth = max(0, depth - 1)
            if char == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(char)
        parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def _skill_items(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return split_skill_items(value)


def _skill_category_slug(category) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(category or "").lower()).strip("_")


def master_resume_to_profile(resume: dict) -> dict:
    skill_groups = resume.get("skills", [])
    if isinstance(skill_groups, str):
        skill_groups = [{"category": "Skills", "items": skill_groups}]

    normalized_groups = []
    used_keys = set()
    for index, group in enumerate(skill_groups):
        if not isinstance(group, dict):
            continue
        category = str(group.get("key", "")).strip()
        if not category:
            category = _skill_category_slug(group.get("category", ""))
        if not category:
            category = f"skill_{index}"

        base_category = category
        suffix = 2
        while category in used_keys:
            category = f"{base_category}_{suffix}"
            suffix += 1

        used_keys.add(category)
        normalized_groups.append({
            "key": category,
            "label": str(group.get("category") or category),
            "items": _skill_items(group.get("items", "")),
        })

    skills = {
        group["key"]: group["items"]
        for group in normalize_profile_skills(normalized_groups)
    }

    experience = []
    for index, item in enumerate(resume.get("experience", [])):
        bullets = [
            {"id": f"master-exp-{index}-{bullet_index}", "text": text, "keywords": []}
            for bullet_index, text in enumerate(_lines(item.get("highlights", "")))
        ]
        experience.append({
            "company": item.get("company", ""),
            "title": item.get("title", ""),
            "location": item.get("location", ""),
            "start_date": item.get("startDate", ""),
            "end_date": item.get("endDate", ""),
            "bullets": bullets,
        })

    projects = []
    for index, item in enumerate(resume.get("projects", [])):
        projects.append({
            "id": f"master-project-{index}",
            "name": item.get("name", ""),
            "tech_stack": [
                value.strip()
                for value in str(item.get("technologies", "")).split(",")
                if value.strip()
            ],
            "links": {
                str(link.get("name", "")).strip().casefold(): link.get("url", "")
                for link in item.get("links", [])
                if isinstance(link, dict) and link.get("name") and link.get("url")
            },
            "bullets": [
                {
                    "id": f"master-project-{index}-{bullet_index}",
                    "text": text,
                    "keywords": [],
                }
                for bullet_index, text in enumerate(_lines(item.get("description", "")))
            ],
        })

    return {
        "meta": {
            "label": resume.get("targetRole", ""),
            "target_roles": [],
        },
        "contact": dict(resume.get("contact", {})),
        "summary": {"default": resume.get("summary", ""), "variants": {}},
        "skills": skills,
        "experience": experience,
        "projects": projects,
        "education": [
            {
                "institution": item.get("institution", ""),
                "degree": item.get("degree", ""),
                "field": item.get("field", ""),
                "graduation_date": item.get("graduationDate", ""),
            }
            for item in resume.get("education", [])
        ],
        "certifications": [
            {
                "name": item.get("name", ""),
                "issuer": item.get("issuer", ""),
                "date": item.get("date", ""),
            }
            for item in resume.get("certifications", [])
        ],
        "ats_config": {
            "skills_order": list(skills),
        },
    }
