"""Normalize legacy and ordered resume skill shapes for backend consumers."""


def normalize_profile_skills(
    skills,
    skills_order: list[str] | None = None,
) -> list[dict]:
    """Return ordered ``key``/``label``/``items`` skill groups.

    Legacy profiles store a keyed dictionary and optionally a separate render
    order. Ordered profiles already store groups. This is the sole read-time
    compatibility boundary between those shapes.
    """
    if isinstance(skills, dict):
        keys = list(skills_order) if skills_order is not None else list(skills)
        return [
            {"key": key, "label": key, "items": list(skills.get(key) or [])}
            for key in keys
            if key in skills
        ]

    if isinstance(skills, list):
        groups = []
        for section in skills:
            if not isinstance(section, dict):
                continue
            key = str(section.get("key") or section.get("category") or "").strip()
            if not key:
                continue
            label = str(section.get("label") or section.get("category") or key).strip()
            groups.append({
                "key": key,
                "label": label or key,
                "items": list(section.get("items") or []),
            })
        return groups

    return []
