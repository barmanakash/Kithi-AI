"""Recruiter Outreach Agent.

Drafts recruiter messages, referral requests, follow-ups, thank-you notes and replies from the
candidate's own verified data.

Safety design:
1. The local model writes only the body paragraphs and subject. Greeting, sign-off and the optional job
   link are added by code, so the model can never add contact details or links of its own.
2. Every AI-written sentence is fact-checked with the same rules as Resume Generation: it is dropped if it
   names a skill the candidate does not have, uses a number that is not in the candidate's data,
   adds a leadership claim, or contains a placeholder, a link or an email address.
3. If the model is unavailable or its output does not survive the check, a plain template built only from
   verified facts is used and the result says so.
4. Job postings and received messages are untrusted: wrapped, scanned for injection phrases, never obeyed.
   Numbers that appear only in a received message (interview times, salary) are NOT treated as verified,
   so the model cannot echo them as commitments.

Nothing here sends anything. A draft only becomes sendable after the user approves its exact text.
"""
import re

from pydantic import BaseModel, Field, field_validator

from app.agents.job_analysis import score_job
from app.agents.resume_generation import check_claims
from app.core.prompt_guard import sanitize_untrusted, wrap_untrusted
from app.services.ai_service import AIServiceError, get_ai_service
from app.services.candidate import summarize_candidate
from app.services.prompts import SYSTEM_BASE, build_message_prompt
from app.utils.skills import extract_skills

MAX_SUBJECT = 80
MAX_PARAGRAPHS = 4
MIN_WORDS = {"email": 30, "linkedin": 12}
LINKEDIN_NOTE_LIMIT = 300

_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
_PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,60}\]")
_LINK_RE = re.compile(r"https?://|www\.|\S+@\S+\.\S+", re.I)
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


class MessageOut(BaseModel):
    subject: str = ""
    paragraphs: list[str] = Field(default_factory=list)

    @field_validator("subject", mode="before")
    @classmethod
    def _subject(cls, value):
        return "" if value is None else str(value)

    @field_validator("paragraphs", mode="before")
    @classmethod
    def _paragraphs(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [p.strip() for p in re.split(r"\n\s*\n|\n", value) if p.strip()]
        if isinstance(value, list):
            return [str(p).strip() for p in value if str(p).strip()]
        return []


# --------------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------------
def _numbers(text: str) -> set[str]:
    found: set[str] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        number = raw.replace(",", "")
        found.add(number)
        found.add(number.split(".")[0])
    return found


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def _one_line(text: str, limit: int) -> str:
    return _CTRL_RE.sub(" ", text or "").strip()[:limit]


def _filter(text: str, skills: set[str], numbers: set[str], allowed_text: str, removed: list) -> str:
    kept: list[str] = []
    for sentence in _sentences(text):
        if _PLACEHOLDER_RE.search(sentence):
            removed.append({"sentence": sentence, "reasons": ["contains a placeholder"]})
        elif _LINK_RE.search(sentence):
            removed.append({"sentence": sentence, "reasons": ["contains a link or email address"]})
        else:
            problems = check_claims(sentence, skills, numbers, allowed_text)
            if problems:
                removed.append({"sentence": sentence, "reasons": problems})
            else:
                kept.append(sentence)
    return " ".join(kept)


def _safe_http(url: str | None) -> str | None:
    return url if url and str(url).lower().startswith(("http://", "https://")) else None


def _first_name(name: str | None) -> str:
    parts = _one_line(name or "", 120).split()
    return parts[0] if parts else ""


def _latest_role(profile: dict) -> dict | None:
    roles = profile.get("experience", [])
    for role in roles:
        if role.get("current"):
            return role
    return roles[0] if roles else None


def _resolve_target(job: dict | None, application: dict | None, recruiter: dict | None) -> tuple[str, str]:
    title = (job or {}).get("title") or (application or {}).get("job_title") or ""
    company = (job or {}).get("company") or (application or {}).get("company") or (recruiter or {}).get("company") or ""
    return _one_line(title, 200), _one_line(company, 200)


# --------------------------------------------------------------------------------------------------
# Deterministic parts: greeting, sign-off, templates
# --------------------------------------------------------------------------------------------------
def greeting(channel: str, recruiter: dict | None) -> str:
    first = _first_name((recruiter or {}).get("name"))
    if channel == "linkedin":
        return f"Hi {first}," if first else "Hi,"
    return f"Hello {first}," if first else "Hello,"


def signoff(channel: str, name: str) -> str:
    word = "Best regards," if channel == "email" else "Best,"
    return f"{word}\n{name}".strip() if name else word


def _template_subject(kind: str, title: str, company: str) -> str:
    at = f" at {company}" if company else ""
    if kind == "outreach":
        return f"Interested in {title}{at}" if title else (f"Introduction - opportunities{at}" if company else "Introduction")
    if kind == "referral":
        return f"Referral request: {title}{at}" if title else "Referral request"
    if kind == "follow_up":
        return f"Following up: {title} application" if title else "Following up on my application"
    if kind == "thank_you":
        return f"Thank you - {title}" if title else "Thank you"
    return "Re: your message"


def _template_paragraphs(kind: str, ctx: dict, title: str, company: str, matched: list[str], app_date: str | None) -> list[str]:
    profile = ctx["profile"]
    headline = (profile.get("headline") or "").strip().rstrip(".")
    role = f"the {title} role" if title else "opportunities"
    at = f" at {company}" if company else ""
    skills_line = ("My experience includes " + ", ".join(matched[:6]) + ", which align with this work.") if matched else ""
    latest = _latest_role(profile)
    recent = f"Most recently I worked as {latest['title']} at {latest['company']}." if latest and latest.get("title") and latest.get("company") else ""

    if kind == "outreach":
        first = f"I am interested in {role}{at} and would like to be considered." if title else (
            f"I am reaching out to introduce myself and ask about suitable opportunities{at}."
        )
        if headline:
            first += f" My professional focus: {headline}."
        middle = " ".join(p for p in (skills_line, recent) if p)
        close = "I would be glad to share my resume and talk about how I can contribute. Thank you for your time."
        return [p for p in (first, middle, close) if p]
    if kind == "referral":
        return [
            f"I hope you are well. I noticed {role}{at} and I am very interested in it.",
            " ".join(p for p in (skills_line, recent) if p) or "I believe my background is a good fit.",
            "If you feel comfortable referring me, I would be grateful. If not, I completely understand. Thank you for considering it.",
        ]
    if kind == "follow_up":
        when = f" on {app_date}" if app_date else ""
        return [
            f"I applied for {role}{at}{when} and wanted to follow up on the status of my application.",
            "I remain very interested and would be happy to provide any further information. Thank you for your time.",
        ]
    if kind == "thank_you":
        return [
            f"Thank you for taking the time to speak with me about {role}{at}.",
            "Our conversation strengthened my interest in the position. Please let me know if I can provide anything further.",
        ]
    return [  # reply
        "Thank you for your message and for considering me.",
        "I will confirm the details you mentioned shortly. In the meantime, please let me know if you need anything else from me.",
    ]


def assemble_body(channel: str, recruiter: dict | None, paragraphs: list[str], candidate_name: str, job_url: str | None, kind: str) -> str:
    parts = [greeting(channel, recruiter), *paragraphs]
    if job_url and kind == "referral":
        parts.append(f"Link to the role: {job_url}")
    parts.append(signoff(channel, candidate_name))
    return "\n\n".join(parts)


# --------------------------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------------------------
def generate_message(
    ctx: dict,
    kind: str,
    channel: str,
    tone: str,
    weights: dict,
    recruiter: dict | None = None,
    job: dict | None = None,
    application: dict | None = None,
    incoming_message: str | None = None,
    note: str | None = None,
) -> dict:
    profile = ctx["profile"]
    title, company = _resolve_target(job, application, recruiter)
    app_date = (application or {}).get("application_date")
    note = sanitize_untrusted(note or "", 500).strip()
    warnings: list[str] = []
    injection_flags: list[str] = []

    # Context shown to the model
    target_lines: list[str] = []
    if recruiter:
        who = _one_line(recruiter.get("name", ""), 120)
        extra = ", ".join(x for x in (recruiter.get("title"), recruiter.get("company")) if x)
        target_lines.append(f"Recipient: {who}" + (f" ({_one_line(extra, 200)})" if extra else ""))
    if title:
        target_lines.append(f"Role: {title}" + (f" at {company}" if company else ""))
    if application:
        target_lines.append(f"Application status: {application.get('status', '')}" + (f", submitted {app_date}" if app_date else ""))

    # Skills the model may claim: only verified skills that matter for the role
    matched: list[str] = []
    job_url = None
    wrapped_job = None
    if job:
        match = score_job(job, ctx, weights)
        matched = [m["skill"] for m in match["matched_skills"]][:12]
        job_url = _safe_http(job.get("url"))
        wrapped_job, flags = wrap_untrusted("job_posting", f"{job.get('title', '')}\n{job.get('description', '')}", max_chars=2500)
        injection_flags += flags
        if flags:
            warnings.append("The job posting contains text that looks like instructions aimed at AI tools. It was treated as data and ignored.")
    if not matched:
        matched = list(ctx["skills"])[:8]

    wrapped_incoming = None
    if incoming_message:
        wrapped_incoming, flags = wrap_untrusted("recruiter_message", incoming_message, max_chars=3000)
        injection_flags += flags
        if flags:
            warnings.append(
                "The message you pasted contains wording that looks like instructions to an AI tool or a request for your documents. "
                "Kithi did not act on it. Decide yourself what to share."
            )

    facts = summarize_candidate(ctx)
    allowed_text = "\n".join(
        [facts, profile.get("summary") or "", ctx.get("resume_text") or "", note, title, company, app_date or ""]
    )
    allowed_numbers = _numbers(allowed_text)
    if ctx.get("years_experience") is not None:
        years = ctx["years_experience"]
        allowed_numbers |= {str(int(years)), str(int(years) + (0 if years == int(years) else 1))}
    allowed_skills = set(ctx["skills"])

    removed: list = []
    paragraphs: list[str] = []
    subject = ""
    ai_error: str | None = None
    try:
        out = get_ai_service().generate_structured(
            SYSTEM_BASE,
            build_message_prompt(kind, channel, tone, facts, matched, target_lines, note, wrapped_job, wrapped_incoming),
            MessageOut,
        )
        for paragraph in out.paragraphs[:MAX_PARAGRAPHS + 1]:
            cleaned = _filter(paragraph, allowed_skills, allowed_numbers, allowed_text, removed)
            if cleaned:
                paragraphs.append(cleaned)
        paragraphs = paragraphs[:MAX_PARAGRAPHS]
        if channel == "email":
            subject = _one_line(_filter(_one_line(out.subject, 200), allowed_skills, allowed_numbers, allowed_text, []), MAX_SUBJECT)
        if sum(len(p.split()) for p in paragraphs) < MIN_WORDS[channel]:
            ai_error = "The local model's message did not pass the fact check, so a template was used."
    except AIServiceError as exc:
        ai_error = str(exc)

    source = "ai"
    if ai_error:
        source = "template"
        paragraphs = _template_paragraphs(kind, ctx, title, company, matched if job else [], app_date)
        subject = ""
        warnings.append(f"The message was written from a template using only your verified facts. {ai_error}")
    if removed:
        warnings.append(f"{len(removed)} AI-written sentence(s) were removed because they were not supported by your data.")

    if channel == "email" and not subject:
        subject = _template_subject(kind, title, company)[:MAX_SUBJECT + 40]
    if channel == "linkedin":
        subject = ""
        if sum(len(p) for p in paragraphs) > LINKEDIN_NOTE_LIMIT:
            warnings.append(
                f"This is longer than LinkedIn's {LINKEDIN_NOTE_LIMIT}-character connection note limit. "
                "Use it as a message to an existing connection, or shorten it."
            )
    if not (recruiter or {}).get("name"):
        warnings.append("No recipient name saved, so the greeting is generic.")
    if kind == "reply":
        warnings.append("Check that the reply fits what the recruiter actually asked. Kithi cannot confirm times, salary or availability for you.")

    body = assemble_body(channel, recruiter, paragraphs, ctx["full_name"], job_url, kind)
    return {
        "subject": subject,
        "body": body,
        "source": source,
        "ai_error": ai_error,
        "warnings": warnings,
        "removed_sentences": removed,
        "injection_flags": sorted(set(injection_flags)),
    }
