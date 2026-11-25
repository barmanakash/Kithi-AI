"""Deterministic skill vocabulary used for evidence-based matching (no AI required)."""
import re

SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust", "Kotlin", "Swift", "PHP",
    "Ruby", "Scala", "SQL", "NoSQL", "HTML", "CSS", "React", "Angular", "Vue.js", "Next.js", "Node.js",
    "Express.js", "Django", "Flask", "FastAPI", "Spring Boot", "Spring", ".NET", "ASP.NET", "Laravel",
    "MongoDB", "PostgreSQL", "MySQL", "SQLite", "Redis", "Elasticsearch", "Kafka", "RabbitMQ", "GraphQL",
    "REST API", "RESTful", "gRPC", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "Ansible",
    "Jenkins", "CI/CD", "Git", "GitHub Actions", "Linux", "Bash", "PowerShell", "Pandas", "NumPy",
    "SciPy", "scikit-learn", "TensorFlow", "PyTorch", "Keras", "Machine Learning", "Deep Learning",
    "NLP", "Computer Vision", "LLM", "LangChain", "LangGraph", "Hugging Face", "OpenCV", "Apache Spark",
    "Hadoop", "Airflow", "Power BI", "Tableau", "Excel", "Data Analysis", "Data Engineering", "ETL",
    "Microservices", "System Design", "Agile", "Scrum", "JIRA", "Selenium", "Playwright", "Cypress",
    "Jest", "Pytest", "JUnit", "Unit Testing", "Redux", "Tailwind CSS", "Material UI", "Bootstrap",
    "Figma", "React Native", "Flutter", "Android", "iOS", "Firebase", "Supabase", "OAuth", "JWT",
    "Postman", "Swagger", "Nginx", "Prometheus", "Grafana", "Celery", "SQLAlchemy", "Hibernate",
    "Maven", "Gradle", "Webpack", "Vite", "jQuery", "WordPress", "Salesforce", "SAP", "Blockchain",
    "Solidity", "Cybersecurity", "Penetration Testing", "DevOps", "SRE", "Product Management", "SEO",
    "Digital Marketing", "Ollama", "MongoDB Atlas", "Prompt Engineering", "RAG",
]

ALIASES = {
    "js": "JavaScript", "ts": "TypeScript", "reactjs": "React", "react.js": "React", "vue": "Vue.js",
    "nodejs": "Node.js", "node": "Node.js", "express": "Express.js", "postgres": "PostgreSQL",
    "k8s": "Kubernetes", "golang": "Go", "mongo": "MongoDB", "pyspark": "Apache Spark",
    "sklearn": "scikit-learn", "ml": "Machine Learning", "dotnet": ".NET", "tailwind": "Tailwind CSS",
    "mui": "Material UI", "amazon web services": "AWS", "google cloud": "GCP", "nextjs": "Next.js",
    "large language model": "LLM", "large language models": "LLM", "natural language processing": "NLP",
}
# Ambiguous English words that must not be treated as skills on their own.
_AMBIGUOUS = {"go", "node", "express", "vue", "spring", "swift", "excel", "rag", "sap"}

_LOOKUP: dict[str, str] = {s.lower(): s for s in SKILLS}
for _alias, _canon in ALIASES.items():
    _LOOKUP[_alias] = _canon

# "go", "rag", "sap", etc. only count in their unambiguous written forms (see ALIASES / case rules below).
_alternatives = sorted(_LOOKUP.keys(), key=len, reverse=True)
_PATTERN = re.compile(
    r"(?<![\w+#])(" + "|".join(re.escape(a) for a in _alternatives) + r")(?![\w+#])", re.IGNORECASE
)
_CASE_SENSITIVE = {"Go", "RAG", "SAP", "Swift", "Excel", "Spring", "Express.js"}


def canonical(skill: str) -> str:
    return _LOOKUP.get(skill.strip().lower(), skill.strip())


def extract_skills(text: str) -> dict[str, str]:
    """Return {canonical skill: evidence snippet} for every known skill found in the text."""
    found: dict[str, str] = {}
    if not text:
        return found
    for match in _PATTERN.finditer(text):
        raw = match.group(1)
        skill = _LOOKUP[raw.lower()]
        if skill in found:
            continue
        # Ambiguous single words must appear capitalised in the text to count.
        if raw.lower() in _AMBIGUOUS and skill in _CASE_SENSITIVE and not raw[:1].isupper():
            continue
        if raw.lower() in {"node", "express", "vue"} and raw.lower() == raw:
            continue
        start, end = max(0, match.start() - 60), min(len(text), match.end() + 60)
        found[skill] = re.sub(r"\s+", " ", text[start:end]).strip()
    return found
