"""
build_resume_pdf.py
-------------------
Generates a single-page PDF resume from a structured resume dict.
Uses Playwright (headless Chromium) to render HTML/CSS → PDF.

Usage (standalone):
    python build_resume_pdf.py resume.json output.pdf

Public API:
    build_pdf(resume_data, output_path) -> Path
    build_pdf_with_overrides(resume_data, output_path, overrides) -> Path
    _render_html(resume, spacing_adjust, overrides) -> str
"""

import concurrent.futures
import json
import shutil
import sys
import tempfile
from pathlib import Path


def _render_html(resume: dict, spacing_adjust: float = 0, overrides: dict | None = None) -> str:
    """
    Render resume dict to HTML string.

    overrides (optional): dict with keys:
        font_size       (float, pt)  — default 8.5
        margin          (float, in)  — default 0.4
        entry_spacing   (float, pt)  — overrides entry_margin
        section_spacing (float, pt)  — overrides section_margin
    """
    contact    = resume.get("contact", {})
    skills     = resume.get("skills", {})
    experience = resume.get("experience", [])
    projects   = resume.get("projects", [])
    education  = resume.get("education", [])
    certs      = resume.get("certifications", [])
    ats_config = resume.get("ats_config", {})
    highlights = set(s.lower() for s in resume.get("skills_to_highlight", []))

    summary_text = (
        resume.get("tailored_summary") or
        (resume["summary"] if isinstance(resume.get("summary"), str)
         else (resume.get("summary") or {}).get("default", ""))
    )

    skills_order = ats_config.get("skills_order") or list(skills.keys())
    skill_labels = {
        "languages": "Languages", "ai_ml": "AI / ML", "backend": "Backend",
        "frontend": "Frontend", "databases_cloud": "Data & Cloud", "tools": "Tools",
    }

    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    def fmt_date(d):
        if not d or d == "present": return "Present"
        parts = d.split("-")
        year = parts[0]
        if len(parts) >= 2:
            try:
                month = MONTHS[int(parts[1]) - 1]
                return f"{month} {year}"
            except (ValueError, IndexError):
                pass
        return year

    def bullet_text(b):
        if isinstance(b, str): return b
        return b.get("text") or b.get("tailored") or ""

    # Contact row
    contact_parts = []
    if contact.get("location"): contact_parts.append(contact["location"])
    if contact.get("phone"):    contact_parts.append(contact["phone"])
    if contact.get("email"):    contact_parts.append(f'<a href="mailto:{contact["email"]}">{contact["email"]}</a>')
    for label, key in [("Portfolio","portfolio"),("GitHub","github"),("LinkedIn","linkedin")]:
        if contact.get(key): contact_parts.append(f'<a href="{contact[key]}">{label}</a>')
    contact_html = "  <span class='sep'>|</span>  ".join(contact_parts)

    # Skills
    skills_html = ""
    for cat in skills_order:
        items = skills.get(cat)
        if not items: continue
        label = skill_labels.get(cat, cat)
        items_html = ""
        for i, skill in enumerate(items):
            comma = ", " if i > 0 else ""
            hl = " class='hl'" if skill.lower() in highlights else ""
            items_html += f"{comma}<span{hl}>{skill}</span>"
        skills_html += f"<div class='skill-row'><span class='skill-cat'>{label}:</span> {items_html}</div>"

    # Experience
    exp_html = ""
    for exp in experience:
        bullets_html = "".join(f"<li>{bullet_text(b)}</li>" for b in exp.get("bullets",[]) if bullet_text(b))
        location = f" <span class='dot'>•</span> {exp['location']}" if exp.get("location") else ""
        exp_html += f"""
        <div class='entry'>
          <div class='entry-header'>
            <span class='entry-title'>{exp.get('title','')}</span>
            <span class='entry-date'>{fmt_date(exp.get('start_date'))}&ndash;{fmt_date(exp.get('end_date'))}</span>
          </div>
          <div class='entry-sub'>{exp.get('company','')}{location}</div>
          <ul>{bullets_html}</ul>
        </div>"""

    # Projects
    proj_html = ""
    for proj in projects:
        tech    = " · ".join(proj.get("tech_stack", []))
        name    = proj.get("name", "Project")
        github  = proj.get("links", {}).get("github")
        preview = proj.get("links", {}).get("preview")
        name_html    = f'<a href="{github}">{name}</a>' if github else name
        preview_html = f' <span class="dot">·</span> <a href="{preview}">Live Demo</a>' if preview else ""
        bullets_html = "".join(f"<li>{bullet_text(b)}</li>" for b in proj.get("bullets",[]) if bullet_text(b))
        proj_html += f"""
        <div class='entry'>
          <div class='entry-header'>
            <span class='entry-title'>{name_html}{preview_html}</span>
            <span class='entry-date entry-tech'>{tech}</span>
          </div>
          <ul>{bullets_html}</ul>
        </div>"""

    # Education
    edu_html = ""
    for edu in education:
        grad = fmt_date(edu.get("graduation_date","")) if edu.get("graduation_date") else ""
        edu_html += f"""
        <div class='entry'>
          <div class='entry-header'>
            <span class='entry-title'>{edu.get('degree','')} in {edu.get('field','')}&ensp;<span class='entry-sub-inline'>{edu.get('institution','')}</span></span>
            <span class='entry-date'>{grad}</span>
          </div>
        </div>"""

    # Certifications
    cert_html = ""
    for cert in certs:
        year   = fmt_date(cert.get("date","")) if cert.get("date") else ""
        issuer = cert.get("issuer","")
        ctype  = cert.get("type","")
        sub    = f"{issuer} — {ctype}" if ctype else issuer
        cert_html += f"""
        <div class='entry'>
          <div class='entry-header'>
            <span class='entry-title'>{cert.get('name','')}&ensp;<span class='entry-sub-inline'>{sub}</span></span>
            <span class='entry-date'>{year}</span>
          </div>
        </div>"""

    def section(title, body):
        return f"<div class='section'><div class='section-title'>{title}</div>{body}</div>"

    sections = ""
    if summary_text: sections += section("SUMMARY",        f"<p class='summary'>{summary_text}</p>")
    if skills_html:  sections += section("SKILLS",         skills_html)
    if exp_html:     sections += section("EXPERIENCE",     exp_html)
    if proj_html:    sections += section("PROJECTS",       proj_html)
    if edu_html:     sections += section("EDUCATION",      edu_html)
    if cert_html:    sections += section("CERTIFICATIONS", cert_html)

    # ── Spacing ───────────────────────────────────────────────────────────────
    has_projects     = bool(projects)
    skill_row_count  = sum(1 for cat in skills_order if skills.get(cat))
    has_dense_skills = skill_row_count >= 4 and not has_projects

    if overrides:
        # User-controlled override mode
        font_size_pt    = overrides.get("font_size", 8.5)
        margin_in       = overrides.get("margin", 0.4)
        entry_margin    = overrides.get("entry_spacing", 5.0)
        section_margin  = overrides.get("section_spacing", 6.0)
        li_margin       = 1.5
        contact_margin  = 6.0
        section_pb      = 0.5
        body_lh         = "1.28"
        page_margin_css = f"{margin_in}in 0.5in {margin_in}in 0.5in"
    else:
        # Auto-fit mode
        font_size_pt    = 8.5
        page_margin_css = "0.4in 0.5in 0.4in 0.5in"

        if has_projects:
            li_margin      = max(0.5, 1.0 + spacing_adjust)
            entry_margin   = max(2.0, 5.0 + spacing_adjust)
            section_margin = max(3.0, 6.0 + (spacing_adjust * 0.5))
            contact_margin = max(4.0, 6.0 + spacing_adjust)
            section_pb     = max(0.3, 0.5 + (spacing_adjust * 0.2))
            body_lh        = "1.25"
        elif has_dense_skills:
            li_margin      = max(0.5, 1.5 + spacing_adjust)
            entry_margin   = max(2.0, 6.0 + spacing_adjust)
            section_margin = max(3.0, 7.0 + (spacing_adjust * 0.5))
            contact_margin = max(4.0, 7.0 + spacing_adjust)
            section_pb     = max(0.3, 0.5 + (spacing_adjust * 0.2))
            body_lh        = "1.25"
        else:
            li_margin      = max(0.5, 2.5 + spacing_adjust)
            entry_margin   = max(3.0, 7.0 + spacing_adjust)
            section_margin = max(4.0, 8.0 + (spacing_adjust * 0.5))
            contact_margin = max(5.0, 7.0 + spacing_adjust)
            section_pb     = max(0.5, 1.0 + (spacing_adjust * 0.2))
            body_lh        = "1.30"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{
    size: letter;
    margin: {page_margin_css};
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: {font_size_pt}pt;
    line-height: {body_lh};
    color: #000;
    width: 100%;
  }}

  a {{ color: #000; text-decoration: underline; }}

  .name {{
    text-align: center;
    font-size: 16pt;
    font-weight: bold;
    line-height: 1.2;
    margin-bottom: 4pt;
  }}

  .contact {{
    text-align: center;
    font-size: 8pt;
    margin-bottom: {contact_margin:.1f}pt;
  }}

  .sep {{ margin: 0 2pt; color: #555; }}

  .section {{
    margin-top: {section_margin:.1f}pt;
  }}

  .section-title {{
    font-size: 9.5pt;
    font-weight: bold;
    text-transform: uppercase;
    border-bottom: 0.75pt solid #000;
    padding-bottom: {section_pb:.1f}pt;
    margin-bottom: 4pt;
    line-height: 1.3;
  }}

  .skill-row {{
    font-size: 8pt;
    line-height: 1.35;
  }}

  .skill-cat {{ font-weight: bold; }}
  .hl        {{ font-weight: normal; }}

  .entry {{ margin-top: {entry_margin:.1f}pt; }}
  .entry:first-child {{ margin-top: 0; }}

  .entry-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}

  .entry-title {{
    font-weight: bold;
    font-size: 9pt;
    flex: 1;
    line-height: 1.3;
  }}

  .entry-date {{
    font-style: italic;
    font-size: 8pt;
    white-space: nowrap;
    margin-left: 8pt;
    flex-shrink: 0;
  }}

  .entry-tech {{ font-style: italic; font-weight: normal; }}

  .entry-sub {{
    font-style: italic;
    font-size: 8pt;
    margin-bottom: 2pt;
    line-height: 1.3;
  }}

  .entry-sub-inline {{
    font-style: italic;
    font-weight: normal;
    font-size: 8.5pt;
  }}

  .dot {{ margin: 0 2pt; }}

  ul {{
    margin: 0;
    padding-left: 12pt;
    list-style-type: disc;
  }}

  li {{
    font-size: 8pt;
    line-height: 1.35;
    margin-bottom: {li_margin:.1f}pt;
  }}

  li:last-child {{ margin-bottom: 0; }}

  .summary {{
    font-size: 8pt;
    line-height: 1.35;
  }}
</style>
</head>
<body>
  <div class="name">{contact.get('name','')}</div>
  <div class="contact">{contact_html}</div>
  {sections}
</body>
</html>"""


def _build_pdf_worker(resume_data: dict, output_path) -> Path:
    """Auto-fit PDF — runs spacing feedback loop."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    usable_height = 979
    has_projects  = bool(resume_data.get("projects", []))
    has_certs     = bool(resume_data.get("certifications", []))

    if has_projects:
        spacing          = -1.5
        expand_threshold = 160
    elif has_certs:
        spacing          = -0.5
        expand_threshold = 70
    else:
        spacing          = -0.5
        expand_threshold = 40

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()

        for attempt in range(5):
            page.set_content(_render_html(resume_data, spacing), wait_until="networkidle")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name

            page.pdf(path=tmp_path, format="Letter", print_background=True)
            reader     = PdfReader(tmp_path)
            page_count = len(reader.pages)

            if page_count == 1:
                content_height = page.evaluate("document.body.scrollHeight")
                slack = usable_height - content_height

                if slack > expand_threshold and attempt < 4:
                    Path(tmp_path).unlink(missing_ok=True)
                    line_count = page.evaluate(
                        "document.querySelectorAll('li, .entry, .skill-row, .section').length"
                    )
                    if line_count > 0:
                        spacing += min(1.0, slack / line_count)
                    continue

                shutil.copy(tmp_path, output_path)
                Path(tmp_path).unlink(missing_ok=True)
                break

            Path(tmp_path).unlink(missing_ok=True)
            spacing -= 2.0

        else:
            page.pdf(path=str(output_path), format="Letter", print_background=True)

        browser.close()

    return output_path


def _build_pdf_overrides_worker(resume_data: dict, output_path, overrides: dict) -> Path:
    """Custom PDF — uses exact override values, no auto-fit loop."""
    from playwright.sync_api import sync_playwright

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    margin_in = overrides.get("margin", 0.4)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(_render_html(resume_data, overrides=overrides), wait_until="networkidle")
        page.pdf(
            path=str(output_path),
            format="Letter",
            margin={
                "top":    f"{margin_in}in",
                "bottom": f"{margin_in}in",
                "left":   "0.5in",
                "right":  "0.5in",
            },
            print_background=True,
        )
        browser.close()

    return output_path


def build_pdf(resume_data: dict, output_path) -> Path:
    """Auto-fit single-page PDF."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_worker, resume_data, output_path)
        return future.result()


def build_pdf_with_overrides(resume_data: dict, output_path, overrides: dict) -> Path:
    """Custom PDF with user-specified spacing overrides."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_build_pdf_overrides_worker, resume_data, output_path, overrides)
        return future.result()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python build_resume_pdf.py <resume.json> <output.pdf>")
        sys.exit(1)
    resume = json.loads(Path(sys.argv[1]).read_text())
    out = build_pdf(resume, sys.argv[2])
    print(f"Written: {out}  ({out.stat().st_size:,} bytes)")