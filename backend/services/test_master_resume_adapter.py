from services.master_resume_adapter import master_resume_to_profile


def test_master_resume_adapter_preserves_experience_bullets_and_builder_fields():
    profile = master_resume_to_profile({
        "contact": {"name": "Jamie Rivera", "email": "jamie@example.com"},
        "targetRole": "Research Resume",
        "summary": "Clinical research professional.",
        "skills": [{"category": "Systems", "items": "CTMS, EDC"}],
        "experience": [{
            "company": "Example Hospital",
            "title": "Research Coordinator",
            "location": "Houston, TX",
            "startDate": "2023-01",
            "endDate": "",
            "highlights": "Managed trials.\nResolved queries.",
        }],
        "education": [{
            "institution": "State University",
            "degree": "B.S.",
            "field": "Biology",
            "graduationDate": "2017",
        }],
        "projects": [],
        "certifications": [{"name": "GCP", "issuer": "CITI", "date": ""}],
    })

    assert profile["summary"]["default"] == "Clinical research professional."
    assert profile["skills"] == {"builder_0": ["CTMS", "EDC"]}
    assert [bullet["text"] for bullet in profile["experience"][0]["bullets"]] == [
        "Managed trials.",
        "Resolved queries.",
    ]
    assert profile["education"][0]["graduation_date"] == "2017"
    assert profile["certifications"][0]["name"] == "GCP"
