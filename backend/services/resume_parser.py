"""Extract conservative, editable resume drafts from PDF and DOCX files."""

from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree

from pypdf import PdfReader


SECTION_ALIASES = {
    "summary": {"summary", "professional summary", "profile", "objective"},
    "experience": {
        "experience", "work experience", "professional experience", "employment",
        "employment history", "work history",
    },
    "education": {"education", "academic background", "education & training"},
    "education_certifications": {
        "education & certifications", "education and certifications",
    },
    "skills": {"skills", "technical skills", "core competencies", "technologies"},
    "projects": {"projects", "selected projects", "personal projects"},
    "certifications": {
        "certifications", "certificates", "licenses", "licenses & certifications",
    },
}

EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
    "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12,
    "december": 12,
}
MONTH_TOKEN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)"
)
DATE_TOKEN = rf"(?:{MONTH_TOKEN}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{4}})"
DATE_RANGE_PATTERN = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to)\s*"
    rf"(?P<end>{DATE_TOKEN}|present|current|now)",
    re.IGNORECASE,
)
SINGLE_DATE_PATTERN = re.compile(DATE_TOKEN, re.IGNORECASE)
LOCATION_PATTERN = re.compile(
    r"^(?:[A-Za-z .'-]+,\s*(?:[A-Z]{2}|[A-Za-z .'-]+)|Remote|Hybrid)$",
    re.IGNORECASE,
)


def extract_pdf_text(content: bytes) -> str:
    """Extract text from a text-based PDF without retaining the source."""
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise ValueError("Password-protected PDFs are not supported.")
        page_text = []
        annotation_urls = []
        for page in reader.pages:
            page_text.append(page.extract_text() or "")
            for annotation_reference in page.get("/Annots") or []:
                annotation = annotation_reference.get_object()
                action = annotation.get("/A")
                url = action.get("/URI") if action else None
                if url and url not in annotation_urls:
                    annotation_urls.append(str(url))
        return "\n".join([*annotation_urls, *page_text])
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF could not be read.") from exc


def extract_docx_text(content: bytes) -> str:
    """Extract paragraph and table-cell text from a DOCX archive."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            document = archive.read("word/document.xml")
    except (BadZipFile, KeyError) as exc:
        raise ValueError("The DOCX file could not be read.") from exc

    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as exc:
        raise ValueError("The DOCX file contains invalid document data.") from exc

    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _section_name(line: str) -> str | None:
    normalized = re.sub(r"[:\s]+$", "", line).strip().lower()
    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section
    return None


def _blank_draft() -> dict:
    return {
        "contact": {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "portfolio": "",
        },
        "targetRole": "",
        "summary": "",
        "experience": [{
            "company": "",
            "title": "",
            "location": "",
            "startDate": "",
            "endDate": "",
            "highlights": "",
        }],
        "education": [{
            "institution": "",
            "degree": "",
            "field": "",
            "graduationDate": "",
        }],
        "skills": [{"category": "", "items": ""}],
        "projects": [{
            "name": "",
            "technologies": "",
            "description": "",
            "links": [],
        }],
        "certifications": [{
            "name": "",
            "issuer": "",
            "date": "",
        }],
    }


def _split_parts(line: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*(?:\||\t)\s*", line) if part.strip()]


def _looks_like_location(value: str) -> bool:
    return bool(LOCATION_PATTERN.fullmatch(value.strip()))


def _split_company_location(value: str) -> tuple[str, str] | None:
    parts = [
        part.strip()
        for part in re.split(r"\s+[–—-]\s+", value.strip(), maxsplit=1)
    ]
    if len(parts) == 2 and _looks_like_location(parts[1]):
        return parts[0], parts[1]
    return None


def _parse_date(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"present", "current", "now"}:
        return ""
    if re.fullmatch(r"\d{4}", normalized):
        return ""
    numeric = re.fullmatch(r"(\d{1,2})/(\d{4})", normalized)
    if numeric:
        return f"{numeric.group(2)}-{int(numeric.group(1)):02d}"
    named = re.fullmatch(r"([A-Za-z]+)\s+(\d{4})", normalized)
    if named:
        month = MONTHS.get(named.group(1))
        if month:
            return f"{named.group(2)}-{month:02d}"
    return ""


def _without_match(line: str, match: re.Match) -> str:
    return re.sub(r"^[\s|,;:–—-]+|[\s|,;:–—-]+$", "", line[:match.start()] + line[match.end():])


def _parse_experience(lines: list[str]) -> list[dict]:
    anchors = []
    for index, line in enumerate(lines):
        match = DATE_RANGE_PATTERN.search(line)
        if match:
            remainder = _without_match(line, match)
            anchors.append((index, match, remainder))
    if not anchors:
        return [{
            "company": "",
            "title": "",
            "location": "",
            "startDate": "",
            "endDate": "",
            "highlights": "\n".join(lines),
        }]

    entries = []
    for anchor_index, (line_index, match, remainder) in enumerate(anchors):
        parts = _split_parts(remainder)
        previous_parts = _split_parts(lines[line_index - 1]) if line_index > 0 else []
        used_previous_header = len(parts) < 2 and bool(previous_parts)
        company_location = _split_company_location(remainder)
        used_next_title = (not parts or company_location is not None) and line_index + 1 < len(lines)

        title = parts[0] if parts else (lines[line_index + 1] if used_next_title else "")
        company = parts[1] if len(parts) > 1 else (previous_parts[0] if used_previous_header else "")
        location_candidates = parts[2:] if len(parts) > 1 else previous_parts[1:]
        location = next((part for part in location_candidates if _looks_like_location(part)), "")

        if company_location:
            company, location = company_location
            title = lines[line_index + 1] if used_next_title else ""
        elif used_previous_header and len(previous_parts) == 1:
            previous_company_location = _split_company_location(previous_parts[0])
            if previous_company_location:
                company, location = previous_company_location

        if not title and previous_parts:
            title = previous_parts[0]
            company = previous_parts[1] if len(previous_parts) > 1 else ""
            location = next((part for part in previous_parts[2:] if _looks_like_location(part)), "")

        next_line_index = anchors[anchor_index + 1][0] if anchor_index + 1 < len(anchors) else len(lines)
        next_remainder = anchors[anchor_index + 1][2] if anchor_index + 1 < len(anchors) else ""
        next_uses_previous = (
            anchor_index + 1 < len(anchors)
            and len(_split_parts(next_remainder)) < 2
            and _split_company_location(next_remainder) is None
            and next_line_index > line_index + 1
        )
        highlights_end = next_line_index - 1 if next_uses_previous else next_line_index
        highlights_start = line_index + 2 if used_next_title else line_index + 1
        highlights = lines[highlights_start:highlights_end]

        entries.append({
            "company": company,
            "title": title,
            "location": location,
            "startDate": _parse_date(match.group("start")),
            "endDate": _parse_date(match.group("end")),
            "highlights": "\n".join(highlights),
        })
    return entries


def _parse_degree(value: str) -> tuple[str, str]:
    degree_pattern = re.compile(
        r"^(?P<degree>Bachelor of (?:Science|Arts)|Master of (?:Science|Arts)|"
        r"Associate(?: of (?:Science|Arts))?|Doctor of [A-Za-z ]+|"
        r"B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|Ph\.?D\.?)"
        r"(?:\s+in\s+(?P<field>.+))?$",
        re.IGNORECASE,
    )
    match = degree_pattern.match(value.strip())
    if not match:
        return value.strip(), ""
    return match.group("degree"), (match.group("field") or "").strip()


def _parse_education(lines: list[str]) -> list[dict]:
    entries = []
    for index, line in enumerate(lines):
        match = SINGLE_DATE_PATTERN.search(line)
        if not match:
            continue
        remainder = _without_match(line, match)
        parts = _split_parts(remainder)
        institution = lines[index - 1] if index > 0 else ""
        degree_text = parts[0] if parts else ""
        if len(parts) > 1 and not institution:
            institution = parts[0]
            degree_text = parts[1]
        degree, field = _parse_degree(degree_text)
        entries.append({
            "institution": institution,
            "degree": degree,
            "field": field,
            "graduationDate": _parse_date(match.group(0)),
        })
    if entries:
        return entries
    return [{
        "institution": lines[0] if lines else "",
        "degree": lines[1] if len(lines) > 1 else "",
        "field": " | ".join(lines[2:]),
        "graduationDate": "",
    }]


def _link_name(url: str) -> str:
    lowered = url.lower()
    if "github.com" in lowered:
        return "GitHub"
    if "linkedin.com" in lowered:
        return "LinkedIn"
    return "Project link"


def _parse_projects(lines: list[str]) -> list[dict]:
    header_indexes = [index for index, line in enumerate(lines) if URL_PATTERN.search(line)]
    if not header_indexes:
        technology_indexes = [
            index for index, line in enumerate(lines)
            if index > 0
            and "," in line
            and len(line) <= 120
            and not line.endswith((".", ","))
        ]
        if technology_indexes:
            projects = []
            for position, technology_index in enumerate(technology_indexes):
                next_technology_index = (
                    technology_indexes[position + 1]
                    if position + 1 < len(technology_indexes)
                    else len(lines)
                )
                description_end = next_technology_index - 1 if position + 1 < len(technology_indexes) else len(lines)
                projects.append({
                    "name": lines[technology_index - 1],
                    "technologies": lines[technology_index],
                    "description": "\n".join(lines[technology_index + 1:description_end]),
                    "links": [],
                })
            return projects
        return [{
            "name": lines[0] if lines else "",
            "technologies": "",
            "description": "\n".join(lines[1:]),
            "links": [],
        }]

    projects = []
    for position, line_index in enumerate(header_indexes):
        line = lines[line_index]
        urls = [url.rstrip(".,;)") for url in URL_PATTERN.findall(line)]
        name = URL_PATTERN.sub("", line)
        name = re.sub(r"^[\s|,;:–—-]+|[\s|,;:–—-]+$", "", name)
        end = header_indexes[position + 1] if position + 1 < len(header_indexes) else len(lines)
        projects.append({
            "name": _split_parts(name)[0] if name else "",
            "technologies": "",
            "description": "\n".join(lines[line_index + 1:end]),
            "links": [
                {
                    "name": _link_name(url),
                    "url": url if url.lower().startswith("http") else f"https://{url}",
                }
                for url in urls
            ],
        })
    return projects


def _parse_certifications(lines: list[str]) -> list[dict]:
    entries = []
    for line in lines:
        match = SINGLE_DATE_PATTERN.search(line)
        remainder = _without_match(line, match) if match else line
        parts = _split_parts(remainder)
        if not parts:
            continue
        entries.append({
            "name": parts[0],
            "issuer": parts[1] if len(parts) > 1 else "",
            "date": _parse_date(match.group(0)) if match else "",
        })
    return entries or [{"name": "", "issuer": "", "date": ""}]


def _parse_combined_education_certifications(
    lines: list[str],
) -> tuple[list[dict], list[dict]]:
    education = []
    certifications = []
    index = 0
    while index < len(lines):
        detail_line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        date_match = SINGLE_DATE_PATTERN.search(detail_line)
        date_on_next_line = not date_match and bool(SINGLE_DATE_PATTERN.fullmatch(next_line))
        if date_on_next_line:
            date_match = SINGLE_DATE_PATTERN.search(next_line)
        detail_without_date = _without_match(detail_line, date_match) if date_match and not date_on_next_line else detail_line
        parts = [
            part.strip()
            for part in re.split(r"\s+[–—]\s+|\s*\|\s*", detail_without_date)
            if part.strip()
        ]
        date = _parse_date(date_match.group(0)) if date_match else ""

        if parts and re.search(r"\b(?:university|college|school|institute)\b", parts[0], re.IGNORECASE):
            degree_text = parts[1] if len(parts) > 1 else ""
            degree, field = _parse_degree(degree_text)
            if not field and "," in degree:
                degree, field = [value.strip() for value in degree.split(",", 1)]
            education.append({
                "institution": parts[0],
                "degree": degree,
                "field": field,
                "graduationDate": date,
            })
        elif parts:
            certifications.append({
                "name": parts[0],
                "issuer": parts[1] if len(parts) > 1 else "",
                "date": date,
            })
        index += 2 if date_on_next_line else 1

    return (
        education or [{"institution": "", "degree": "", "field": "", "graduationDate": ""}],
        certifications or [{"name": "", "issuer": "", "date": ""}],
    )


def parse_resume_text(text: str) -> tuple[dict, list[str]]:
    """Map extracted text into the editable builder shape without inventing facts."""
    lines = [re.sub(r"^[\u2022\u25cf\u25aa\u25e6*\-–—]\s*", "", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError("No readable text was found. Scanned resumes are not supported yet.")

    draft = _blank_draft()
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ALIASES}
    contact_lines = []
    current_section = None

    for line in lines:
        detected_section = _section_name(line)
        if detected_section:
            current_section = detected_section
        elif current_section:
            sections[current_section].append(line)
        else:
            contact_lines.append(line)

    contact_text = " | ".join(contact_lines)
    email = EMAIL_PATTERN.search(contact_text)
    phone = PHONE_PATTERN.search(contact_text)
    urls = URL_PATTERN.findall(contact_text)
    draft["contact"]["email"] = email.group(0) if email else ""
    draft["contact"]["phone"] = phone.group(0) if phone else ""

    for url in urls:
        normalized_url = url.rstrip(".,;)")
        if "linkedin.com" in normalized_url.lower():
            draft["contact"]["linkedin"] = normalized_url
        elif not draft["contact"]["portfolio"]:
            draft["contact"]["portfolio"] = normalized_url

    descriptive_lines = []
    for line in contact_lines:
        if EMAIL_PATTERN.search(line) or PHONE_PATTERN.search(line) or URL_PATTERN.search(line):
            for part in _split_parts(line):
                if _looks_like_location(part):
                    draft["contact"]["location"] = part
            continue
        if _looks_like_location(line):
            draft["contact"]["location"] = line
        else:
            descriptive_lines.append(line)
    if descriptive_lines:
        draft["contact"]["name"] = descriptive_lines[0]
    if len(descriptive_lines) > 1:
        draft["targetRole"] = descriptive_lines[1]

    draft["summary"] = " ".join(sections["summary"] or descriptive_lines[2:])
    skill_groups = []
    for line in sections["skills"]:
        if ":" in line:
            category, items = (part.strip() for part in line.split(":", 1))
            skill_groups.append({"category": category, "items": items})
        elif skill_groups:
            skill_groups[-1]["items"] = ", ".join(
                value for value in (skill_groups[-1]["items"], line) if value
            )
        else:
            skill_groups.append({"category": "Skills", "items": line})
    draft["skills"] = skill_groups or [{"category": "", "items": ""}]
    draft["experience"] = _parse_experience(sections["experience"])
    draft["education"] = _parse_education(sections["education"])
    draft["projects"] = _parse_projects(sections["projects"])
    draft["certifications"] = _parse_certifications(sections["certifications"])
    if sections["education_certifications"]:
        draft["education"], draft["certifications"] = _parse_combined_education_certifications(
            sections["education_certifications"]
        )

    warnings = [
        "Review all imported fields before saving. Dates and section details may need correction."
    ]
    if not email:
        warnings.append("No email address was detected.")
    return draft, warnings
