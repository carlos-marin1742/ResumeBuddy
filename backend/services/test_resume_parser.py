from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from services.resume_parser import extract_docx_text, extract_pdf_text, parse_resume_text


def _docx_with_paragraphs(*paragraphs: str) -> bytes:
    body = "".join(
        f"<w:p><w:r><w:t>{paragraph}</w:t></w:r></w:p>"
        for paragraph in paragraphs
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def test_docx_text_is_parsed_into_reviewable_resume_fields():
    content = _docx_with_paragraphs(
        "Jamie Rivera",
        "Product Manager",
        "jamie@example.com | 312-555-0100 | https://linkedin.com/in/jamie",
        "Professional Summary",
        "Product leader focused on accessible software.",
        "Skills",
        "Roadmaps",
        "User research",
        "Projects",
        "Portfolio redesign",
        "Improved navigation and accessibility.",
    )

    draft, warnings = parse_resume_text(extract_docx_text(content))

    assert draft["contact"]["name"] == "Jamie Rivera"
    assert draft["contact"]["email"] == "jamie@example.com"
    assert draft["contact"]["linkedin"] == "https://linkedin.com/in/jamie"
    assert draft["targetRole"] == ""
    assert draft["summary"] == "Product leader focused on accessible software."
    assert draft["skills"] == [{
        "category": "Skills",
        "items": "Roadmaps, User research",
    }]
    assert draft["projects"][0]["name"] == "Portfolio redesign"
    assert "Review all imported fields" in warnings[0]


def test_empty_extracted_text_is_rejected():
    with pytest.raises(ValueError, match="No readable text"):
        parse_resume_text(" \n ")


def test_invalid_docx_is_rejected():
    with pytest.raises(ValueError, match="DOCX file could not be read"):
        extract_docx_text(b"not-a-docx")


def test_pdf_extraction_includes_embedded_link_destinations():
    class FakeAnnotation:
        def get_object(self):
            return {"/A": {"/URI": "https://www.linkedin.com/in/example"}}

    class FakePage:
        def extract_text(self):
            return "Jordan Lee"

        def get(self, key):
            return [FakeAnnotation()] if key == "/Annots" else None

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    with patch("services.resume_parser.PdfReader", return_value=FakeReader()):
        text = extract_pdf_text(b"%PDF")

    assert text.splitlines() == [
        "https://www.linkedin.com/in/example",
        "Jordan Lee",
    ]


def test_conventional_resume_maps_multiple_entries_to_their_fields():
    text = """
Jamie Rivera
Product Manager
Chicago, IL | jamie@example.com | 312-555-0100
Professional Summary
Product leader focused on accessible software.
Professional Experience
Acme Corp | Chicago, IL
Senior Product Manager | January 2022 - Present
Led a cross-functional product team.
Beta Labs | Remote
Product Manager | June 2019 - December 2021
Launched two customer-facing products.
Education
State University
Bachelor of Science in Information Systems | May 2019
Technical Skills
Product: Roadmaps, User research
Tools: Jira, Figma
Projects
Accessibility Toolkit | https://github.com/jamie/a11y
Created reusable accessibility guidance.
Certifications
Certified Scrum Product Owner | Scrum Alliance | March 2023
"""

    draft, _ = parse_resume_text(text)

    assert draft["contact"]["location"] == "Chicago, IL"
    assert draft["targetRole"] == ""
    assert draft["experience"] == [
        {
            "company": "Acme Corp",
            "title": "Senior Product Manager",
            "location": "Chicago, IL",
            "startDate": "2022-01",
            "endDate": "",
            "highlights": "Led a cross-functional product team.",
        },
        {
            "company": "Beta Labs",
            "title": "Product Manager",
            "location": "Remote",
            "startDate": "2019-06",
            "endDate": "2021-12",
            "highlights": "Launched two customer-facing products.",
        },
    ]
    assert draft["education"] == [{
        "institution": "State University",
        "degree": "Bachelor of Science",
        "field": "Information Systems",
        "graduationDate": "2019-05",
    }]
    assert draft["skills"] == [
        {"category": "Product", "items": "Roadmaps, User research"},
        {"category": "Tools", "items": "Jira, Figma"},
    ]
    assert draft["projects"] == [{
        "name": "Accessibility Toolkit",
        "technologies": "",
        "description": "Created reusable accessibility guidance.",
        "links": [{
            "name": "GitHub",
            "url": "https://github.com/jamie/a11y",
        }],
    }]
    assert draft["certifications"] == [{
        "name": "Certified Scrum Product Owner",
        "issuer": "Scrum Alliance",
        "date": "2023-03",
    }]


def test_visually_positioned_resume_maps_unheaded_and_combined_sections():
    text = """
https://example.com/portfolio
https://github.com/example
https://www.linkedin.com/in/example
Jordan Lee
Austin, TX | 512-555-0100 | jordan@example.com | Portfolio | GitHub | LinkedIn
Software Engineer | Full-Stack & Applied AI
Full-stack engineer who ships production systems.
Builds reliable services for regulated data.
TECHNICAL SKILLS
AI & LLMs:
Claude API, LangChain, RAG
Backend & Cloud:
Python, FastAPI, PostgreSQL, AWS
PROFESSIONAL EXPERIENCE
Regional Health — Austin, TX 06/2022 – Present
Software Developer
Built and shipped a full-stack operations platform.
Community Hospital — Austin, TX 04/2020 – 09/2021
Research Coordinator
Improved enrollment workflows by 20%.
SELECTED PROJECTS
Document Checker
Python, FastAPI, Claude API
Built a compliance classification pipeline.
Billing Workflow
React, Express, AWS
Designed a multi-user billing application.
EDUCATION & CERTIFICATIONS
State University — BS, Biological Sciences May 2019
Cloud AI Engineer — Professional Certificate April 2024
Full Stack Engineer — Professional Certificate October 2023
"""

    draft, _ = parse_resume_text(text)

    assert draft["contact"]["linkedin"] == "https://www.linkedin.com/in/example"
    assert draft["contact"]["portfolio"] == "https://example.com/portfolio"
    assert draft["summary"] == (
        "Full-stack engineer who ships production systems. "
        "Builds reliable services for regulated data."
    )
    assert draft["experience"][0] == {
        "company": "Regional Health",
        "title": "Software Developer",
        "location": "Austin, TX",
        "startDate": "2022-06",
        "endDate": "",
        "highlights": "Built and shipped a full-stack operations platform.",
    }
    assert draft["experience"][1]["company"] == "Community Hospital"
    assert draft["experience"][1]["title"] == "Research Coordinator"
    assert draft["skills"] == [
        {"category": "AI & LLMs", "items": "Claude API, LangChain, RAG"},
        {"category": "Backend & Cloud", "items": "Python, FastAPI, PostgreSQL, AWS"},
    ]
    assert draft["projects"] == [
        {
            "name": "Document Checker",
            "technologies": "Python, FastAPI, Claude API",
            "description": "Built a compliance classification pipeline.",
            "links": [],
        },
        {
            "name": "Billing Workflow",
            "technologies": "React, Express, AWS",
            "description": "Designed a multi-user billing application.",
            "links": [],
        },
    ]
    assert draft["education"] == [{
        "institution": "State University",
        "degree": "BS",
        "field": "Biological Sciences",
        "graduationDate": "2019-05",
    }]
    assert draft["certifications"] == [
        {
            "name": "Cloud AI Engineer",
            "issuer": "Professional Certificate",
            "date": "2024-04",
        },
        {
            "name": "Full Stack Engineer",
            "issuer": "Professional Certificate",
            "date": "2023-10",
        },
    ]


def test_research_resume_layout_maps_into_editable_fields():
    text = """
Carlos Marin
Houston, Texas | 713-791-3494 | carlosmarinjr1@gmail.com
Dedicated Clinical Research professional with 4+ years of comprehensive experience in Phase II-IV trials, specializing in
site management, regulatory compliance, and data integrity. Leverages a deep understanding of ICH-GCP and ALCOA+
principles to transition into a Clinical Research Associate role focused on multi-site oversight.
TECHNICAL SKILLS
●\u200b Study Oversight: Site Initiation (SIV), Routine Monitoring (IMV), and Close-out (COV) Preparation. ●\u200b Regulatory Compliance: ICH-GCP, FDA Code of Federal Regulations, ALCOA+ Principles.
EXPERIENCE
Clinical Research Coordinator – Heart Failure | Houston Methodist Hospital
04/2023 – 09/2025
●\u200b Managed a portfolio of Phase II-IV trials.
Clinical Research Coordinator | DM Clinical Research
09/2021 – 03/2023
●\u200b Oversaw execution of 12 clinical protocols.
EDUCATION
University of Houston - Downtown, Houston, Texas 2017
B.S. - Biological and Physical Sciences
Certifications & Systems
Certifications: GCP & Human Subjects Research Training (CITI Program), IATA Dangerous Goods. Systems: CTMS, eTMF, EDC (Medidata Rave), EMR (Epic). Software: Microsoft Excel (Advanced), Word, PowerPoint.
"""

    draft, _ = parse_resume_text(text)

    assert draft["contact"]["name"] == "Carlos Marin"
    assert draft["summary"].startswith("Dedicated Clinical Research professional")
    assert draft["skills"][0]["category"] == "Study Oversight"
    assert draft["experience"][0]["title"] == "Clinical Research Coordinator – Heart Failure"
    assert draft["experience"][0]["company"] == "Houston Methodist Hospital"
    assert draft["experience"][1]["company"] == "DM Clinical Research"
    assert draft["education"][0] == {
        "institution": "University of Houston - Downtown, Houston, Texas",
        "degree": "B.S.",
        "field": "Biological and Physical Sciences",
        "graduationDate": "2017",
    }
    assert {group["category"] for group in draft["skills"]} >= {"Systems", "Software"}
    assert [item["name"] for item in draft["certifications"]] == [
        "GCP & Human Subjects Research Training (CITI Program)",
        "IATA Dangerous Goods.",
    ]
