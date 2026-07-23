"""Unit tests for deterministic project selection."""

from project_selection import select_relevant_projects


def _project(name: str, keywords: list[str], *, created_at_work: bool = False) -> dict:
    return {
        "name": name,
        "created_at_work": created_at_work,
        "tech_stack": keywords,
        "bullets": [{"text": f"Built {name}", "keywords": keywords}],
    }


def test_preserves_all_projects_and_order_when_three_or_fewer():
    projects = [
        _project("First", ["React"]),
        _project("Second", ["Python"]),
        _project("Third", ["Docker"]),
    ]

    assert select_relevant_projects(projects, "Python", ["Python"]) == projects


def test_selects_only_three_most_relevant_projects():
    projects = [
        _project("Unrelated", ["Excel"]),
        _project("API", ["Python", "FastAPI"]),
        _project("Frontend", ["React"]),
        _project("Platform", ["Python", "Docker"]),
    ]

    selected = select_relevant_projects(
        projects,
        "Build Python APIs with FastAPI, Docker, and React",
        ["Python", "FastAPI", "Docker", "React"],
    )

    assert [project["name"] for project in selected] == [
        "API",
        "Platform",
        "Frontend",
    ]


def test_work_projects_take_priority_over_more_relevant_personal_projects():
    projects = [
        _project("Personal Python", ["Python", "FastAPI"]),
        _project("Personal Docker", ["Docker"]),
        _project("Personal React", ["React"]),
        _project("Work Operations", ["Excel"], created_at_work=True),
    ]

    selected = select_relevant_projects(
        projects,
        "Python FastAPI Docker React",
        ["Python", "FastAPI", "Docker", "React"],
    )

    assert selected[0]["name"] == "Work Operations"
    assert len(selected) == 3


def test_ranks_work_projects_by_relevance_when_more_than_three_are_work_projects():
    projects = [
        _project("Work Excel", ["Excel"], created_at_work=True),
        _project("Work React", ["React"], created_at_work=True),
        _project("Work Python", ["Python"], created_at_work=True),
        _project("Work Docker", ["Docker"], created_at_work=True),
    ]

    selected = select_relevant_projects(
        projects,
        "Python Docker React",
        ["Python", "Docker", "React"],
    )

    assert [project["name"] for project in selected] == [
        "Work React",
        "Work Python",
        "Work Docker",
    ]


def test_uses_original_order_to_break_relevance_ties():
    projects = [_project(f"Project {index}", []) for index in range(4)]

    selected = select_relevant_projects(projects, "unmatched role", [])

    assert [project["name"] for project in selected] == [
        "Project 0",
        "Project 1",
        "Project 2",
    ]


def test_non_positive_limit_returns_empty_list():
    assert select_relevant_projects([_project("One", ["Python"])], "Python", [], 0) == []


def test_ignores_blank_selected_keywords():
    projects = [_project(f"Project {index}", []) for index in range(4)]

    selected = select_relevant_projects(projects, "unmatched role", ["", "   "])

    assert [project["name"] for project in selected] == [
        "Project 0",
        "Project 1",
        "Project 2",
    ]
