"""Convert reviewed builder resumes into the tailoring/rendering schema."""

import re


def _lines(value: str) -> list[str]:
    return [
        re.sub(r"^[\s•●▪◦*-]+", "", line).strip()
        for line in str(value or "").splitlines()
        if line.strip()
    ]


def master_resume_to_profile(resume: dict) -> dict:
    skill_groups = resume.get("skills", [])
    if isinstance(skill_groups, str):
        skill_groups = [{"category": "Skills", "items": skill_groups}]

    skills = {}
    skill_labels = {}
    for index, group in enumerate(skill_groups):
        if not isinstance(group, dict) or not group.get("category", "").strip():
            continue
        category = f"builder_{index}"
        skills[category] = [
            item.strip()
            for item in str(group.get("items", "")).split(",")
            if item.strip()
        ]
        skill_labels[category] = group["category"].strip()

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
            "skill_labels": skill_labels,
        },
    }
