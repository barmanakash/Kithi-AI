"""Builds one consistent, verified view of the candidate for every agent.

Only information the user entered or uploaded is used. Nothing is inferred beyond that.
"""
import re
from datetime import date

from bson import ObjectId

from app.database.mongo import get_db
from app.utils.skills import canonical, extract_skills

_EDU_PATTERNS = [
    (4, re.compile(r"\b(ph\.?d|doctorate)\b", re.I)),
    (3, re.compile(r"\b(master'?s?|m\.?tech|mtech|m\.?sc|msc|mba|mca|m\.e\.)", re.I)),
    (2, re.compile(r"\b(bachelor'?s?|b\.?tech|btech|b\.?sc|bsc|bca|b\.com|b\.e\.)", re.I)),
    (1, re.compile(r"\bdiploma\b", re.I)),
]


def education_level(text: str) -> int:
    for level, pattern in _EDU_PATTERNS:
        if pattern.search(text or ""):
            return level
    return 0


def _months(value: str) -> int:
    year, month = value.split("-")
    return int(year) * 12 + int(month)


def years_from_experience(experience: list[dict]) -> float | None:
    """Total years across all roles, with overlapping periods merged."""
    today = date.today()
    intervals: list[tuple[int, int]] = []
    for job in experience or []:
        start = job.get("start_date")
        if not start:
            continue
        end = job.get("end_date")
        end_m = _months(end) if end else today.year * 12 + today.month
        if job.get("current"):
            end_m = today.year * 12 + today.month
        start_m = _months(start)
        if end_m >= start_m:
            intervals.append((start_m, end_m))
    if not intervals:
        return None
    intervals.sort()
    merged = [list(intervals[0])]
    for start_m, end_m in intervals[1:]:
        if start_m <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end_m)
        else:
            merged.append([start_m, end_m])
    return round(sum(e - s for s, e in merged) / 12, 1)


def profile_completeness(profile: dict) -> dict:
    checks = {
        "full_name": bool(profile.get("full_name")),
        "headline": bool(profile.get("headline")),
        "summary": bool(profile.get("summary")),
        "phone": bool(profile.get("phone")),
        "location": bool(profile.get("location")),
        "experience": bool(profile.get("experience")),
        "technical_skills": bool(profile.get("technical_skills")),
        "education": bool(profile.get("education")),
        "preferred_locations": bool(profile.get("preferred_locations")),
        "employment_preferences": bool(profile.get("employment_preferences")),
        "links": bool(profile.get("linkedin_url") or profile.get("github_url") or profile.get("portfolio_url")),
    }
    percent = round(100 * sum(checks.values()) / len(checks))
    return {"percent": percent, "missing": [k for k, ok in checks.items() if not ok]}


def get_primary_resume(user_id: ObjectId) -> dict | None:
    db = get_db()
    resume = db.resumes.find_one({"user_id": user_id, "is_primary": True})
    return resume or db.resumes.find_one({"user_id": user_id}, sort=[("created_at", -1)])


def load_candidate_context(user_id: ObjectId, user: dict | None = None) -> dict:
    db = get_db()
    profile = db.candidate_profiles.find_one({"user_id": user_id}) or {}
    resume = get_primary_resume(user_id)
    resume_text = (resume or {}).get("text", "")

    skills: dict[str, str] = {}  # canonical -> source
    for skill in profile.get("technical_skills", []):
        skills[canonical(skill)] = "profile"
    ai_block = (((resume or {}).get("analysis") or {}).get("ai")) or {}
    for skill in ai_block.get("skills", []):
        skills.setdefault(canonical(skill), "resume_analysis")
    for skill in extract_skills(resume_text):
        skills.setdefault(skill, "resume")

    experience_text_parts: list[str] = []
    for job in profile.get("experience", []):
        job_text = f"{job.get('title', '')} {job.get('description', '')} " + " ".join(job.get("achievements", []))
        experience_text_parts.append(job_text)
        for skill in extract_skills(job_text):
            skills.setdefault(skill, "profile")
    for project in profile.get("projects", []):
        experience_text_parts.append(f"{project.get('name', '')} {project.get('description', '')}")
        for tech in project.get("technologies", []):
            skills.setdefault(canonical(tech), "profile")

    years = years_from_experience(profile.get("experience", []))
    if years is None and resume:
        years = (((resume.get("analysis") or {}).get("ai")) or {}).get("years_experience")

    education_text = " ".join(f"{e.get('degree', '')} {e.get('field_of_study', '')}" for e in profile.get("education", []))
    edu_level = max(education_level(education_text), education_level(resume_text))

    corpus = " ".join(experience_text_parts + [profile.get("summary") or "", profile.get("headline") or "", resume_text])

    return {
        "user_id": user_id,
        "full_name": profile.get("full_name") or (user or {}).get("full_name") or "",
        "email": (user or {}).get("email", ""),
        "profile": profile,
        "resume": resume,
        "resume_text": resume_text,
        "skills": skills,
        "years_experience": years,
        "education_level": edu_level,
        "corpus": corpus,
        "location": profile.get("location") or "",
        "preferred_locations": profile.get("preferred_locations", []),
        "employment_preferences": profile.get("employment_preferences", []),
        "has_data": bool(skills or resume_text),
        "completeness": profile_completeness(profile),
    }


def summarize_candidate(ctx: dict, max_skills: int = 25) -> str:
    """Compact, factual candidate summary to place in prompts (user's own verified data)."""
    profile = ctx["profile"]
    lines = [f"Name: {ctx['full_name']}"]
    if profile.get("headline"):
        lines.append(f"Headline: {profile['headline']}")
    if ctx["years_experience"] is not None:
        lines.append(f"Total experience (years): {ctx['years_experience']}")
    if ctx["skills"]:
        lines.append("Skills: " + ", ".join(list(ctx["skills"])[:max_skills]))
    for job in profile.get("experience", [])[:5]:
        lines.append(f"Role: {job.get('title')} at {job.get('company')} ({job.get('start_date')} to {job.get('end_date') or 'present'})")
    for edu in profile.get("education", [])[:3]:
        lines.append(f"Education: {edu.get('degree')} - {edu.get('institution')}")
    for project in profile.get("projects", [])[:4]:
        lines.append(f"Project: {project.get('name')} - {(project.get('description') or '')[:150]}")
    return "\n".join(lines)
