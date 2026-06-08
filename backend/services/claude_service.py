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


# ---------------------------------------------------------------------------
# Skill category mapping helpers
# ---------------------------------------------------------------------------

# Standard tech category keys — used to detect non-tech (admin/clinical) resumes
STANDARD_TECH_CATEGORIES = {"languages", "ai_ml", "backend", "frontend", "databases_cloud", "tools"}

SKILL_TO_CATEGORY = {
    # languages
    "python": "languages", "typescript": "languages", "javascript": "languages",
    "js": "languages", "ts": "languages", "html5": "languages", "html": "languages",
    "css3": "languages", "css": "languages", "sql": "languages", "go": "languages",
    "golang": "languages", "c++": "languages", "c#": "languages", "java": "languages",
    "ruby": "languages", "rust": "languages", "php": "languages", "swift": "languages",
    "kotlin": "languages", "scala": "languages", "r": "languages", "shell": "languages",
    "bash": "languages",

    # ai_ml
    "llms": "ai_ml", "large language models": "ai_ml", "gemini": "ai_ml", "gpt": "ai_ml",
    "llama": "ai_ml", "claude": "ai_ml", "langchain": "ai_ml", "llamaindex": "ai_ml",
    "crewai": "ai_ml", "autogen": "ai_ml", "rag": "ai_ml",
    "retrieval-augmented generation": "ai_ml", "prompt engineering": "ai_ml",
    "computer vision": "ai_ml", "nlp": "ai_ml", "natural language processing": "ai_ml",
    "pytorch": "ai_ml", "tensorflow": "ai_ml", "scikit-learn": "ai_ml", "sklearn": "ai_ml",
    "keras": "ai_ml", "pandas": "ai_ml", "numpy": "ai_ml", "opencv": "ai_ml",
    "yolo": "ai_ml", "yolov8": "ai_ml", "huggingface": "ai_ml", "transformers": "ai_ml",
    "deep learning": "ai_ml", "machine learning": "ai_ml", "ml": "ai_ml",
    "generative ai": "ai_ml", "vertex ai": "ai_ml", "spacy": "ai_ml", "nltk": "ai_ml",

    # backend
    "fastapi": "backend", "flask": "backend", "django": "backend", "node.js": "backend",
    "nodejs": "backend", "express": "backend", "express.js": "backend", "nestjs": "backend",
    "spring": "backend", "spring boot": "backend", "ruby on rails": "backend",
    "rails": "backend", "asp.net": "backend", "graphql": "backend",
    "rest apis": "backend", "rest api": "backend", "grpc": "backend",
    "microservices": "backend", "apis": "backend", "api": "backend",

    # frontend
    "react": "frontend", "react.js": "frontend", "reactjs": "frontend",
    "angular": "frontend", "vue": "frontend", "vue.js": "frontend", "vuejs": "frontend",
    "next.js": "frontend", "nextjs": "frontend", "svelte": "frontend",
    "tailwind": "frontend", "tailwindcss": "frontend", "bootstrap": "frontend",
    "jquery": "frontend", "sass": "frontend", "streamlit": "frontend",
    "vite": "frontend", "webpack": "frontend",

    # databases_cloud
    "postgresql": "databases_cloud", "postgres": "databases_cloud", "mysql": "databases_cloud",
    "mongodb": "databases_cloud", "redis": "databases_cloud", "dynamodb": "databases_cloud",
    "sqlite": "databases_cloud", "cassandra": "databases_cloud",
    "elasticsearch": "databases_cloud", "aws": "databases_cloud", "gcp": "databases_cloud",
    "azure": "databases_cloud", "google cloud": "databases_cloud",
    "google cloud platform": "databases_cloud", "amazon web services": "databases_cloud",
    "kubernetes": "databases_cloud", "k8s": "databases_cloud", "docker": "databases_cloud",
    "terraform": "databases_cloud", "ansible": "databases_cloud", "jenkins": "databases_cloud",
    "github actions": "databases_cloud", "pyspark": "databases_cloud", "spark": "databases_cloud",
    "hadoop": "databases_cloud", "pinecone": "databases_cloud", "chroma": "databases_cloud",
    "chromadb": "databases_cloud", "vector databases": "databases_cloud",
    "vector database": "databases_cloud", "cloud deployment": "databases_cloud",

    # tools
    "git": "tools", "github": "tools", "gitlab": "tools", "jira": "tools",
    "confluence": "tools", "cursor": "tools", "vscode": "tools", "vs code": "tools",
    "pydantic": "tools", "postman": "tools", "npm": "tools", "pip": "tools",
    "poetry": "tools", "eslint": "tools",

    # clinical_research
    "clinical trials": "clinical_research", "clinical trial": "clinical_research",
    "good clinical practice": "clinical_research", "gcp guidelines": "clinical_research",
    "ich guidelines": "clinical_research", "ich e6": "clinical_research",
    "irb": "clinical_research", "institutional review board": "clinical_research",
    "fda regulations": "clinical_research", "21 cfr": "clinical_research",
    "21 cfr part 11": "clinical_research", "ind": "clinical_research",
    "nda": "clinical_research", "bla": "clinical_research",
    "protocol development": "clinical_research", "protocol deviation": "clinical_research",
    "crf": "clinical_research", "case report form": "clinical_research",
    "edc": "clinical_research", "electronic data capture": "clinical_research",
    "adverse event reporting": "clinical_research", "adverse events": "clinical_research",
    "pharmacovigilance": "clinical_research", "drug safety": "clinical_research",
    "informed consent": "clinical_research", "econsent": "clinical_research",
    "clinical monitoring": "clinical_research", "source data verification": "clinical_research",
    "sdv": "clinical_research", "risk-based monitoring": "clinical_research",
    "ctms": "clinical_research", "clinical trial management system": "clinical_research",
    "cdisc": "clinical_research", "cdash": "clinical_research", "sdtm": "clinical_research",
    "adam": "clinical_research", "clinical data management": "clinical_research",
    "redcap": "clinical_research", "medidata rave": "clinical_research",
    "medidata": "clinical_research", "rave": "clinical_research",
    "veeva vault": "clinical_research", "oracle clinical": "clinical_research",
    "openclinica": "clinical_research",
    "medical writing": "clinical_research", "clinical study report": "clinical_research",
    "regulatory submissions": "clinical_research", "regulatory affairs": "clinical_research",
    "gmp": "clinical_research", "good manufacturing practice": "clinical_research",
    "glp": "clinical_research", "good laboratory practice": "clinical_research",
    "sops": "clinical_research", "standard operating procedures": "clinical_research",
    "clinical operations": "clinical_research", "site management": "clinical_research",
    "patient recruitment": "clinical_research", "subject recruitment": "clinical_research",
    "tmf": "clinical_research", "trial master file": "clinical_research",
    "dsmb": "clinical_research", "data safety monitoring": "clinical_research",
    "biostatistics": "clinical_research", "clinical research associate": "clinical_research",
    "cra": "clinical_research", "clinical research coordinator": "clinical_research",
    "crc": "clinical_research", "phase i": "clinical_research", "phase ii": "clinical_research",
    "phase iii": "clinical_research", "phase iv": "clinical_research",
    "cro": "clinical_research", "contract research organization": "clinical_research",
    "data integrity": "clinical_research", "post-market surveillance": "clinical_research",

    # administrative
    "microsoft office": "administrative", "microsoft office suite": "administrative",
    "ms office": "administrative", "word": "administrative", "microsoft word": "administrative",
    "excel": "administrative", "microsoft excel": "administrative",
    "powerpoint": "administrative", "microsoft powerpoint": "administrative",
    "outlook": "administrative", "microsoft outlook": "administrative",
    "access": "administrative", "microsoft access": "administrative",
    "onenote": "administrative", "microsoft onenote": "administrative",
    "google workspace": "administrative", "g suite": "administrative",
    "google docs": "administrative", "google sheets": "administrative",
    "google slides": "administrative", "google drive": "administrative",
    "google calendar": "administrative",
    "calendar management": "administrative", "scheduling": "administrative",
    "travel coordination": "administrative", "travel arrangements": "administrative",
    "expense reporting": "administrative", "expense management": "administrative",
    "concur": "administrative", "quickbooks": "administrative",
    "accounts payable": "administrative", "accounts receivable": "administrative",
    "invoicing": "administrative", "payroll": "administrative", "budgeting": "administrative",
    "budget management": "administrative", "procurement": "administrative",
    "vendor management": "administrative", "purchase orders": "administrative",
    "sharepoint": "administrative", "microsoft sharepoint": "administrative",
    "workday": "administrative", "adp": "administrative", "kronos": "administrative",
    "hris": "administrative", "hr administration": "administrative",
    "onboarding": "administrative", "offboarding": "administrative",
    "salesforce": "administrative", "hubspot": "administrative", "crm": "administrative",
    "zoom": "administrative", "microsoft teams": "administrative", "slack": "administrative",
    "docusign": "administrative", "adobe acrobat": "administrative", "adobe sign": "administrative",
    "data entry": "administrative", "records management": "administrative",
    "document management": "administrative", "filing systems": "administrative",
    "office management": "administrative", "executive support": "administrative",
    "administrative support": "administrative", "executive assistant": "administrative",
    "meeting coordination": "administrative", "meeting minutes": "administrative",
    "correspondence management": "administrative", "reception": "administrative",
    "front desk": "administrative", "multi-line phone systems": "administrative",
    "supply management": "administrative", "inventory management": "administrative",
    "facilities management": "administrative", "event planning": "administrative",
    "event coordination": "administrative", "project coordination": "administrative",
    "customer service": "administrative", "clerical": "administrative",
    "notary": "administrative", "transcription": "administrative",
}

PREFERRED_SKILL_CASING = {
    "python": "Python", "typescript": "TypeScript", "javascript": "JavaScript",
    "js": "JavaScript", "ts": "TypeScript", "html5": "HTML5", "html": "HTML5",
    "css3": "CSS3", "css": "CSS3", "sql": "SQL", "go": "Go", "golang": "Go",
    "c++": "C++", "c#": "C#", "java": "Java", "ruby": "Ruby", "rust": "Rust",
    "php": "PHP", "swift": "Swift", "kotlin": "Kotlin", "scala": "Scala",
    "r": "R", "bash": "Bash", "shell": "Shell Scripting",
    "llms": "LLMs", "large language models": "LLMs", "gemini": "Gemini", "gpt": "GPT",
    "llama": "Llama", "claude": "Claude", "langchain": "LangChain",
    "llamaindex": "LlamaIndex", "crewai": "CrewAI", "autogen": "AutoGen", "rag": "RAG",
    "retrieval-augmented generation": "RAG", "prompt engineering": "Prompt Engineering",
    "computer vision": "Computer Vision", "nlp": "NLP",
    "natural language processing": "NLP", "pytorch": "PyTorch",
    "tensorflow": "TensorFlow", "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "keras": "Keras", "pandas": "Pandas", "numpy": "NumPy", "opencv": "OpenCV",
    "yolo": "YOLO", "yolov8": "YOLOv8", "huggingface": "HuggingFace",
    "transformers": "Transformers", "deep learning": "Deep Learning",
    "machine learning": "Machine Learning", "ml": "Machine Learning",
    "generative ai": "Generative AI", "vertex ai": "Vertex AI", "spacy": "spaCy",
    "nltk": "NLTK", "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "node.js": "Node.js", "nodejs": "Node.js", "express": "Express.js",
    "express.js": "Express.js", "nestjs": "NestJS", "spring": "Spring",
    "spring boot": "Spring Boot", "ruby on rails": "Ruby on Rails", "rails": "Ruby on Rails",
    "asp.net": "ASP.NET", "graphql": "GraphQL", "rest apis": "REST APIs",
    "rest api": "REST APIs", "grpc": "gRPC", "microservices": "Microservices",
    "react": "React", "react.js": "React", "reactjs": "React", "angular": "Angular",
    "vue": "Vue", "vue.js": "Vue", "vuejs": "Vue", "next.js": "Next.js",
    "nextjs": "Next.js", "svelte": "Svelte", "tailwind": "Tailwind",
    "tailwindcss": "Tailwind CSS", "bootstrap": "Bootstrap", "jquery": "jQuery",
    "sass": "Sass", "streamlit": "Streamlit", "vite": "Vite", "webpack": "Webpack",
    "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mysql": "MySQL",
    "mongodb": "MongoDB", "redis": "Redis", "dynamodb": "DynamoDB", "sqlite": "SQLite",
    "cassandra": "Cassandra", "elasticsearch": "Elasticsearch", "aws": "AWS",
    "gcp": "GCP", "azure": "Azure", "google cloud": "GCP",
    "google cloud platform": "GCP", "amazon web services": "AWS",
    "kubernetes": "Kubernetes", "k8s": "Kubernetes", "docker": "Docker",
    "terraform": "Terraform", "ansible": "Ansible", "jenkins": "Jenkins",
    "github actions": "GitHub Actions", "pyspark": "PySpark", "spark": "Spark",
    "hadoop": "Hadoop", "pinecone": "Pinecone", "chroma": "ChromaDB",
    "chromadb": "ChromaDB", "vector databases": "Vector Databases",
    "vector database": "Vector Databases", "cloud deployment": "Cloud Deployment",
    "git": "Git", "github": "GitHub", "gitlab": "GitLab", "jira": "Jira",
    "confluence": "Confluence", "cursor": "Cursor", "vscode": "VS Code",
    "vs code": "VS Code", "pydantic": "Pydantic", "postman": "Postman",
    "npm": "npm", "pip": "pip", "poetry": "Poetry", "eslint": "ESLint",
    # clinical_research
    "clinical trials": "Clinical Trials", "clinical trial": "Clinical Trials",
    "good clinical practice": "GCP (Good Clinical Practice)",
    "gcp guidelines": "GCP (Good Clinical Practice)", "ich guidelines": "ICH Guidelines",
    "ich e6": "ICH E6", "irb": "IRB", "institutional review board": "IRB",
    "fda regulations": "FDA Regulations", "21 cfr": "21 CFR",
    "21 cfr part 11": "21 CFR Part 11", "ind": "IND", "nda": "NDA", "bla": "BLA",
    "protocol development": "Protocol Development", "protocol deviation": "Protocol Deviation",
    "crf": "CRF", "case report form": "CRF", "edc": "EDC",
    "electronic data capture": "EDC", "adverse event reporting": "Adverse Event Reporting",
    "adverse events": "Adverse Events", "pharmacovigilance": "Pharmacovigilance",
    "drug safety": "Drug Safety", "informed consent": "Informed Consent",
    "econsent": "eConsent", "clinical monitoring": "Clinical Monitoring",
    "source data verification": "SDV", "sdv": "SDV",
    "risk-based monitoring": "Risk-Based Monitoring", "ctms": "CTMS",
    "clinical trial management system": "CTMS", "cdisc": "CDISC", "cdash": "CDASH",
    "sdtm": "SDTM", "adam": "ADaM", "clinical data management": "Clinical Data Management",
    "redcap": "REDCap", "medidata rave": "Medidata Rave", "medidata": "Medidata",
    "rave": "Medidata Rave", "veeva vault": "Veeva Vault",
    "oracle clinical": "Oracle Clinical", "openclinica": "OpenClinica",
    "medical writing": "Medical Writing", "clinical study report": "Clinical Study Report",
    "regulatory submissions": "Regulatory Submissions",
    "regulatory affairs": "Regulatory Affairs", "gmp": "GMP",
    "good manufacturing practice": "GMP", "glp": "GLP",
    "good laboratory practice": "GLP", "sops": "SOPs",
    "standard operating procedures": "SOPs", "clinical operations": "Clinical Operations",
    "site management": "Site Management", "patient recruitment": "Patient Recruitment",
    "subject recruitment": "Subject Recruitment", "tmf": "TMF",
    "trial master file": "TMF", "dsmb": "DSMB",
    "data safety monitoring": "Data Safety Monitoring", "biostatistics": "Biostatistics",
    "clinical research associate": "CRA", "cra": "CRA",
    "clinical research coordinator": "CRC", "crc": "CRC",
    "phase i": "Phase I", "phase ii": "Phase II", "phase iii": "Phase III",
    "phase iv": "Phase IV", "cro": "CRO",
    "contract research organization": "CRO", "data integrity": "Data Integrity",
    "post-market surveillance": "Post-Market Surveillance",
    # administrative
    "microsoft office": "Microsoft Office Suite",
    "microsoft office suite": "Microsoft Office Suite",
    "ms office": "Microsoft Office Suite", "word": "Microsoft Word",
    "microsoft word": "Microsoft Word", "excel": "Microsoft Excel",
    "microsoft excel": "Microsoft Excel", "powerpoint": "PowerPoint",
    "microsoft powerpoint": "PowerPoint", "outlook": "Microsoft Outlook",
    "microsoft outlook": "Microsoft Outlook", "access": "Microsoft Access",
    "microsoft access": "Microsoft Access", "onenote": "OneNote",
    "microsoft onenote": "OneNote", "google workspace": "Google Workspace",
    "g suite": "Google Workspace", "google docs": "Google Docs",
    "google sheets": "Google Sheets", "google slides": "Google Slides",
    "google drive": "Google Drive", "google calendar": "Google Calendar",
    "calendar management": "Calendar Management", "scheduling": "Scheduling",
    "travel coordination": "Travel Coordination",
    "travel arrangements": "Travel Arrangements",
    "expense reporting": "Expense Reporting", "expense management": "Expense Management",
    "concur": "Concur", "quickbooks": "QuickBooks",
    "accounts payable": "Accounts Payable", "accounts receivable": "Accounts Receivable",
    "invoicing": "Invoicing", "payroll": "Payroll", "budgeting": "Budgeting",
    "budget management": "Budget Management", "procurement": "Procurement",
    "vendor management": "Vendor Management", "purchase orders": "Purchase Orders",
    "sharepoint": "SharePoint", "microsoft sharepoint": "SharePoint",
    "workday": "Workday", "adp": "ADP", "kronos": "Kronos",
    "hris": "HRIS", "hr administration": "HR Administration",
    "onboarding": "Onboarding", "offboarding": "Offboarding",
    "salesforce": "Salesforce", "hubspot": "HubSpot", "crm": "CRM",
    "zoom": "Zoom", "microsoft teams": "Microsoft Teams", "slack": "Slack",
    "docusign": "DocuSign", "adobe acrobat": "Adobe Acrobat", "adobe sign": "Adobe Sign",
    "data entry": "Data Entry", "records management": "Records Management",
    "document management": "Document Management", "filing systems": "Filing Systems",
    "office management": "Office Management", "executive support": "Executive Support",
    "administrative support": "Administrative Support",
    "executive assistant": "Executive Assistant",
    "meeting coordination": "Meeting Coordination", "meeting minutes": "Meeting Minutes",
    "correspondence management": "Correspondence Management", "reception": "Reception",
    "front desk": "Front Desk", "multi-line phone systems": "Multi-Line Phone Systems",
    "supply management": "Supply Management", "inventory management": "Inventory Management",
    "facilities management": "Facilities Management", "event planning": "Event Planning",
    "event coordination": "Event Coordination", "project coordination": "Project Coordination",
    "customer service": "Customer Service", "clerical": "Clerical",
    "notary": "Notary", "transcription": "Transcription",
}

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
    ],
    "clinical_research": [
        "clinical trial", "clinical trials", "good clinical practice", "gcp guidelines", "ich guidelines", "ich e6",
        "irb", "institutional review board", "fda regulations", "21 cfr", "21 cfr part 11", "ind", "nda", "bla",
        "protocol development", "protocol deviation", "crf", "case report form", "edc", "electronic data capture",
        "adverse event reporting", "adverse events", "pharmacovigilance", "drug safety", "informed consent", "econsent",
        "clinical monitoring", "source data verification", "sdv", "risk-based monitoring",
        "ctms", "clinical trial management system", "cdisc", "cdash", "sdtm", "adam", "clinical data management",
        "redcap", "medidata rave", "medidata", "rave", "veeva vault", "oracle clinical", "openclinica",
        "medical writing", "clinical study report", "regulatory submissions", "regulatory affairs",
        "gmp", "good manufacturing practice", "glp", "good laboratory practice", "sops", "standard operating procedures",
        "clinical operations", "site management", "patient recruitment", "subject recruitment",
        "tmf", "trial master file", "dsmb", "data safety monitoring", "biostatistics",
        "clinical research associate", "cra", "clinical research coordinator", "crc",
        "phase i", "phase ii", "phase iii", "phase iv", "cro", "contract research organization",
        "data integrity", "post-market surveillance", "clinical research"
    ],
    "administrative": [
        "microsoft office", "microsoft office suite", "ms office", "word", "microsoft word",
        "excel", "microsoft excel", "powerpoint", "microsoft powerpoint", "outlook", "microsoft outlook",
        "access", "microsoft access", "onenote", "google workspace", "g suite", "google docs",
        "google sheets", "google slides", "google drive", "google calendar",
        "calendar management", "scheduling", "travel coordination", "travel arrangements",
        "expense reporting", "expense management", "concur", "quickbooks",
        "accounts payable", "accounts receivable", "invoicing", "payroll", "budgeting",
        "budget management", "procurement", "vendor management", "purchase orders",
        "sharepoint", "workday", "adp", "kronos", "hris", "hr administration",
        "onboarding", "offboarding", "salesforce", "hubspot", "crm",
        "zoom", "microsoft teams", "slack", "docusign", "adobe acrobat", "adobe sign",
        "data entry", "records management", "document management", "filing systems",
        "office management", "executive support", "administrative support", "executive assistant",
        "meeting coordination", "meeting minutes", "correspondence management", "reception",
        "front desk", "multi-line phone systems", "supply management", "inventory management",
        "facilities management", "event planning", "event coordination", "project coordination",
        "customer service", "clerical", "notary", "transcription", "administrative"
    ]
}


def determine_skills_to_add(
    base_skills: dict[str, list[str]],
    selected_keywords: list[str]
) -> dict[str, list[str]]:
    """
    Identifies selected keywords not present in base skills that map to known
    categories, and returns them structured by category.
    """
    existing_skills_lower = set()
    for skill_list in base_skills.values():
        for skill in skill_list:
            existing_skills_lower.add(skill.lower())

    skills_to_add: dict[str, list[str]] = {}

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


def determine_skills_to_show(
    job_description: str,
    selected_keywords: list[str],
    base_skills: dict | None = None,
) -> list[str]:
    """
    Determines which skill categories should be shown on the resume.

    For admin/clinical resumes (non-standard category keys), returns all
    existing categories unchanged. For tech resumes, filters by JD relevance.
    """
    # ── Non-tech resume detection ─────────────────────────────────────────
    # If the resume uses categories outside the standard tech set (e.g.
    # "Administrative Operations", "Software Data", "Communication Leadership"),
    # return all of them as-is — the tech filter logic doesn't apply.
    if base_skills:
        resume_cats = set(base_skills.keys())
        if not resume_cats.intersection(STANDARD_TECH_CATEGORIES):
            return list(resume_cats)

    # ── Tech resume logic ─────────────────────────────────────────────────
    jd_lower = job_description.lower()
    skills_to_show = ["languages"]
    categories_to_check = ["ai_ml", "backend", "frontend", "databases_cloud", "tools"]

    for category in categories_to_check:
        has_keyword_match = any(
            SKILL_TO_CATEGORY.get(kw.lower()) == category
            for kw in selected_keywords
        )
        if has_keyword_match:
            skills_to_show.append(category)
            continue

        has_jd_match = any(
            re.search(rf"\b{re.escape(term)}\b", jd_lower)
            for term in CATEGORY_KEYWORDS.get(category, [])
        )
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
- Keep every bullet to a maximum of 165 characters. For project bullets where the original is already near the limit, skip the keyword append rather than truncating.
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
                    tailored=b.get("tailored", ""),
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
                    tailored=b.get("tailored", ""),
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
        skills_to_show=determine_skills_to_show(
            job_description, selected_keywords, base_resume.get("skills", {})
        ),
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
    """
    selected_keywords = selected_keywords or []

    corpus_parts = []
    corpus_parts.append(tailored_resume.get("tailored_summary", ""))

    for skill_list in tailored_resume.get("skills", {}).values():
        if isinstance(skill_list, list):
            corpus_parts.extend(skill_list)

    for exp in tailored_resume.get("experience", []):
        corpus_parts.append(exp.get("title", ""))
        for bullet in exp.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    for proj in tailored_resume.get("projects", []):
        corpus_parts.append(proj.get("name", ""))
        for bullet in proj.get("bullets", []):
            if isinstance(bullet, dict):
                corpus_parts.append(bullet.get("text", ""))
            else:
                corpus_parts.append(str(bullet))

    for cert in tailored_resume.get("certifications", []):
        corpus_parts.append(cert.get("name", ""))
        corpus_parts.append(cert.get("issuer", ""))

    corpus = _normalize(" ".join(corpus_parts))

    matched = []
    missing = []

    for kw in selected_keywords:
        kw_words = _normalize(kw).split()
        if all(word in corpus for word in kw_words):
            matched.append(kw)
        else:
            missing.append(kw)

    total = len(selected_keywords)
    coverage = len(matched) / total if total > 0 else 0.0

    base_score = coverage * 70
    bonus = 0
    if tailored_resume.get("tailored_summary"):
        bonus += 10
    if len(tailored_resume.get("experience", [])) >= 2:
        bonus += 10
    if tailored_resume.get("certifications"):
        bonus += 10

    overall_score = min(100, int(base_score + bonus))

    suggestions = []
    if missing:
        suggestions.append(
            f"Add these missing keywords to your resume: {', '.join(missing[:3])}."
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