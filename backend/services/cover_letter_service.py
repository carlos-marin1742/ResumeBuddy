"""
cover_letter_service.py
-----------------------
LangChain-powered cover letter generation for ResuméBuddy.

Takes the TAILORED resume output (post claude_service.tailor_resume),
the job description, and the user's selected keywords, and generates
a grounded, sub-250-word cover letter via Claude Haiku.

Chain: ChatPromptTemplate | ChatAnthropic | StrOutputParser
"""
from dotenv import load_dotenv
load_dotenv()

import os
import re

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
TEMPERATURE = 0.7


# ---------------------------------------------------------------------------
# Pydantic response model
# ---------------------------------------------------------------------------

class CoverLetterResult(BaseModel):
    letter: str
    word_count: int
    company: str
    job_title: str


# ---------------------------------------------------------------------------
# LLM + chain setup
# ---------------------------------------------------------------------------

def _get_llm() -> ChatAnthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return ChatAnthropic(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        anthropic_api_key=api_key,
    )


_SYSTEM_PROMPT = """\
You are a professional career coach and expert copywriter. You write concise,
high-impact cover letters that sound like a confident human, not an AI.

Structure (do NOT label these sections in the output):
1. Hook: open by naming the specific role and company, connecting the
   candidate's background to the role in one strong sentence.
2. Bridge: one paragraph on the most relevant experience. Show, don't tell,
   using the candidate's real accomplishments and exact metrics.
3. Hard skills: briefly emphasize the technical toolkit and certifications
   most relevant to this job description.
4. Close: an enthusiastic but professional call to action.

Hard rules:
- Under 250 words. Plain text only, no markdown.
- Do NOT include section headings, labels, or a subject line.
- Do NOT use these phrases: "I am excited to apply", "I am writing to express",
  "proven track record", "passionate about", "hit the ground running".
- Only reference accomplishments, metrics, and skills that appear in the
  provided resume data. Never invent anything.
- Use active past-tense verbs (Deployed, Engineered, Reduced).
- Never use em-dashes or en-dashes anywhere in the output.
- Output ONLY the letter body: no preamble, no explanation, no signature block
  beyond a simple closing with the candidate's name.
"""

_USER_PROMPT = """\
Write a cover letter for this application.

CANDIDATE NAME: {candidate_name}
COMPANY: {company}
ROLE: {job_title}

KEYWORDS TO WEAVE IN NATURALLY (candidate-selected):
{keywords}

TAILORED RESUME DATA (source of truth — do not invent beyond this):
{resume_context}

JOB DESCRIPTION:
{job_description}
"""


def _build_chain():
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM_PROMPT),
        ("human", _USER_PROMPT),
    ])
    return prompt | _get_llm() | StrOutputParser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_resume_context(tailored_resume: dict) -> str:
    """
    Flatten the tailored resume dict into a compact plain-text block.
    Expects the shape produced by claude_service.tailor_resume().model_dump(),
    but degrades gracefully if fields are missing.
    """
    lines: list[str] = []

    if summary := tailored_resume.get("summary"):
        lines.append(f"SUMMARY: {summary}")

    if skills := tailored_resume.get("skills_to_highlight"):
        lines.append(f"KEY SKILLS: {', '.join(skills)}")

    for exp in tailored_resume.get("experiences", []):
        lines.append(f"\n{exp.get('title', '')} at {exp.get('company', '')}:")
        for b in exp.get("tailored_bullets", []):
            text = b.get("tailored") or b.get("original") or ""
            if text:
                lines.append(f"- {text}")

    return "\n".join(lines)


def _sanitize(text: str) -> str:
    """Belt-and-suspenders: strip dashes the model was told not to use."""
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cover_letter(
    tailored_resume: dict,
    job_description: str,
    company: str,
    job_title: str,
    selected_keywords: list[str],
    candidate_name: str = "Carlos Marin",
) -> CoverLetterResult:
    """
    Generate a cover letter grounded in the tailored resume.

    Args:
        tailored_resume:   TailoredResume.model_dump() from claude_service.
        job_description:   Full JD text.
        company:           Target company name (from app state).
        job_title:         Target role title (from app state).
        selected_keywords: Keywords the user confirmed in KeywordSelector.
        candidate_name:    Name for the letter closing.

    Returns:
        CoverLetterResult with the letter text and word count.
    """
    chain = _build_chain()

    raw = chain.invoke({
        "candidate_name": candidate_name,
        "company": company or "the company",
        "job_title": job_title or "this role",
        "keywords": ", ".join(selected_keywords) if selected_keywords else "none specified",
        "resume_context": _format_resume_context(tailored_resume),
        "job_description": job_description,
    })

    letter = _sanitize(raw)

    return CoverLetterResult(
        letter=letter,
        word_count=len(letter.split()),
        company=company,
        job_title=job_title,
    )


# ---------------------------------------------------------------------------
# Quick smoke test (run directly: python cover_letter_service.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stub_tailored = {
        "summary": "AI-focused full-stack engineer with hands-on RAG and LLM experience.",
        "skills_to_highlight": ["Python", "FastAPI", "LangChain", "RAG"],
        "experiences": [
            {
                "company": "Personal Projects",
                "title": "AI Engineer",
                "tailored_bullets": [
                    {
                        "original": "Built a RAG pipeline with LangChain and Chroma.",
                        "tailored": "Built a RAG pipeline using LangChain, Chroma, and HuggingFace embeddings, achieving 100% retrieval precision.",
                        "keywords_injected": ["RAG", "LangChain"],
                    }
                ],
            }
        ],
    }
    stub_jd = "We need an AI Engineer with Python, LangChain, and RAG experience to build LLM applications."

    result = generate_cover_letter(
        tailored_resume=stub_tailored,
        job_description=stub_jd,
        company="SampleCo",
        job_title="AI Engineer",
        selected_keywords=["Python", "LangChain", "RAG"],
    )
    print(f"[{result.word_count} words]\n")
    print(result.letter)