"""Resume Intelligence Agent.

Two parts:
1. A deterministic, transparent health score (every point is backed by evidence).
2. Local-LLM extraction (skills, titles, summary, suggestions), where every extracted skill or
   title must literally appear in the resume text, so the model cannot invent qualifications.

If the local model is unavailable the deterministic part is still returned and the AI error is
reported explicitly. Nothing is ever sent to an external AI service.
"""
import re

from pydantic import BaseModel, Field, field_validator

from app.core.prompt_guard import wrap_untrusted
from app.services.ai_service import AIServiceError, get_ai_service
from app.services.prompts import SYSTEM_BASE, build_resume_extraction_prompt

SECTION_PATTERNS = {
    "summary": r"^\s*(professional\s+)?(summary|profile|objective|about\s+me)\s*:?\s*$",
    "experience": r"^\s*(work\s+|professional\s+)?(experience|employment(\s+history)?|work\s+history|internships?)\s*:?\s*$",
    "education": r"^\s*(education|academic(\s+background)?|qualifications)\s*:?\s*$",
    "skills": r"^\s*(technical\s+)?(skills|core\s+competencies|technologies|tech\s+stack)\s*:?\s*$",
    "projects": r"^\s*(personal\s+|academic\s+)?projects\s*:?\s*$",
}
SECTION_POINTS = {"experience": 10, "education": 8, "skills": 8, "summary": 2, "projects": 2}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")
BULLET_RE = re.compile(r"^\s*[•\-\*–·▪●◦]\s+\S", re.M)
QUANT_RE = re.compile(
    r"\d+(\.\d+)?\s*%|[$₹€£]\s?\d|\b\d+\s*(k|m|x|users|customers|requests|ms|seconds|hours|days|clients|apis?)\b",
    re.I,
)


class ResumeExtraction(BaseModel):
    skills: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    years_experience: float | None = None
    summary: str = ""
    suggestions: list[str] = Field(default_factory=list)

    @field_validator("skills", "job_titles", "suggestions", mode="before")
    @classmethod
    def _coerce_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return [str(v).strip() for v in value if str(v).strip()]

    @field_validator("years_experience", mode="before")
    @classmethod
    def _coerce_years(cls, value):
        if value is None or isinstance(value, (int, float)):
            return value
        match = re.search(r"\d+(\.\d+)?", str(value))
        return float(match.group()) if match else None

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary(cls, value):
        return "" if value is None else str(value)


def heuristic_review(text: str) -> dict:
    lower = text.lower()
    words = len(text.split())
    breakdown: list[dict] = []

    def add(label: str, points: int, maximum: int, evidence: str) -> None:
        breakdown.append({"label": label, "points": points, "max": maximum, "evidence": evidence})

    # Contact details (15)
    has_email = bool(EMAIL_RE.search(text))
    has_phone = bool(PHONE_RE.search(text))
    add("Contact details", (8 if has_email else 0) + (7 if has_phone else 0), 15,
        f"email {'found' if has_email else 'missing'}, phone {'found' if has_phone else 'missing'}")

    # Sections (30)
    found = [name for name, pattern in SECTION_PATTERNS.items() if re.search(pattern, text, re.I | re.M)]
    missing = [name for name in SECTION_PATTERNS if name not in found]
    add("Standard sections", sum(SECTION_POINTS[s] for s in found), 30,
        f"found: {', '.join(found) or 'none'}; missing: {', '.join(missing) or 'none'}")

    # Length (15)
    if 300 <= words <= 900:
        length_points = 15
    elif 200 <= words < 300 or 900 < words <= 1200:
        length_points = 9
    else:
        length_points = 4
    add("Length", length_points, 15, f"{words} words (ideal 300-900)")

    # Bullet usage (15)
    bullets = len(BULLET_RE.findall(text))
    bullet_points = 15 if bullets >= 8 else 9 if bullets >= 4 else 4 if bullets >= 1 else 0
    add("Bullet-point formatting", bullet_points, 15, f"{bullets} bullet lines")

    # Quantified achievements (15)
    quantified = sum(1 for line in text.splitlines() if QUANT_RE.search(line))
    quant_points = 15 if quantified >= 4 else 9 if quantified >= 2 else 4 if quantified >= 1 else 0
    add("Quantified achievements", quant_points, 15, f"{quantified} lines contain measurable results")

    # Professional links (10)
    has_linkedin = "linkedin.com" in lower
    has_github = "github.com" in lower
    other_link = bool(re.search(r"https?://(?!\S*(linkedin|github)\.com)\S+", lower))
    add("Professional links", (4 if has_linkedin else 0) + (4 if has_github else 0) + (2 if other_link else 0), 10,
        f"LinkedIn {'found' if has_linkedin else 'missing'}, GitHub {'found' if has_github else 'missing'}, "
        f"portfolio/other {'found' if other_link else 'missing'}")

    suggestions: list[str] = []
    if not has_email:
        suggestions.append("Add a professional email address at the top of the resume.")
    if not has_phone:
        suggestions.append("Add a phone number so recruiters can reach you.")
    for name in missing:
        if name in ("experience", "education", "skills"):
            suggestions.append(f"Add a clearly labelled '{name.title()}' section.")
    if words < 200:
        suggestions.append("The resume is very short; add detail on responsibilities and outcomes.")
    elif words > 1200:
        suggestions.append("The resume is long; trim it to the most relevant 1-2 pages.")
    if bullets < 4:
        suggestions.append("Use bullet points to describe achievements under each role.")
    if quantified < 2:
        suggestions.append("Add measurable results (percentages, counts, time or cost saved) where they are true.")
    if not has_github and not has_linkedin:
        suggestions.append("Add LinkedIn and/or GitHub links.")

    return {
        "health_score": sum(item["points"] for item in breakdown),
        "score_breakdown": breakdown,
        "sections_found": found,
        "sections_missing": missing,
        "word_count": words,
        "rule_based_suggestions": suggestions,
    }


def analyze_resume(text: str) -> dict:
    result = heuristic_review(text)
    wrapped, injection_flags = wrap_untrusted("resume", text, max_chars=6000)
    result["injection_flags"] = injection_flags
    result["ai"] = None
    result["ai_error"] = None

    try:
        extraction = get_ai_service().generate_structured(
            SYSTEM_BASE, build_resume_extraction_prompt(wrapped), ResumeExtraction
        )
    except AIServiceError as exc:
        result["ai_error"] = str(exc)
        return result

    lower = text.lower()
    skills = [s for s in extraction.skills if s.lower() in lower][:40]
    titles = [t for t in extraction.job_titles if t.lower() in lower][:10]
    years = extraction.years_experience
    if years is not None and not 0 <= years <= 50:
        years = None

    result["ai"] = {
        "skills": skills,
        "job_titles": titles,
        "years_experience": years,
        "summary": extraction.summary[:600],
        "suggestions": extraction.suggestions[:6],
        "unsupported_items_removed": (len(extraction.skills) - len(skills))
        + (len(extraction.job_titles) - len(titles)),
    }
    return result
