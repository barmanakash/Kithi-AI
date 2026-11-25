"""Career routes: skill gaps, learning roadmap/plans, goals, skill assessments, progress, GitHub analysis."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents.career_intelligence import aggregate_skill_gaps, build_roadmap, career_progress
from app.agents.github_analyzer import GitHubError, analyze_github, username_from_url
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, to_object_id, utcnow
from app.utils.skills import canonical

router = APIRouter(prefix="/career", tags=["career"])

MAX_PLANS = 30
MAX_GOALS = 200
MAX_SKILLS = 300


# ---------------------------------------------------------------- skill gaps

@router.get("/skill-gaps")
def skill_gaps(user: dict = Depends(get_current_user)) -> dict:
    """Skills your saved jobs ask for that are missing from your profile/resume, ranked by frequency."""
    return aggregate_skill_gaps(user["_id"])


# ---------------------------------------------------------------- roadmap and plans

class RoadmapIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_role: str | None = Field(default=None, max_length=100)
    weeks: int = Field(default=8, ge=2, le=26)
    focus_skills: list[str] = Field(default_factory=list, max_length=10)


def _default_role(user_id, cand: dict) -> str:
    goal = get_db().career_goals.find_one({"user_id": user_id, "kind": "goal", "status": "active"}, sort=[("created_at", -1)])
    if goal:
        return goal["text"][:100]
    experience = cand["profile"].get("experience") or []
    if experience and experience[0].get("title"):
        return experience[0]["title"]
    return cand["profile"].get("headline") or "Software professional"


@router.post("/roadmap", status_code=201)
def create_roadmap(body: RoadmapIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Turn your skill gaps into a week-by-week learning plan with portfolio project ideas (local AI)."""
    db = get_db()
    if db.learning_plans.count_documents({"user_id": user["_id"]}) >= MAX_PLANS:
        raise HTTPException(status_code=409, detail=f"Plan limit reached ({MAX_PLANS}). Delete an old plan first.")
    cand = load_candidate_context(user["_id"], user)
    if not cand["has_data"]:
        raise HTTPException(status_code=422, detail="Upload a resume or complete your profile first.")

    focus = [canonical(s) for s in body.focus_skills if s.strip()]
    if not focus:
        focus = [g["skill"] for g in aggregate_skill_gaps(user["_id"])["gaps"][:6]]
    if not focus:
        raise HTTPException(
            status_code=422,
            detail="No skill gaps found yet. Save or discover jobs first, or pass focus_skills yourself.",
        )

    role = (body.target_role or "").strip() or _default_role(user["_id"], cand)
    result = build_roadmap(cand, role, focus, body.weeks)
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "title": f"{result['target_role']} - {body.weeks}-week plan"[:150],
        "target_role": result["target_role"],
        "weeks": body.weeks,
        "focus_skills": focus,
        "items": result["items"],
        "portfolio_projects": result["portfolio_projects"],
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = db.learning_plans.insert_one(doc).inserted_id
    record_task(user["_id"], "career_intelligence", "completed", f"Roadmap for {result['target_role']}", {"plan_id": str(doc["_id"])})
    log_activity(user["_id"], "learning_plan_created", {"plan_id": str(doc["_id"])}, request)
    return public(doc)


@router.get("/plans")
def list_plans(limit: int = 50, user: dict = Depends(get_current_user)) -> dict:
    docs = get_db().learning_plans.find({"user_id": user["_id"]}).sort("created_at", -1).limit(clamp_limit(limit, 100))
    plans = []
    for doc in docs:
        out = public(doc)
        items = out.get("items", [])
        out["progress"] = {"done": sum(1 for i in items if i.get("done")), "total": len(items)}
        plans.append(out)
    return {"plans": plans}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, user: dict = Depends(get_current_user)) -> dict:
    return public(get_owned_or_404("learning_plans", plan_id, user["_id"]))


class ItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    done: bool


@router.patch("/plans/{plan_id}/items/{index}")
def update_plan_item(plan_id: str, index: int, body: ItemUpdate, user: dict = Depends(get_current_user)) -> dict:
    plan = get_owned_or_404("learning_plans", plan_id, user["_id"])
    if index < 0 or index >= len(plan.get("items", [])):
        raise HTTPException(status_code=404, detail="Plan item not found")
    now = utcnow()
    get_db().learning_plans.update_one(
        {"_id": plan["_id"], "user_id": user["_id"]},
        {"$set": {f"items.{index}.done": body.done, f"items.{index}.done_at": now if body.done else None, "updated_at": now}},
    )
    return public(get_db().learning_plans.find_one({"_id": plan["_id"]}))


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    plan = get_owned_or_404("learning_plans", plan_id, user["_id"], {"_id": 1})
    get_db().learning_plans.delete_one({"_id": plan["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "learning_plan_deleted", {"plan_id": plan_id}, request)


# ---------------------------------------------------------------- goals (and preferred companies)

class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["goal", "preferred_company"] = "goal"
    text: str = Field(min_length=1, max_length=300)
    target_date: date | None = None
    status: Literal["active", "achieved", "dropped"] = "active"


class GoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, min_length=1, max_length=300)
    target_date: date | None = None
    status: Literal["active", "achieved", "dropped"] | None = None


@router.get("/goals")
def list_goals(kind: Literal["goal", "preferred_company"] | None = None, user: dict = Depends(get_current_user)) -> dict:
    query: dict = {"user_id": user["_id"]}
    if kind:
        query["kind"] = kind
    return {"goals": [public(d) for d in get_db().career_goals.find(query).sort("created_at", -1).limit(MAX_GOALS)]}


@router.post("/goals", status_code=201)
def create_goal(body: GoalIn, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    if db.career_goals.count_documents({"user_id": user["_id"]}) >= MAX_GOALS:
        raise HTTPException(status_code=409, detail="Goal limit reached. Delete some first.")
    now = utcnow()
    doc = {**body.model_dump(mode="json"), "user_id": user["_id"], "text": body.text.strip(), "created_at": now, "updated_at": now}
    doc["_id"] = db.career_goals.insert_one(doc).inserted_id
    return public(doc)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, body: GoalUpdate, user: dict = Depends(get_current_user)) -> dict:
    goal = get_owned_or_404("career_goals", goal_id, user["_id"])
    changes = body.model_dump(mode="json", exclude_unset=True)
    if "text" in changes:
        changes["text"] = changes["text"].strip()
    if changes:
        changes["updated_at"] = utcnow()
        get_db().career_goals.update_one({"_id": goal["_id"], "user_id": user["_id"]}, {"$set": changes})
    return public(get_db().career_goals.find_one({"_id": goal["_id"]}))


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: str, user: dict = Depends(get_current_user)) -> None:
    goal = get_owned_or_404("career_goals", goal_id, user["_id"], {"_id": 1})
    get_db().career_goals.delete_one({"_id": goal["_id"], "user_id": user["_id"]})


# ---------------------------------------------------------------- skill assessments

class SkillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: str = Field(min_length=1, max_length=60)
    level: int = Field(ge=1, le=5, description="1 = beginner, 5 = expert (your own honest rating)")
    kind: Literal["strength", "gap", "learning"] = "learning"
    evidence: str = Field(default="", max_length=300)


@router.get("/skills")
def list_skills(user: dict = Depends(get_current_user)) -> dict:
    docs = get_db().skill_assessments.find({"user_id": user["_id"]}).sort("updated_at", -1).limit(MAX_SKILLS)
    return {"skills": [public(d, "skill_key") for d in docs]}


@router.post("/skills", status_code=201)
def save_skill(body: SkillIn, user: dict = Depends(get_current_user)) -> dict:
    """Create or update your own rating for a skill (one entry per skill)."""
    db = get_db()
    name = canonical(body.skill)
    key = name.lower()
    now = utcnow()
    existing = db.skill_assessments.find_one({"user_id": user["_id"], "skill_key": key})
    fields = {"skill": name, "skill_key": key, "level": body.level, "kind": body.kind, "evidence": body.evidence.strip(), "source": "manual", "updated_at": now}
    if existing:
        db.skill_assessments.update_one({"_id": existing["_id"], "user_id": user["_id"]}, {"$set": fields})
        return public(db.skill_assessments.find_one({"_id": existing["_id"]}), "skill_key")
    if db.skill_assessments.count_documents({"user_id": user["_id"]}) >= MAX_SKILLS:
        raise HTTPException(status_code=409, detail="Skill assessment limit reached. Delete some first.")
    doc = {**fields, "user_id": user["_id"], "created_at": now}
    doc["_id"] = db.skill_assessments.insert_one(doc).inserted_id
    return public(doc, "skill_key")


@router.delete("/skills/{skill_id}", status_code=204)
def delete_skill(skill_id: str, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("skill_assessments", skill_id, user["_id"], {"_id": 1})
    get_db().skill_assessments.delete_one({"_id": doc["_id"], "user_id": user["_id"]})


# ---------------------------------------------------------------- progress and GitHub

@router.get("/progress")
def progress(user: dict = Depends(get_current_user)) -> dict:
    """Career Progress Tracker: learning, skills, interviews, applications, profile and resume."""
    cand = load_candidate_context(user["_id"], user)
    return career_progress(user["_id"], cand)


@router.get("/github")
def github_analysis(
    request: Request,
    username: str | None = Query(default=None, max_length=39),
    user: dict = Depends(get_current_user),
) -> dict:
    """GitHub Portfolio Analyzer (public data only). Defaults to the GitHub URL in your profile."""
    cand = load_candidate_context(user["_id"], user)
    name = (username or "").strip() or username_from_url(cand["profile"].get("github_url"))
    if not name:
        raise HTTPException(status_code=422, detail="Add your GitHub URL to your profile, or pass ?username=")
    targets = [g["skill"] for g in aggregate_skill_gaps(user["_id"])["gaps"][:8]] + list(cand["skills"])[:15]
    try:
        result = analyze_github(name, targets)
    except GitHubError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    record_task(user["_id"], "career_intelligence", "completed", f"GitHub analysis for {name}")
    log_activity(user["_id"], "github_analyzed", {"username": name}, request)
    return result
