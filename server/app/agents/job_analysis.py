"""Job Analysis Agent: transparent, evidence-based compatibility scoring.

The score is deterministic. Every component reports its weight, its score, a plain-language
detail and the evidence behind it. Components with no usable data are excluded and the remaining
weights are re-normalised, so missing information never silently drags a score up or down.
"""
import re
from collections import Counter

from pydantic import BaseModel

from app.core.prompt_guard import wrap_untrusted
from app.services.ai_service import AIServiceError, get_ai_service
from app.services.candidate import education_level
from app.services.prompts import SYSTEM_BASE
from app.utils.skills import extract_skills

DEFAULT_WEIGHTS = {
    "skills": 40,
    "experience": 20,
    "responsibilities": 15,
    "education": 5,
    "location": 10,
    "preferences": 10,
}
COMPONENT_LABELS = {
    "skills": "Skills",
    "experience": "Experience",
    "responsibilities": "Responsibilities",
    "education": "Education",
    "location": "Location",
    "preferences": "Preferences",
}

_OPTIONAL_HINT = re.compile(r"preferred|nice[\s-]to[\s-]have|bonus|\bplus\b|good to have|desirable|added advantage", re.I)
_YEARS_RE = re.compile(r"(\d{1,2})\+?(?:\s*(?:-|to)\s*\d{1,2})?\s*(?:years?|yrs?)", re.I)
_STOP = set(
    "the and for with that this are you our will have from your their been has was were into over more than "
    "such other also able etc per via within across including include required requirements responsibilities "
    "experience years work working team teams role job candidate looking strong good great skills skill "
    "knowledge ability using use used build building develop developing development company opportunity "
    "environment business technical solutions client clients".split()
)


def _keywords(text: str, top: int = 40) -> list[str]:
    tokens = re.findall(r"[a-z][a-z+#]{3,}", (text or "").lower())
    counts = Counter(t for t in tokens if t not in _STOP)
    return [word for word, _ in counts.most_common(top)]


def _required_years(text: str) -> int | None:
    values = []
    for match in _YEARS_RE.finditer(text):
        window = text[max(0, match.start() - 80): match.end() + 80].lower()
        if "experience" in window:
            values.append(int(match.group(1)))
    return min(values) if values else None


def _norm_type(value: str | None) -> str | None:
    if not value:
        return None
    value = re.sub(r"[\s-]+", "_", value.strip().lower())
    for known in ("full_time", "part_time", "contract", "internship"):
        if known in value:
            return known
    return value


def _skills_component(job_skills: dict[str, str], cand: dict) -> tuple[dict, list, list]:
    matched, missing = [], []
    required_total = 0.0
    matched_total = 0.0
    for skill, snippet in job_skills.items():
        optional = bool(_OPTIONAL_HINT.search(snippet))
        weight = 0.5 if optional else 1.0
        required_total += weight
        if skill in cand["skills"]:
            matched_total += weight
            matched.append({"skill": skill, "job_evidence": snippet, "candidate_source": cand["skills"][skill], "optional": optional})
        else:
            missing.append({"skill": skill, "job_evidence": snippet, "optional": optional})
    if required_total == 0:
        return {"score": None, "detail": "No recognisable skills were found in the job description.", "evidence": []}, matched, missing
    score = matched_total / required_total
    return {
        "score": score,
        "detail": f"{len(matched)} of {len(job_skills)} skills in the job description are present in your profile or resume.",
        "evidence": [f"{m['skill']} (from your {m['candidate_source']})" for m in matched][:15],
    }, matched, missing


def _experience_component(job_text: str, cand: dict) -> dict:
    required = _required_years(job_text)
    have = cand["years_experience"]
    if required is None:
        return {"score": None, "detail": "The job does not state required years of experience.", "evidence": []}
    if have is None:
        return {"score": None, "detail": f"The job asks for {required}+ years; your experience duration is unknown. Add dated roles to your profile.", "evidence": []}
    return {
        "score": min(1.0, have / required),
        "detail": f"The job asks for {required}+ years; you have about {have}.",
        "evidence": [f"Required: {required} years", f"Yours: {have} years"],
    }


def _responsibilities_component(job_text: str, cand: dict) -> dict:
    job_kw = _keywords(job_text)
    if len(job_kw) < 8:
        return {"score": None, "detail": "The job description is too short to compare responsibilities.", "evidence": []}
    candidate_tokens = set(re.findall(r"[a-z][a-z+#]{3,}", cand["corpus"].lower()))
    if not candidate_tokens:
        return {"score": None, "detail": "No profile or resume text available to compare.", "evidence": []}
    overlap = [w for w in job_kw if w in candidate_tokens]
    return {
        "score": min(1.0, (len(overlap) / len(job_kw)) / 0.6),
        "detail": f"{len(overlap)} of the job's {len(job_kw)} key terms also appear in your experience text.",
        "evidence": overlap[:15],
    }


def _education_component(job_text: str, cand: dict) -> dict:
    required = education_level(job_text)
    if required == 0:
        return {"score": None, "detail": "No specific degree is mentioned in the job.", "evidence": []}
    have = cand["education_level"]
    names = {1: "diploma", 2: "bachelor's", 3: "master's", 4: "doctorate"}
    if have == 0:
        return {"score": None, "detail": f"The job mentions a {names[required]} degree; none was found in your profile or resume.", "evidence": []}
    score = 1.0 if have >= required else 0.5 if have == required - 1 else 0.0
    return {"score": score, "detail": f"The job mentions a {names[required]} degree; your highest detected level is {names[have]}.", "evidence": []}


def _location_component(job: dict, cand: dict) -> dict:
    job_loc = (job.get("location") or "").lower()
    remote = bool(job.get("remote")) or "remote" in job_loc
    prefs = [p.lower() for p in cand["preferred_locations"]] + ([cand["location"].lower()] if cand["location"] else [])
    if remote:
        if "remote" in cand["employment_preferences"] or not prefs:
            return {"score": 1.0, "detail": "The role is remote.", "evidence": []}
        return {"score": 0.8, "detail": "The role is remote; you listed specific preferred locations.", "evidence": []}
    if not job_loc or not prefs:
        return {"score": None, "detail": "Location information is missing on the job or in your preferences.", "evidence": []}
    job_tokens = set(re.findall(r"[a-z]{3,}", job_loc))
    pref_tokens = set(re.findall(r"[a-z]{3,}", " ".join(prefs)))
    if job_tokens & pref_tokens:
        return {"score": 1.0, "detail": f"The job location ({job.get('location')}) matches your preferences.", "evidence": sorted(job_tokens & pref_tokens)}
    return {"score": 0.0, "detail": f"The job location ({job.get('location')}) is not in your preferred locations.", "evidence": []}


def _preferences_component(job: dict, cand: dict) -> dict:
    prefs = set(cand["employment_preferences"])
    type_prefs = prefs & {"full_time", "part_time", "contract", "internship"}
    mode_prefs = prefs & {"remote", "hybrid", "onsite"}
    parts, evidence = [], []
    job_type = _norm_type(job.get("job_type"))
    if type_prefs and job_type:
        ok = job_type in type_prefs
        parts.append(1.0 if ok else 0.0)
        evidence.append(f"Job type {job_type} {'matches' if ok else 'is not in'} your preferences")
    if mode_prefs:
        mode = "remote" if job.get("remote") else None
        if mode:
            ok = "remote" in mode_prefs
            parts.append(1.0 if ok else 0.3)
            evidence.append(f"Remote role {'matches' if ok else 'is not in'} your work-mode preferences")
    if not parts:
        return {"score": None, "detail": "No comparable employment preferences.", "evidence": []}
    return {"score": sum(parts) / len(parts), "detail": "Employment type and work mode compared with your preferences.", "evidence": evidence}


def _label(score: float) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "good"
    if score >= 35:
        return "partial"
    return "weak"


def score_job(job: dict, cand: dict, weights: dict | None = None) -> dict:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    job_text = f"{job.get('title', '')}\n{job.get('description', '')}"
    job_skills = extract_skills(job_text)

    skills_comp, matched, missing = _skills_component(job_skills, cand)
    raw = {
        "skills": skills_comp,
        "experience": _experience_component(job_text, cand),
        "responsibilities": _responsibilities_component(job_text, cand),
        "education": _education_component(job_text, cand),
        "location": _location_component(job, cand),
        "preferences": _preferences_component(job, cand),
    }
    components = []
    weighted_sum, available_weight = 0.0, 0.0
    for key, comp in raw.items():
        weight = float(weights.get(key, 0))
        entry = {"key": key, "label": COMPONENT_LABELS[key], "weight": weight, **comp}
        entry["score_percent"] = None if comp["score"] is None else round(comp["score"] * 100)
        components.append(entry)
        if comp["score"] is not None and weight > 0:
            weighted_sum += weight * comp["score"]
            available_weight += weight

    if available_weight == 0:
        score, notes = None, ["Not enough data to calculate a score. Upload a resume or complete your profile."]
    else:
        score = round(100 * weighted_sum / available_weight)
        notes = []
        excluded = [c["label"] for c in components if c["score"] is None]
        if excluded:
            notes.append("Excluded from the score (no usable data): " + ", ".join(excluded))

    return {
        "score": score,
        "label": _label(score) if score is not None else "unknown",
        "components": components,
        "matched_skills": matched,
        "missing_skills": missing,
        "weights": weights,
        "notes": notes,
    }


class _Explanation(BaseModel):
    explanation: str = ""


def explain_match(job: dict, result: dict) -> tuple[str | None, str | None]:
    """Optional natural-language summary written from the computed facts only."""
    facts = [f"Job: {job.get('title')} at {job.get('company')}", f"Score: {result['score']} ({result['label']})"]
    for comp in result["components"]:
        facts.append(f"{comp['label']}: {comp['detail']}")
    if result["missing_skills"]:
        facts.append("Missing skills: " + ", ".join(m["skill"] for m in result["missing_skills"][:10]))
    wrapped, _ = wrap_untrusted("match_facts", "\n".join(facts), max_chars=3000)
    prompt = (
        'Write a 3-sentence plain-language explanation of this job match using ONLY the facts below. '
        'Do not add facts. Return JSON: {"explanation": string}\n\n' + wrapped
    )
    try:
        out = get_ai_service().generate_structured(SYSTEM_BASE, prompt, _Explanation)
        return out.explanation[:800], None
    except AIServiceError as exc:
        return None, str(exc)
