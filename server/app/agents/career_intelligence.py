"""Career Intelligence Agent.

- Skill gaps and strengths are computed deterministically from your saved job matches, so every
  number can be traced to real jobs.
- The learning roadmap and portfolio ideas are written by the local model, then filtered: milestones
  may only target skills from your gap list or your own skills, tasks containing links are dropped,
  and nothing is stored if the model returns nothing usable.
- Progress is a transparent average of measurable components, never a made-up score.
"""
from collections import Counter

from bson import ObjectId
from pydantic import BaseModel, Field, field_validator

from app.core.prompt_guard import wrap_untrusted
from app.database.mongo import get_db
from app.services.ai_service import AIResponseError, get_ai_service
from app.services.candidate import summarize_candidate
from app.services.prompts import SYSTEM_BASE
from app.utils.coerce import as_int, as_str_list
from app.utils.skills import canonical

SUBMITTED = ["applied", "interview_scheduled", "interview_completed", "offer_received", "rejected", "no_response"]
INTERVIEWING = ["interview_scheduled", "interview_completed", "offer_received"]


def aggregate_skill_gaps(user_id: ObjectId, limit_matches: int = 300) -> dict:
    matches = list(
        get_db().job_matches.find(
            {"user_id": user_id, "score": {"$ne": None}},
            {"missing_skills": 1, "matched_skills": 1},
        ).sort("computed_at", -1).limit(limit_matches)
    )
    total = len(matches)
    missing: Counter = Counter()
    optional_only: dict[str, bool] = {}
    matched: Counter = Counter()
    for match in matches:
        for item in match.get("missing_skills", []):
            skill = item["skill"]
            missing[skill] += 1
            optional_only[skill] = optional_only.get(skill, True) and bool(item.get("optional"))
        for item in match.get("matched_skills", []):
            matched[item["skill"]] += 1

    def share(count: int) -> int:
        return round(100 * count / total) if total else 0

    return {
        "jobs_analyzed": total,
        "gaps": [
            {"skill": s, "jobs_requiring": n, "share_percent": share(n), "mostly_optional": optional_only.get(s, False)}
            for s, n in missing.most_common(15)
        ],
        "strengths": [
            {"skill": s, "jobs_matching": n, "share_percent": share(n)} for s, n in matched.most_common(15)
        ],
        "note": None if total else "No scored jobs yet. Save or discover jobs in AI Job Search first, then check again.",
    }


# ---------------------------------------------------------------- roadmap (local AI)

class Milestone(BaseModel):
    week: int = 1
    skill: str = ""
    title: str = ""
    tasks: list[str] = Field(default_factory=list)

    @field_validator("week", mode="before")
    @classmethod
    def _week(cls, v):
        return as_int(v, 1)

    @field_validator("skill", "title", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v).strip()

    @field_validator("tasks", mode="before")
    @classmethod
    def _tasks(cls, v):
        return as_str_list(v)


class ProjectIdea(BaseModel):
    name: str = ""
    description: str = ""
    skills: list[str] = Field(default_factory=list)

    @field_validator("name", "description", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v).strip()

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        return as_str_list(v)


class Roadmap(BaseModel):
    target_role: str = ""
    milestones: list[Milestone] = Field(default_factory=list)
    portfolio_projects: list[ProjectIdea] = Field(default_factory=list)

    @field_validator("target_role", mode="before")
    @classmethod
    def _role(cls, v):
        return "" if v is None else str(v).strip()

    @field_validator("milestones", "portfolio_projects", mode="before")
    @classmethod
    def _dict_items(cls, v):
        return [i for i in v if isinstance(i, dict)] if isinstance(v, list) else []


_ROADMAP_TASK = (
    "Create a {weeks}-week learning roadmap for the candidate below.\n"
    "Return JSON with exactly these keys:\n"
    '{{"target_role": string, "milestones": [{{"week": number, "skill": string, "title": string, "tasks": [string]}}], '
    '"portfolio_projects": [{{"name": string, "description": string, "skills": [string]}}]}}\n'
    "Rules:\n"
    "- Target role: {role}\n"
    "- Skills to learn (only use these as milestone skills): {focus}\n"
    "- One milestone per skill, ordered by week (week 1 to {weeks}). Each milestone has 2 to 4 concrete hands-on practice tasks.\n"
    "- Suggest 2 or 3 portfolio projects that combine the skills to learn with skills the candidate already has.\n"
    "- Do NOT include links, course or certificate names, prices or statistics. Plain actionable tasks only.\n"
)


def build_roadmap(cand: dict, target_role: str, focus: list[str], weeks: int) -> dict:
    wrapped, flags = wrap_untrusted("candidate_profile", summarize_candidate(cand), max_chars=3000)
    prompt = _ROADMAP_TASK.format(weeks=weeks, role=target_role, focus=", ".join(focus)) + "\n" + wrapped
    roadmap = get_ai_service().generate_structured(SYSTEM_BASE, prompt, Roadmap)

    allowed = {canonical(s).lower() for s in focus} | {canonical(s).lower() for s in cand["skills"]}
    focus_keys = {canonical(s).lower() for s in focus}
    items = []
    for m in roadmap.milestones[:12]:
        if m.skill and canonical(m.skill).lower() not in focus_keys:
            continue
        tasks = [t[:220] for t in m.tasks if "http" not in t.lower() and "www." not in t.lower()][:5]
        if not tasks:
            continue
        skill = canonical(m.skill) if m.skill else ""
        items.append(
            {
                "week": min(max(m.week, 1), weeks),
                "skill": skill,
                "title": (m.title or f"Learn {skill}")[:120],
                "tasks": tasks,
                "done": False,
                "done_at": None,
            }
        )
    items.sort(key=lambda i: i["week"])

    projects = []
    for p in roadmap.portfolio_projects[:3]:
        if not p.name:
            continue
        projects.append(
            {
                "name": p.name[:100],
                "description": p.description[:400],
                "skills": [canonical(s) for s in p.skills if canonical(s).lower() in allowed][:8],
            }
        )

    if not items:
        raise AIResponseError(
            "The local model did not produce a usable roadmap. Try again, or choose fewer focus skills."
        )
    return {"target_role": roadmap.target_role[:100] or target_role, "items": items, "portfolio_projects": projects, "injection_flags": flags}


# ---------------------------------------------------------------- progress

def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def career_progress(user_id: ObjectId, cand: dict) -> dict:
    db = get_db()

    plans = list(db.learning_plans.find({"user_id": user_id}, {"items.done": 1}))
    total_items = sum(len(p.get("items", [])) for p in plans)
    done_items = sum(1 for p in plans for i in p.get("items", []) if i.get("done"))
    learning = {
        "plans": len(plans),
        "items_total": total_items,
        "items_done": done_items,
        "percent": round(100 * done_items / total_items) if total_items else None,
    }

    assessments = list(db.skill_assessments.find({"user_id": user_id}, {"level": 1, "kind": 1}))
    levels = [a["level"] for a in assessments if isinstance(a.get("level"), (int, float))]
    skills = {
        "assessed": len(assessments),
        "average_level": _avg(levels),
        "strengths": sum(1 for a in assessments if a.get("kind") == "strength"),
        "gaps": sum(1 for a in assessments if a.get("kind") == "gap"),
        "skills_in_profile_and_resume": len(cand["skills"]),
    }

    feedback = list(db.interview_feedback.find({"user_id": user_id}, {"overall_score": 1}).sort("created_at", -1).limit(10))
    scores = [f["overall_score"] for f in feedback if isinstance(f.get("overall_score"), (int, float))]
    trend = None
    if len(scores) >= 4:
        half = len(scores) // 2
        diff = (_avg(scores[:half]) or 0) - (_avg(scores[half:]) or 0)
        trend = "improving" if diff > 0.5 else "declining" if diff < -0.5 else "steady"
    interviews = {"scored_sessions": len(scores), "average_score": _avg(scores), "latest_scores": list(reversed(scores)), "trend": trend}

    counts = {row["_id"]: row["n"] for row in db.applications.aggregate([{"$match": {"user_id": user_id}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    submitted = sum(counts.get(s, 0) for s in SUBMITTED)
    interviewing = sum(counts.get(s, 0) for s in INTERVIEWING)
    applications = {
        "total": sum(counts.values()),
        "submitted": submitted,
        "reached_interview_or_offer": interviewing,
        "interview_rate_percent": round(100 * interviewing / submitted) if submitted else None,
    }

    resume_analysis = (cand.get("resume") or {}).get("analysis") or {}
    resume_score = resume_analysis.get("health_score")

    components = []
    if learning["percent"] is not None:
        components.append({"label": "Learning plan completion", "percent": learning["percent"]})
    components.append({"label": "Profile completeness", "percent": cand["completeness"]["percent"]})
    if resume_score is not None:
        components.append({"label": "Resume health", "percent": int(resume_score)})
    if interviews["average_score"] is not None:
        components.append({"label": "Average interview score", "percent": round(interviews["average_score"] * 10)})
    if skills["average_level"] is not None:
        components.append({"label": "Average self-assessed skill level", "percent": round(skills["average_level"] * 20)})

    return {
        "overall_percent": round(sum(c["percent"] for c in components) / len(components)) if components else None,
        "components": components,
        "learning": learning,
        "skills": skills,
        "interviews": interviews,
        "applications": applications,
        "note": "Overall progress is the plain average of the components listed. Components with no data yet are left out.",
    }
