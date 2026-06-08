"""
claude_service.py
-----------------
AI service layer for the ATS resume builder.

Responsibilities:
  1. extract_keywords(job_description: str) -> KeywordExtractionResult
     Pulls structured keywords from a JD using Groq (free tier, fast).

  2. tailor_resume(base_resume: dict, job_description: str, selected_keywords: list[str]) -> TailoredResume
     Rewrites bullets and generates a targeted summary using Claude Haiku.

  3. score_resume(tailored_resume: dict, job_description: str, selected_keywords: list[str]) -> ATSScoreResult
     Heuristic ATS scoring — no API call, fast and deterministic.
"""
from dotenv import load_dotenv
load_dotenv()

import json
import os
import re
import string
from typing import Any

import anthropic
from groq import Groq
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class KeywordExtractionResult(BaseModel):
    hard_skills: list[str]
    soft_skills: list[str]
    tools_and_technologies: list[str]
    job_titles: list[str]
    certifications: list[str]
    priority_keywords: list[str]
    raw_response: str


class TailoredBullet(BaseModel):
    original: str
    tailored: str
    keywords_injected: list[str] = []


class TailoredExperience(BaseModel):
    company: str
    title: str
    tailored_bullets: list[TailoredBullet]


class TailoredProject(BaseModel):
    name: str
    tailored_bullets: list[TailoredBullet]


class TailoredResume(BaseModel):
    summary: str
    experiences: list[TailoredExperience]
    projects: list[TailoredProject] = []
    skills_to_highlight: list[str]
    skills_to_add: dict[str, list[str]] = {}
    skills_to_show: list[str] = []
    skills_to_filter: dict[str, list[str]] = {}
    raw_response: str


class ATSScoreResult(BaseModel):
    overall_score: int
    keyword_coverage: float
    matched_keywords: list[str]
    missing_keywords: list[str]
    suggestions: list[str]
    raw_response: str


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------

def _get_anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return anthropic.Anthropic(api_key=api_key)


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Add it to your .env file or export it in your shell."
        )
    return Groq(api_key=api_key)


CLAUDE_MODEL      = "claude-haiku-4-5-20251001"
GROQ_MODEL        = "llama-3.3-70b-versatile"
CLAUDE_MAX_TOKENS = 4096
GROQ_MAX_TOKENS   = 2048


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_claude(system: str, user: str, max_tokens: int = CLAUDE_MAX_TOKENS) -> str:
    client = _get_anthropic_client()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


def _call_groq(system: str, user: str, max_tokens: int = GROQ_MAX_TOKENS) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content


def _extract_json(text: str) -> Any:
    cleaned = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
    return json.loads(cleaned)


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation for fuzzy keyword matching."""
    return text.lower().translate(str.maketrans("", "", string.punctuation))


def limit_character_count(text: str) -> str:
    """Limits the character count of a bullet to less than 165 characters (maximum 164)."""
    if len(text) >= 165:
        return text[:164]
    return text


def validate_keywords_in_text(text: str, keywords: list[str]) -> list[str]:
    """
    Returns the subset of keywords that actually appear in text,
    using normalized (case-insensitive, punctuation-stripped) word matching.
    """
    normalized_text = _normalize(text)
    return [
        kw for kw in keywords
        if all(word in normalized_text for word in _normalize(kw).split())
    ]


SKILL_TO_CATEGORY = {
    # languages
    "python": "languages",
    "typescript": "languages",
    "javascript": "languages",
    "js": "languages",
    "ts": "languages",
    "html5": "languages",
    "html": "languages",
    "css3": "languages",
    "css": "languages",
    "sql": "languages",
    "go": "languages",
    "golang": "languages",
    "c++": "languages",
    "c#": "languages",
    "java": "languages",
    "ruby": "languages",
    "rust": "languages",
    "php": "languages",
    "swift": "languages",
    "kotlin": "languages",
    "scala": "languages",
    "r": "languages",
    "shell": "languages",
    "bash": "languages",

    # ai_ml
    "llms": "ai_ml",
    "large language models": "ai_ml",
    "gemini": "ai_ml",
    "gpt": "ai_ml",
    "llama": "ai_ml",
    "claude": "ai_ml",
    "langchain": "ai_ml",
    "llamaindex": "ai_ml",
    "crewai": "ai_ml",
    "autogen": "ai_ml",
    "rag": "ai_ml",
    "retrieval-augmented generation": "ai_ml",
    "prompt engineering": "ai_ml",
    "computer vision": "ai_ml",
    "nlp": "ai_ml",
    "natural language processing": "ai_ml",
    "pytorch": "ai_ml",
    "tensorflow": "ai_ml",
    "scikit-learn": "ai_ml",
    "sklearn": "ai_ml",
    "keras": "ai_ml",
    "pandas": "ai_ml",
    "numpy": "ai_ml",
    "opencv": "ai_ml",
    "yolo": "ai_ml",
    "yolov8": "ai_ml",
    "huggingface": "ai_ml",
    "transformers": "ai_ml",
    "deep learning": "ai_ml",
    "machine learning": "ai_ml",
    "ml": "ai_ml",
    "generative ai": "ai_ml",
    "vertex ai": "ai_ml",
    "spacy": "ai_ml",
    "nltk": "ai_ml",

    # backend
    "fastapi": "backend",
    "flask": "backend",
    "django": "backend",
    "node.js": "backend",
    "nodejs": "backend",
    "express": "backend",
    "express.js": "backend",
    "nestjs": "backend",
    "spring": "backend",
    "spring boot": "backend",
    "ruby on rails": "backend",
    "rails": "backend",
    "asp.net": "backend",
    "graphql": "backend",
    "rest apis": "backend",
    "rest api": "backend",
    "grpc": "backend",
    "microservices": "backend",
    "apis": "backend",
    "api": "backend",

    # frontend
    "react": "frontend",
    "react.js": "frontend",
    "reactjs": "frontend",
    "angular": "frontend",
    "vue": "frontend",
    "vue.js": "frontend",
    "vuejs": "frontend",
    "next.js": "frontend",
    "nextjs": "frontend",
    "svelte": "frontend",
    "tailwind": "frontend",
    "tailwindcss": "frontend",
    "bootstrap": "frontend",
    "jquery": "frontend",
    "sass": "frontend",
    "streamlit": "frontend",
    "vite": "frontend",
    "webpack": "frontend",

    # databases_cloud
    "postgresql": "databases_cloud",
    "postgres": "databases_cloud",
    "mysql": "databases_cloud",
    "mongodb": "databases_cloud",
    "redis": "databases_cloud",
    "dynamodb": "databases_cloud",
    "sqlite": "databases_cloud",
    "cassandra": "databases_cloud",
    "elasticsearch": "databases_cloud",
    "aws": "databases_cloud",
    "gcp": "databases_cloud",
    "azure": "databases_cloud",
    "google cloud": "databases_cloud",
    "google cloud platform": "databases_cloud",
    "amazon web services": "databases_cloud",
    "kubernetes": "databases_cloud",
    "k8s": "databases_cloud",
    "docker": "databases_cloud",
    "terraform": "databases_cloud",
    "ansible": "databases_cloud",
    "jenkins": "databases_cloud",
    "github actions": "databases_cloud",
    "pyspark": "databases_cloud",
    "spark": "databases_cloud",
    "hadoop": "databases_cloud",
    "pinecone": "databases_cloud",
    "chroma": "databases_cloud",
    "chromadb": "databases_cloud",
    "vector databases": "databases_cloud",
    "vector database": "databases_cloud",
    "cloud deployment": "databases_cloud",

    # tools
    "git": "tools",
    "github": "tools",
    "gitlab": "tools",
    "jira": "tools",
    "confluence": "tools",
    "cursor": "tools",
    "vscode": "tools",
    "vs code": "tools",
    "pydantic": "tools",
    "postman": "tools",
    "npm": "tools",
    "pip": "tools",
    "poetry": "tools",
    "eslint": "tools",
}

PREFERRED_SKILL_CASING = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ts": "TypeScript",
    "html5": "HTML5",
    "html": "HTML5",
    "css3": "CSS3",
    "css": "CSS3",
    "sql": "SQL",
    "go": "Go",
    "golang": "Go",
    "c++": "C++",
    "c#": "C#",
    "java": "Java",
    "ruby": "Ruby",
    "rust": "Rust",
    "php": "PHP",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "r": "R",
    "bash": "Bash",
    "shell": "Shell Scripting",

    "llms": "LLMs",
    "large language models": "LLMs",
    "gemini": "Gemini",
    "gpt": "GPT",
    "llama": "Llama",
    "claude": "Claude",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "crewai": "CrewAI",
    "autogen": "AutoGen",
    "rag": "RAG",
    "retrieval-augmented generation": "RAG",
    "prompt engineering": "Prompt Engineering",
    "computer vision": "Computer Vision",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "keras": "Keras",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "opencv": "OpenCV",
    "yolo": "YOLO",
    "yolov8": "YOLOv8",
    "huggingface": "HuggingFace",
    "transformers": "Transformers",
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "generative ai": "Generative AI",
    "vertex ai": "Vertex AI",
    "spacy": "spaCy",
    "nltk": "NLTK",

    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express.js",
    "express.js": "Express.js",
    "nestjs": "NestJS",
    "spring": "Spring",
    "spring boot": "Spring Boot",
    "ruby on rails": "Ruby on Rails",
    "rails": "Ruby on Rails",
    "asp.net": "ASP.NET",
    "graphql": "GraphQL",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "grpc": "gRPC",
    "microservices": "Microservices",

    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "angular": "Angular",
    "vue": "Vue",
    "vue.js": "Vue",
    "vuejs": "Vue",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "svelte": "Svelte",
    "tailwind": "Tailwind",
    "tailwindcss": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "jquery": "jQuery",
    "sass": "Sass",
    "streamlit": "Streamlit",
    "vite": "Vite",
    "webpack": "Webpack",

    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "dynamodb": "DynamoDB",
    "sqlite": "SQLite",
    "cassandra": "Cassandra",
    "elasticsearch": "Elasticsearch",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "amazon web services": "AWS",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "docker": "Docker",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    "pyspark": "PySpark",
    "spark": "Spark",
    "hadoop": "Hadoop",
    "pinecone": "Pinecone",
    "chroma": "ChromaDB",
    "chromadb": "ChromaDB",
    "vector databases": "Vector Databases",
    "vector database": "Vector Databases",
    "cloud deployment": "Cloud Deployment",

    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "jira": "Jira",
    "confluence": "Confluence",
    "cursor": "Cursor",
    "vscode": "VS Code",
    "vs code": "VS Code",
    "pydantic": "Pydantic",
    "postman": "Postman",
    "npm": "npm",
    "pip": "pip",
    "poetry": "Poetry",
    "eslint": "ESLint",
}


def determine_skills_to_add(
    base_skills: dict[str, list[str]],
    selected_keywords: list[str]
) -> dict[str, list[str]]:
    """
    Identifies selected keywords that are not present in the candidate's base skills
    but map to known categories, and returns them structured by category.
    """
    existing_skills_lower = set()
    for skill_list in base_skills.values():
        for skill in skill_list:
            existing_skills_lower.add(skill.lower())

    skills_to_add = {}

    for kw in selected_keywords:
        kw_clean = kw.strip()
        kw_lower = kw_clean.lower()

        if kw_lower in SKILL_TO_CATEGORY and kw_lower not in existing_skills_lower:
            category = SKILL_TO_CATEGORY[kw_lower]
            presentation_name = PREFERRED_SKILL_CASING.get(kw_lower, kw_clean)

            if category not in skills_to_add:
                skills_to_add[category] = []
            
            if presentation_name not in skills_to_add[category]:
                skills_to_add[category].append(presentation_name)

    return skills_to_add


CATEGORY_KEYWORDS = {
    "languages": [
        "python", "typescript", "javascript", "js", "ts", "html5", "html", "css3", "css", "sql",
        "go", "golang", "c++", "c#", "java", "ruby", "rust", "php", "swift", "kotlin", "scala", "r", "bash", "shell"
    ],
    "ai_ml": [
        "llm", "large language model", "gemini", "gpt", "llama", "claude", "langchain", "llamaindex", "crewai", "autogen",
        "rag", "retrieval-augmented generation", "prompt engineering", "computer vision", "nlp", "natural language processing",
        "pytorch", "tensorflow", "scikit-learn", "sklearn", "keras", "pandas", "numpy", "opencv", "yolo", "yolov8",
        "huggingface", "transformers", "deep learning", "machine learning", "ml", "generative ai", "vertex ai", "spacy", "nltk",
        "artificial intelligence", "neural network", "agent"
    ],
    "backend": [
        "fastapi", "flask", "django", "node.js", "nodejs", "express", "express.js", "nestjs", "spring", "spring boot",
        "ruby on rails", "rails", "asp.net", "graphql", "rest apis", "rest api", "grpc", "microservices", "api", "apis", "backend"
    ],
    "frontend": [
        "react", "react.js", "reactjs", "angular", "vue", "vue.js", "vuejs", "next.js", "nextjs", "svelte", "tailwind",
        "tailwindcss", "bootstrap", "jquery", "sass", "streamlit", "vite", "webpack", "frontend", "ui", "ux", "html", "css"
    ],
    "databases_cloud": [
        "postgresql", "postgres", "mysql", "mongodb", "redis", "dynamodb", "sqlite", "cassandra", "elasticsearch", "aws", "gcp",
        "azure", "google cloud", "google cloud platform", "amazon web services", "kubernetes", "k8s", "docker", "terraform",
        "ansible", "jenkins", "github actions", "pyspark", "spark", "hadoop", "pinecone", "chroma", "chromadb", "vector databases",
        "vector database", "cloud deployment", "database", "databases", "cloud"
    ],
    "tools": [
        "git", "github", "gitlab", "jira", "confluence", "cursor", "vscode", "vs code", "pydantic", "postman", "npm", "pip",
        "poetry", "eslint", "tool", "tools"
    ]
}


def determine_skills_to_show(job_description: str, selected_keywords: list[str]) -> list[str]:
    """
    Determines which skill categories should be shown on the resume based on the
    job description text and selected keywords.
    """
    jd_lower = job_description.lower()
    skills_to_show = ["languages"]
    categories_to_check = ["ai_ml", "backend", "frontend", "databases_cloud", "tools"]
    
    for category in categories_to_check:
        # Check if any selected keyword maps to this category
        has_keyword_match = False
        for kw in selected_keywords:
            if SKILL_TO_CATEGORY.get(kw.lower()) == category:
                has_keyword_match = True
                break
                
        if has_keyword_match:
            skills_to_show.append(category)
            continue
            
        # Check if the job description mentions any keyword from this category
        has_jd_match = False
        for term in CATEGORY_KEYWORDS.get(category, []):
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, jd_lower):
                has_jd_match = True
                break
                
        if has_jd_match:
            skills_to_show.append(category)
            
    return skills_to_show


# ---------------------------------------------------------------------------
# 1. Keyword extraction — Groq (free tier)
# ---------------------------------------------------------------------------

_KEYWORD_EXTRACTION_SYSTEM = """\
You are an expert ATS (Applicant Tracking System) analyst and technical recruiter.
Your job is to analyze job descriptions and extract structured keyword data that
a candidate can use to tailor their resume for maximum ATS compatibility.

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation.
"""

_KEYWORD_EXTRACTION_SCHEMA = {
    "hard_skills": ["list of specific technical skills, e.g. Python, Kubernetes, SQL"],
    "soft_skills": ["list of soft skills mentioned explicitly, e.g. leadership, communication"],
    "tools_and_technologies": ["specific tools, frameworks, platforms, e.g. dbt, Terraform, React"],
    "job_titles": ["related job titles or seniority levels mentioned"],
    "certifications": ["certs or degrees the JD mentions or implies"],
    "priority_keywords": ["top 10 must-have keywords ranked by emphasis in the JD"],
}


def extract_keywords(job_description: str) -> KeywordExtractionResult:
    user_prompt = f"""\
Analyze the following job description and extract keywords.

Return a JSON object that matches this schema exactly:
{json.dumps(_KEYWORD_EXTRACTION_SCHEMA, indent=2)}

JOB DESCRIPTION:
{job_description}
"""
    raw = _call_groq(_KEYWORD_EXTRACTION_SYSTEM, user_prompt)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Groq returned non-JSON for keyword extraction: {exc}\n\nRaw:\n{raw}") from exc

    return KeywordExtractionResult(
        hard_skills=parsed.get("hard_skills", []),
        soft_skills=parsed.get("soft_skills", []),
        tools_and_technologies=parsed.get("tools_and_technologies", []),
        job_titles=parsed.get("job_titles", []),
        certifications=parsed.get("certifications", []),
        priority_keywords=parsed.get("priority_keywords", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# 2. Resume tailoring — Claude Haiku
# ---------------------------------------------------------------------------

_TAILORING_SYSTEM = """\
You are an expert resume writer with deep experience tailoring resumes across technical, clinical, and administrative roles.
You rewrite resume bullets to emphasize relevance to a specific job description while:
  - Preserving all factual accuracy (never invent metrics or experiences)
  - Keeping bullets concise (1–2 lines, action-verb first)
  - Naturally weaving in the provided keywords
  - Maintaining strong impact framing (STAR-adjacent: action → scale → result)
  - Never using em-dashes (—) or en-dashes (–) anywhere in the output; use commas, colons, or rephrase instead

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation.
"""


def tailor_resume(
    base_resume: dict,
    job_description: str,
    selected_keywords: list[str],
) -> TailoredResume:
    resume_payload = {
        "summary": base_resume.get("summary", ""),
        "skills": base_resume.get("skills", {}),
        "experience": [
            {
                "company": exp.get("company"),
                "title": exp.get("title"),
                "bullets": [b.get("text") for b in exp.get("bullets", [])],
            }
            for exp in base_resume.get("experience", [])
        ],
        "projects": [
            {
                "name": proj.get("name"),
                "bullets": [b.get("text") for b in proj.get("bullets", [])],
            }
            for proj in base_resume.get("projects", [])
        ],
    }

    response_schema = {
        "summary": "A 2–3 sentence targeted professional summary for this specific role",
        "experiences": [
            {
                "company": "string",
                "title": "string",
                "tailored_bullets": [
                    {
                        "original": "exact original bullet text",
                        "tailored": "rewritten bullet",
                        "keywords_injected": ["keyword1", "keyword2"],
                    }
                ],
            }
        ],
        "projects": [
            {
                "name": "string",
                "tailored_bullets": [
                    {
                        "original": "exact original bullet text",
                        "tailored": "rewritten bullet",
                        "keywords_injected": ["keyword1", "keyword2"],
                    }
                ],
            }
        ],
        "skills_to_highlight": ["skills from the candidate's profile most relevant to this JD"],
        "skills_to_show": ["category_key1", "category_key2", "category_key3"],
    }

    user_prompt = f"""\
Tailor the following resume for the job description below.

KEYWORDS TO INCORPORATE (selected by the candidate):
{json.dumps(selected_keywords, indent=2)}

BASE RESUME DATA:
{json.dumps(resume_payload, indent=2)}

JOB DESCRIPTION:
{job_description}

Return a JSON object matching this schema exactly:
{json.dumps(response_schema, indent=2)}

Rules:
- Only rewrite bullets where adding keywords genuinely improves relevance.
- Never fabricate metrics, technologies, or experiences.
- Never add credentials, licenses, or certifications the candidate does not already have in their profile (e.g. do not add RN, MD, PMP, or any license not listed in the certifications section).
- Preserve the candidate's voice — do not over-polish into generic corporate speak.
- Every tailored bullet must start with a strong past-tense action verb.
- If the resume has projects, use exactly 3 bullets for the experience role. If the resume has no projects, use exactly 5 bullets for the first two roles and exactly 4 bullets for the third (oldest) role.
- If the resume has projects, use exactly 3 bullets for the experience role and never fabricate bullets to reach a higher count.
- Keep the same number of bullets per project as in the original — do not add or remove project bullets.
- Never remove quantified metrics (percentages, numbers, counts) from any bullet.
- For project bullets: only append keywords to the END of the original bullet text where natural. Never rewrite, restructure, or remove any part of the original. If a keyword cannot be appended naturally, leave the bullet unchanged.
- Never use fewer bullets than specified — a short resume wastes space.
- Set skills_to_show to the skill category keys most relevant to this JD. For AI/ML roles include ai_ml. For pure backend/fullstack roles omit ai_ml. Always include languages, backend, frontend, databases_cloud, and tools unless irrelevant. Use the exact category key names from the skills object.
"""
    raw = _call_claude(_TAILORING_SYSTEM, user_prompt, max_tokens=CLAUDE_MAX_TOKENS)

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON for resume tailoring: {exc}\n\nRaw:\n{raw}") from exc

    experiences = [
        TailoredExperience(
            company=exp["company"],
            title=exp["title"],
            tailored_bullets=[
                TailoredBullet(
                    original=b.get("original", ""),
                    tailored=limit_character_count(b.get("tailored", "")),
                    keywords_injected=validate_keywords_in_text(
                        b.get("tailored", ""), selected_keywords
                    ),
                )
                for b in exp.get("tailored_bullets", [])
            ],
        )
        for exp in parsed.get("experiences", [])
    ]

    projects = [
        TailoredProject(
            name=proj["name"],
            tailored_bullets=[
                TailoredBullet(
                    original=b.get("original", ""),
                    tailored=limit_character_count(b.get("tailored", "")),
                    keywords_injected=validate_keywords_in_text(
                        b.get("tailored", ""), selected_keywords
                    ),
                )
                for b in proj.get("tailored_bullets", [])
            ],
        )
        for proj in parsed.get("projects", [])
    ]

    return TailoredResume(
        summary=parsed.get("summary", ""),
        experiences=experiences,
        projects=projects,
        skills_to_highlight=parsed.get("skills_to_highlight", []),
        skills_to_add=determine_skills_to_add(base_resume.get("skills", {}), selected_keywords),
        skills_to_show=parsed.get("skills_to_show", []),
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# 3. ATS scoring — heuristic (no API call)
# ---------------------------------------------------------------------------

def score_resume(
    tailored_resume: dict,
    job_description: str,
    selected_keywords: list[str] | None = None,
) -> ATSScoreResult:
    """
    Heuristic ATS scoring — fast, free, deterministic.

    Strategy:
    - Flatten all resume text into a searchable corpus
    - Check each selected keyword against the corpus
    - Score = matched / total * 100
    - Generate actionable suggestions based on gap patterns
    """
    selected_keywords = selected_keywords or []

    # ── Build resume text corpus ──────────────────────────────────────────
    corpus_parts = []

    # Summary
    corpus_parts.append(tailored_resume.get("tailored_summary", ""))

    # Skills
    for skill_list in tailored_resume.get("skills", {}).values():
        if isinstance(skill_list, list):
            corpus_parts.extend(skill_list)

    # Experience bullets
    for exp in tailored_resume.get("experience", []):
        corpus_parts.append(exp.get("title", ""))
        for bullet in exp.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    # Projects
    for proj in tailored_resume.get("projects", []):
        corpus_parts.append(proj.get("name", ""))
        for bullet in proj.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    # Certifications
    for cert in tailored_resume.get("certifications", []):
        corpus_parts.append(cert.get("name", ""))
        corpus_parts.append(cert.get("issuer", ""))

    corpus = _normalize(" ".join(corpus_parts))

    # ── Match keywords ────────────────────────────────────────────────────
    matched = []
    missing = []

    for kw in selected_keywords:
        kw_normalized = _normalize(kw)
        # Check if all words in the keyword appear in the corpus
        kw_words = kw_normalized.split()
        if all(word in corpus for word in kw_words):
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(selected_keywords)
    coverage = len(matched) / total if total > 0 else 0.0

    # ── Score calculation ─────────────────────────────────────────────────
    # Base score from keyword coverage (70% weight)
    # Bonus points for having summary, multiple experiences, certifications (30% weight)
    base_score = coverage * 70

    bonus = 0
    if tailored_resume.get("tailored_summary"):
        bonus += 10
    if len(tailored_resume.get("experience", [])) >= 2:
        bonus += 10
    if tailored_resume.get("certifications"):
        bonus += 10

    overall_score = min(100, int(base_score + bonus))

    # ── Generate suggestions ──────────────────────────────────────────────
    suggestions = []

    if missing:
        top_missing = missing[:3]
        suggestions.append(
            f"Add these missing keywords to your resume: {', '.join(top_missing)}."
        )

    if coverage < 0.6:
        suggestions.append(
            "Keyword coverage is below 60%. Select more relevant keywords and regenerate."
        )

    if not tailored_resume.get("tailored_summary"):
        suggestions.append("Add a targeted summary section to improve ATS matching.")

    skill_count = sum(
        len(v) for v in tailored_resume.get("skills", {}).values()
        if isinstance(v, list)
    )
    if skill_count < 10:
        suggestions.append(
            "Expand your skills section — more relevant skills improve ATS keyword density."
        )

    if len(missing) > len(matched):
        suggestions.append(
            "More than half your target keywords are missing. Consider selecting fewer, "
            "more relevant keywords or tailoring to a closer-match role."
        )

    # Always give at least one suggestion
    if not suggestions:
        suggestions.append(
            "Strong keyword match. Review the missing keywords above and add any you genuinely have."
        )

    return ATSScoreResult(
        overall_score=overall_score,
        keyword_coverage=round(coverage, 2),
        matched_keywords=matched,
        missing_keywords=missing,
        suggestions=suggestions[:5],
        raw_response="heuristic",
    )


# ---------------------------------------------------------------------------
# Quick smoke test (run directly: python claude_service.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_jd = """\
    We are looking for a Senior ML Engineer to join our AI Platform team.
    You will design and deploy large-scale machine learning pipelines using Python,
    PyTorch, and Kubernetes. Experience with MLflow, dbt, and AWS SageMaker is a plus.
    Strong communication skills and the ability to lead cross-functional initiatives required.
    """

    print("--- Keyword Extraction (Groq) ---")
    kw_result = extract_keywords(sample_jd)
    print(json.dumps(kw_result.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- Resume Tailoring (Claude Haiku) ---")
    stub_resume = {
        "summary": "Software engineer with 5 years of experience in ML systems.",
        "skills": {"languages": ["Python", "SQL"], "ai_ml": ["PyTorch", "scikit-learn"]},
        "experience": [
            {
                "company": "Acme Corp",
                "title": "ML Engineer",
                "bullets": [
                    {"text": "Built training pipelines that reduced model iteration time by 40%."},
                    {"text": "Collaborated with product teams to ship recommendation features."},
                ],
            }
        ],
        "projects": [],
    }
    tailored = tailor_resume(stub_resume, sample_jd, kw_result.priority_keywords)
    print(json.dumps(tailored.model_dump(exclude={"raw_response"}), indent=2))

    print("\n--- ATS Score (Heuristic) ---")
    score = score_resume(
        tailored.model_dump(exclude={"raw_response"}),
        sample_jd,
        kw_result.priority_keywords,
    )
    print(json.dumps(score.model_dump(exclude={"raw_response"}), indent=2))