"""Render editable cover-letter text as a letter-size PDF."""

import concurrent.futures
import html
import re
from pathlib import Path


def cover_letter_filename(candidate_name: str, company: str, job_title: str) -> str:
    """Build a filesystem-safe download name from application context."""
    values = [candidate_name, company, job_title, "Cover-Letter"]
    parts = [
        re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
        for value in values
    ]
    return f"{'-'.join(part for part in parts if part)}.pdf"


def _render_cover_letter_html(letter: str) -> str:
    """Return self-contained HTML with the required 12pt Times typography."""
    escaped_letter = html.escape(letter, quote=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <style>
    @page {{ size: Letter; margin: 1in; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: #000;
      font-family: "Times New Roman", Times, serif;
      font-size: 12pt;
      line-height: 1.15;
    }}
    .letter {{
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: break-word;
    }}
  </style>
</head>
<body>
  <div class="letter">{escaped_letter}</div>
</body>
</html>"""


def _build_cover_letter_pdf_worker(letter: str, output_path: str | Path) -> Path:
    from playwright.sync_api import sync_playwright

    resolved_path = Path(output_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(_render_cover_letter_html(letter), wait_until="load")
            page.pdf(
                path=str(resolved_path),
                format="Letter",
                margin={
                    "top": "1in",
                    "bottom": "1in",
                    "left": "1in",
                    "right": "1in",
                },
                print_background=True,
            )
        finally:
            browser.close()

    return resolved_path


def build_cover_letter_pdf(letter: str, output_path: str | Path) -> Path:
    """Build the PDF in a worker thread, matching the resume PDF pipeline."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            _build_cover_letter_pdf_worker,
            letter,
            output_path,
        ).result()
