"""Resume Generation Agent.

Produces job-specific resumes, bullet rewrites and cover letters from the candidate's own verified data.

Anti-fabrication design (nothing is ever invented):
1. Structure and facts come from the user's profile and resume. The tailored resume is built by
   deterministic selection and ordering (skills, bullets, projects), not by free generation.
2. The local model is used only for wording: the summary, optional bullet rewrites and the cover letter.
3. Every AI-written sentence is fact-checked before it is kept. A sentence is dropped if it names a skill the
   candidate does not have, uses a number that is not in the candidate's data, adds a leadership claim, or
   contains a placeholder. Rewritten bullets are rejected on the same grounds.
4. If the model is unavailable or its output does not survive the check, a plain template built only from
   verified facts is used instead, and the result says so.

Job postings are untrusted input: they are wrapped, scanned for injection phrases and never obeyed.
Nothing here sends, submits or attaches anything. Drafts are only saved for the user to review.
"""
import math
import re

from pydantic import BaseModel, Field, field_validator

from app.agents.job_analysis import _keywords as extract_keywords
from app.agents.job_analysis import score_job
from app.core.prompt_guard import wrap_untrusted
from app.services.ai_service import AIServiceError, get_ai_service
from app.services.candidate import summarize_candidate
from app.services.prompts import (
    SYSTEM_BASE,
    build_bullets_prompt,
    build_cover_letter_prompt,
    build_summary_prompt,
)
from app.utils.coerce import as_int
from app.utils.skills import extract_skills

MAX_BULLETS_PER_ROLE = 6
MAX_REWRITES = 6
MAX_PROJECTS = 4
MAX_SKILLS = 30
TONES = ("professional", "warm", "concise")

_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_LEADERSHIP_RE = re.compile(r"\b(led|leading|managed|managing|directed|spearheaded|architected|supervised|headed|owned)\b", re.I)
_PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,60}\]")
_BULLET_PREFIX_RE = re.compile(r"^[\s•\-\*–·▪●◦]+")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# --------------------------------------------------------------------------------------------------
# Structured output models (tolerant of sloppy small-model JSON)
# --------------------------------------------------------------------------------------------------
class SummaryOut(BaseModel):
    summary: str = ""

    @field_validator("summary", mode="before")
    @classmethod
    def _text(cls, value):
        if isinstance(value, list):
            return " ".join(str(v) for v in value)
        return "" if value is None else str(value)


class RewriteItem(BaseModel):
    index: int = -1
    text: str = ""

    @field_validator("index", mode="before")
    @classmethod
    def _index(cls, value):
        return as_int(value, -1)

    @field_validator("text", mode="before")
    @classmethod
    def _text(cls, value):
        return "" if value is None else str(value)


class RewritesOut(BaseModel):
    rewrites: list[RewriteItem] = Field(default_factory=list)

    @field_validator("rewrites", mode="before")
    @classmethod
    def _coerce(cls, value):
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]


class LetterOut(BaseModel):
    paragraphs: list[str] = Field(default_factory=list)

    @field_validator("paragraphs", mode="before")
    @classmethod
    def _coerce(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [p.strip() for p in re.split(r"\n\s*\n|\n", value) if p.strip()]
        if isinstance(value, list):
            return [str(p).strip() for p in value if str(p).strip()]
        return []


# --------------------------------------------------------------------------------------------------
# Fact checking
# --------------------------------------------------------------------------------------------------
def _numbers(text: str) -> set[str]:
    found: set[str] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        number = raw.replace(",", "")
        found.add(number)
        found.add(number.split(".")[0])
    return found


def check_claims(text: str, allowed_skills: set[str], allowed_numbers: set[str], allowed_text: str) -> list[str]:
    """Return the reasons `text` contains something the candidate's data does not support."""
    problems: list[str] = []
    for skill in extract_skills(text):
        if skill not in allowed_skills:
            problems.append(f"mentions '{skill}', which is not in your verified skills")
    for raw in _NUMBER_RE.findall(text):
        number = raw.replace(",", "")
        if number not in allowed_numbers:
            problems.append(f"uses the number {number}, which is not in your data")
    if _LEADERSHIP_RE.search(text) and not _LEADERSHIP_RE.search(allowed_text):
        problems.append("adds a leadership claim that is not in your data")
    return problems


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def _filter_text(text: str, allowed_skills: set[str], allowed_numbers: set[str], allowed_text: str, removed: list) -> str:
    """Keep only sentences that pass the fact check; record the rest in `removed`."""
    kept: list[str] = []
    for sentence in _sentences(text):
        if _PLACEHOLDER_RE.search(sentence):
            removed.append({"sentence": sentence, "reasons": ["contains a placeholder"]})
            continue
        problems = check_claims(sentence, allowed_skills, allowed_numbers, allowed_text)
        if problems:
            removed.append({"sentence": sentence, "reasons": problems})
            continue
        kept.append(sentence)
    return " ".join(kept)


# --------------------------------------------------------------------------------------------------
# Deterministic preparation
# --------------------------------------------------------------------------------------------------
def _relevance(text: str, job_skills: set[str], keywords: set[str]) -> int:
    skills = set(extract_skills(text))
    tokens = set(re.findall(r"[a-z][a-z+#]{3,}", (text or "").lower()))
    return 3 * len(skills & job_skills) + len(tokens & keywords)


def _role_bullets(role: dict) -> list[str]:
    achievements = [a.strip() for a in role.get("achievements", []) if a and a.strip()]
    if achievements:
        return achievements
    description = role.get("description") or ""
    lines = [_BULLET_PREFIX_RE.sub("", line).strip() for line in description.splitlines()]
    lines = [line for line in lines if len(line) >= 15]
    if len(lines) <= 1 and description.strip():
        lines = [s for s in _sentences(_BULLET_PREFIX_RE.sub("", description)) if len(s) >= 15]
    return lines[:8]


def _fmt_month(value: str | None) -> str:
    if not value or not re.match(r"^\d{4}-\d{2}$", value):
        return value or ""
    year, month = value.split("-")
    return f"{_MONTHS[int(month) - 1]} {year}"


def format_period(start: str | None, end: str | None, current: bool) -> str:
    left = _fmt_month(start)
    right = "Present" if current or not end else _fmt_month(end)
    if not left and not right:
        return ""
    return f"{left} - {right}" if left else right


def _rank_roles(profile: dict, job_skills: set[str], keywords: set[str]) -> list[dict]:
    roles = []
    for role in profile.get("experience", []):
        scored = [(b, _relevance(b, job_skills, keywords)) for b in _role_bullets(role)]
        scored.sort(key=lambda item: -item[1])  # stable: equal scores keep their original order
        roles.append(
            {
                "company": role.get("company", ""),
                "title": role.get("title", ""),
                "location": role.get("location"),
                "start_date": role.get("start_date"),
                "end_date": role.get("end_date"),
                "current": bool(role.get("current")),
                "bullets": [{"text": b, "relevance": r} for b, r in scored[:MAX_BULLETS_PER_ROLE]],
            }
        )
    return roles


def _prepare(ctx: dict, job: dict, weights: dict) -> dict:
    profile = ctx["profile"]
    job_text = f"{job.get('title', '')}\n{job.get('description', '')}"
    wrapped, flags = wrap_untrusted("job_posting", job_text, max_chars=3000)
    match = score_job(job, ctx, weights)
    job_skills = set(extract_skills(job_text))
    keywords = set(extract_keywords(job_text, 40))
    roles = _rank_roles(profile, job_skills, keywords)

    facts = summarize_candidate(ctx)
    own_text_parts = [facts, profile.get("summary") or "", ctx.get("resume_text") or ""]
    for role in profile.get("experience", []):
        own_text_parts.append(role.get("description") or "")
        own_text_parts.extend(role.get("achievements", []))
    for project in profile.get("projects", []):
        own_text_parts.append(f"{project.get('name', '')} {project.get('description', '')}")
    allowed_text = "\n".join(own_text_parts)

    allowed_numbers = _numbers(allowed_text)
    years = ctx.get("years_experience")
    if years is not None:
        allowed_numbers |= {str(math.ceil(years)), str(math.floor(years))}

    flat = [
        (b["relevance"], b["text"], role["title"], role["company"])
        for role in roles
        for b in role["bullets"]
    ]
    flat.sort(key=lambda item: -item[0])

    return {
        "wrapped_job": wrapped,
        "injection_flags": flags,
        "match": match,
        "job_skills": job_skills,
        "matched": [m["skill"] for m in match["matched_skills"]],
        "missing": [m["skill"] for m in match["missing_skills"] if not m.get("optional")],
        "roles": roles,
        "top_evidence": flat[:3],
        "facts": facts,
        "allowed_skills": set(ctx["skills"]),
        "allowed_numbers": allowed_numbers,
        "allowed_text": allowed_text,
        "keywords": keywords,
    }


def _base_warnings(prep: dict) -> list[str]:
    warnings = []
    if prep["injection_flags"]:
        warnings.append(
            "The job posting contains text that looks like instructions aimed at AI tools. It was treated as data and ignored."
        )
    return warnings


# --------------------------------------------------------------------------------------------------
# Bullet rewriting
# --------------------------------------------------------------------------------------------------
def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def _verify_rewrite(original: str, improved: str, allowed_skills: set[str]) -> str | None:
    if not 10 <= len(improved) <= 300:
        return "The rewrite has an unreasonable length."
    if len(improved) > 2.2 * len(original) + 40:
        return "The rewrite is much longer than the original, which suggests added content."
    problems = check_claims(
        improved, allowed_skills | set(extract_skills(original)), _numbers(original), original
    )
    return "; ".join(problems) or None


def rewrite_bullets(bullets: list[str], role_title: str, target_skills: list[str], allowed_skills: set[str]) -> list[dict]:
    """Ask the local model to reword bullets. Only rewrites that pass the fact check are accepted.

    Raises AIServiceError when the local model cannot be used.
    """
    numbered = "\n".join(f"{i}. {text}" for i, text in enumerate(bullets, start=1))
    wrapped, _ = wrap_untrusted("bullets", numbered, max_chars=3000)
    out = get_ai_service().generate_structured(
        SYSTEM_BASE, build_bullets_prompt(role_title, target_skills[:10], wrapped), RewritesOut
    )

    by_index: dict[int, str] = {}
    for item in out.rewrites:
        position = item.index - 1
        if 0 <= position < len(bullets) and position not in by_index and item.text.strip():
            by_index[position] = item.text.strip()

    results = []
    for position, original in enumerate(bullets):
        entry = {"index": position, "original": original, "improved": None, "accepted": False, "reason": None}
        improved = by_index.get(position)
        if not improved:
            entry["reason"] = "The model returned no rewrite for this bullet."
        elif _norm(improved) == _norm(original):
            entry["reason"] = "Already clear; left unchanged."
        else:
            entry["improved"] = improved
            reason = _verify_rewrite(original, improved, allowed_skills)
            if reason:
                entry["reason"] = f"Rejected: {reason}."
            else:
                entry["accepted"] = True
        results.append(entry)
    return results


# --------------------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------------------
def _template_summary(ctx: dict, matched: list[str]) -> str:
    headline = (ctx["profile"].get("headline") or "").strip().rstrip(".")
    years = ctx.get("years_experience")
    lead = headline or ("Professional" if (years or matched) else "")
    if not lead:
        return ""
    if years:
        lead += f" with about {years:g} years of experience"
    sentences = [lead + "."]
    if matched:
        sentences.append("Skilled in " + ", ".join(matched[:6]) + ".")
    return " ".join(sentences)


def _build_summary(ctx: dict, job: dict, prep: dict) -> tuple[str, str, str | None, list]:
    """Return (summary, source, ai_error, removed_sentences)."""
    removed: list = []
    relevant = prep["matched"][:12]
    try:
        out = get_ai_service().generate_structured(
            SYSTEM_BASE,
            build_summary_prompt(prep["facts"], job.get("title", ""), relevant, prep["wrapped_job"]),
            SummaryOut,
        )
        text = _filter_text(out.summary, prep["allowed_skills"], prep["allowed_numbers"], prep["allowed_text"], removed)
        if len(text.split()) >= 8:
            return text[:600], "ai", None, removed
        error = "The local model's summary did not pass the fact check, so a template summary was used."
    except AIServiceError as exc:
        error = str(exc)
    return _template_summary(ctx, relevant), "template", error, removed


# --------------------------------------------------------------------------------------------------
# Tailored resume
# --------------------------------------------------------------------------------------------------
def generate_tailored_resume(ctx: dict, job: dict, weights: dict, improve_bullets: bool = False) -> dict:
    prep = _prepare(ctx, job, weights)
    profile = ctx["profile"]
    warnings = _base_warnings(prep)

    summary, source, ai_error, removed = _build_summary(ctx, job, prep)
    if source == "template":
        warnings.append(f"Summary was written from a template using only your verified facts. {ai_error or ''}".strip())

    roles = prep["roles"]
    content_roles = [
        {**{k: v for k, v in role.items() if k != "bullets"}, "bullets": [b["text"] for b in role["bullets"]]}
        for role in roles
    ]
    if not content_roles:
        warnings.append(
            "Your profile has no work experience entries, so the experience section is empty. "
            "Add your roles in Candidate profile for a complete tailored resume."
        )

    bullet_changes: list[dict] = []
    if improve_bullets and content_roles:
        picks = sorted(
            (
                (b["relevance"], ri, bi)
                for ri, role in enumerate(roles)
                for bi, b in enumerate(role["bullets"])
            ),
            key=lambda item: -item[0],
        )[:MAX_REWRITES]
        picks = sorted(picks, key=lambda item: (item[1], item[2]))
        originals = [content_roles[ri]["bullets"][bi] for _, ri, bi in picks]
        try:
            results = rewrite_bullets(originals, job.get("title", ""), prep["matched"], prep["allowed_skills"])
            for (_, ri, bi), result in zip(picks, results):
                if result["accepted"]:
                    content_roles[ri]["bullets"][bi] = result["improved"]
                    bullet_changes.append(
                        {
                            "role": f"{content_roles[ri]['title']} at {content_roles[ri]['company']}",
                            "original": result["original"],
                            "improved": result["improved"],
                        }
                    )
            rejected = sum(1 for r in results if r["improved"] and not r["accepted"])
            if rejected:
                warnings.append(f"{rejected} bullet rewrite(s) were rejected because they added content that is not in your data. The original wording was kept.")
        except AIServiceError as exc:
            warnings.append(f"Bullet rewriting was skipped: {exc}")

    projects = sorted(
        profile.get("projects", []),
        key=lambda p: -_relevance(
            f"{p.get('name', '')} {p.get('description', '')} {' '.join(p.get('technologies', []))}",
            prep["job_skills"], prep["keywords"],
        ),
    )[:MAX_PROJECTS]

    skills_all = list(ctx["skills"])
    ordered_skills = ([s for s in skills_all if s in prep["job_skills"]] + [s for s in skills_all if s not in prep["job_skills"]])[:MAX_SKILLS]

    links = [u for u in (profile.get("linkedin_url"), profile.get("github_url"), profile.get("portfolio_url")) if u]
    content = {
        "header": {
            "name": ctx["full_name"],
            "email": ctx["email"],
            "phone": profile.get("phone") or "",
            "location": profile.get("location") or "",
            "links": links,
        },
        "headline": profile.get("headline") or "",
        "summary": summary,
        "skills": ordered_skills,
        "soft_skills": profile.get("soft_skills", []),
        "experience": content_roles,
        "projects": [
            {"name": p.get("name", ""), "description": p.get("description", ""), "technologies": p.get("technologies", []), "url": p.get("url")}
            for p in projects
        ],
        "education": [
            {k: e.get(k) for k in ("institution", "degree", "field_of_study", "start_year", "end_year", "grade")}
            for e in profile.get("education", [])
        ],
        "certifications": [
            {k: c.get(k) for k in ("name", "issuer", "year")} for c in profile.get("certifications", [])
        ],
        "job_target": {"title": job.get("title", ""), "company": job.get("company", "")},
        "keyword_gaps": prep["missing"][:15],
        "bullet_changes": bullet_changes,
    }
    return {
        "content": content,
        "text": render_resume_text(content),
        "source": source,
        "ai_error": ai_error,
        "warnings": warnings,
        "removed_sentences": removed,
        "injection_flags": prep["injection_flags"],
    }


def render_resume_text(content: dict) -> str:
    header = content.get("header", {})
    lines: list[str] = [header.get("name", "").strip()]
    contact = [header.get(k) for k in ("email", "phone", "location")] + list(header.get("links", []))
    contact_line = " | ".join(str(c) for c in contact if c)
    if contact_line:
        lines.append(contact_line)
    if content.get("headline"):
        lines.append(content["headline"])

    def section(title: str) -> None:
        lines.extend(["", title.upper()])

    if content.get("summary"):
        section("Summary")
        lines.append(content["summary"])
    if content.get("skills"):
        section("Skills")
        lines.append(", ".join(content["skills"]))
    if content.get("soft_skills"):
        lines.append("Soft skills: " + ", ".join(content["soft_skills"]))
    if content.get("experience"):
        section("Experience")
        for role in content["experience"]:
            period = format_period(role.get("start_date"), role.get("end_date"), role.get("current", False))
            lines.append(f"{role.get('title', '')} - {role.get('company', '')}" + (f" ({period})" if period else ""))
            lines.extend(f"- {b}" for b in role.get("bullets", []))
            lines.append("")
        if lines[-1] == "":
            lines.pop()
    if content.get("projects"):
        section("Projects")
        for project in content["projects"]:
            tech = f" [{', '.join(project['technologies'])}]" if project.get("technologies") else ""
            lines.append(f"{project.get('name', '')}{tech}")
            if project.get("description"):
                lines.append(f"- {project['description']}")
    if content.get("education"):
        section("Education")
        for edu in content["education"]:
            years = " - ".join(str(y) for y in (edu.get("start_year"), edu.get("end_year")) if y)
            parts = [edu.get("degree") or "", edu.get("field_of_study") or ""]
            line = f"{', '.join(p for p in parts if p)} - {edu.get('institution', '')}"
            lines.append(line + (f" ({years})" if years else ""))
    if content.get("certifications"):
        section("Certifications")
        for cert in content["certifications"]:
            extra = ", ".join(str(x) for x in (cert.get("issuer"), cert.get("year")) if x)
            lines.append(cert.get("name", "") + (f" ({extra})" if extra else ""))
    return "\n".join(lines).strip()


# --------------------------------------------------------------------------------------------------
# Cover letter
# --------------------------------------------------------------------------------------------------
def _ensure_period(text: str) -> str:
    text = text.strip()
    return text if text[-1:] in ".!?" else text + "."


def _template_letter(ctx: dict, job: dict, prep: dict) -> list[str]:
    title, company = job.get("title", "the role"), job.get("company", "your company")
    headline = (ctx["profile"].get("headline") or "").strip().rstrip(".")
    first = f"I am writing to express my interest in the {title} position at {company}."
    if headline:
        first += f" My professional focus: {headline}."

    second_parts = []
    if prep["matched"]:
        second_parts.append("My background includes " + ", ".join(prep["matched"][:6]) + ", which align with the requirements of this role.")
    for _, text, role_title, role_company in prep["top_evidence"][:2]:
        second_parts.append(f"As {role_title} at {role_company}: {_ensure_period(text)}")
    second = " ".join(second_parts) or "I would bring the experience described in my attached resume to this role."

    third = (
        f"I would welcome the opportunity to discuss how my experience can contribute to {company}. "
        "Thank you for your time and consideration."
    )
    return [first, second, third]


def generate_cover_letter(ctx: dict, job: dict, weights: dict, tone: str = "professional") -> dict:
    tone = tone if tone in TONES else "professional"
    prep = _prepare(ctx, job, weights)
    warnings = _base_warnings(prep)
    removed: list = []
    evidence = [f"{text} (as {title} at {company})" for _, text, title, company in prep["top_evidence"]]

    paragraphs: list[str] = []
    source, ai_error = "ai", None
    try:
        out = get_ai_service().generate_structured(
            SYSTEM_BASE,
            build_cover_letter_prompt(
                prep["facts"], job.get("title", ""), job.get("company", ""),
                prep["matched"][:12], evidence, tone, prep["wrapped_job"],
            ),
            LetterOut,
        )
        for paragraph in out.paragraphs[:5]:
            cleaned = _filter_text(paragraph, prep["allowed_skills"], prep["allowed_numbers"], prep["allowed_text"], removed)
            if cleaned:
                paragraphs.append(cleaned)
        if len(paragraphs) < 2 or sum(len(p.split()) for p in paragraphs) < 50:
            ai_error = "The local model's letter did not pass the fact check, so a template letter was used."
    except AIServiceError as exc:
        ai_error = str(exc)

    if ai_error:
        source = "template"
        paragraphs = _template_letter(ctx, job, prep)
        warnings.append(f"The letter was written from a template using only your verified facts. {ai_error}")
    if removed:
        warnings.append(f"{len(removed)} AI-written sentence(s) were removed because they were not supported by your data.")

    return {
        "content": {"paragraphs": paragraphs, "tone": tone, "job_target": {"title": job.get("title", ""), "company": job.get("company", "")}},
        "text": render_letter_text(paragraphs, ctx["full_name"]),
        "source": source,
        "ai_error": ai_error,
        "warnings": warnings,
        "removed_sentences": removed,
        "injection_flags": prep["injection_flags"],
    }


def render_letter_text(paragraphs: list[str], name: str) -> str:
    body = "\n\n".join(paragraphs)
    signature = f"Sincerely,\n{name}".strip() if name else "Sincerely,"
    return f"Dear Hiring Manager,\n\n{body}\n\n{signature}"
