from routes.extract import flatten_resume_keywords


def test_flatten_resume_keywords_supports_list_based_skills_and_tags():
    resume = {
        "skills": [
            {"category": "Languages", "items": ["Python", "SQL"]},
            {"category": "Empty", "items": []},
        ],
        "experience": [{"bullets": [{"text": "Built APIs", "tags": ["FastAPI"]}]}],
        "projects": [{"bullets": [{"text": "Deployed app", "tags": ["Docker"]}]}],
    }

    assert flatten_resume_keywords(resume) == {
        "python",
        "sql",
        "fastapi",
        "docker",
    }


def test_flatten_resume_keywords_supports_legacy_dict_skills_and_keywords():
    resume = {
        "skills": {"languages": ["Python"], "backend": ["FastAPI"]},
        "experience": [{"bullets": [{"keywords": ["REST"]}]}],
        "projects": [{"bullets": [{"keywords": ["Docker"]}]}],
    }

    assert flatten_resume_keywords(resume) == {
        "python",
        "fastapi",
        "rest",
        "docker",
    }
