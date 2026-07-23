"""Select the projects that are most relevant to a target job."""

import re


MAX_PROJECTS = 3

_STOP_WORDS = {
    "and",
    "are",
    "for",
    "from",
    "have",
    "the",
    "this",
    "using",
    "with",
}


def _terms(value: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(term) > 2 and term not in _STOP_WORDS
    }


def _project_text(project: dict) -> str:
    parts = [
        str(project.get("name", "")),
        *[str(item) for item in project.get("tech_stack", [])],
    ]
    for bullet in project.get("bullets", []):
        parts.append(str(bullet.get("text", "")))
        parts.extend(str(item) for item in bullet.get("keywords", []))
    return " ".join(parts).lower()


def _relevance_score(
    project: dict,
    job_description: str,
    selected_keywords: list[str],
) -> int:
    project_text = _project_text(project)
    normalized_keywords = [
        keyword.strip().lower() for keyword in selected_keywords if keyword.strip()
    ]
    keyword_score = sum(
        10 for keyword in normalized_keywords if keyword in project_text
    )
    return keyword_score + len(_terms(job_description) & _terms(project_text))


def select_relevant_projects(
    projects: list[dict],
    job_description: str,
    selected_keywords: list[str],
    limit: int = MAX_PROJECTS,
) -> list[dict]:
    """Return at most ``limit`` projects, prioritizing work-created projects."""
    if limit <= 0:
        return []
    if len(projects) <= limit:
        return list(projects)

    ranked = sorted(
        enumerate(projects),
        key=lambda item: (
            -int(item[1].get("created_at_work") is True),
            -_relevance_score(item[1], job_description, selected_keywords),
            item[0],
        ),
    )
    return [project for _, project in ranked[:limit]]
