"""Career Memory Engine.

A single, structured view of what Kithi remembers about the user's career: previous applications,
resume versions, interview feedback, strengths, gaps, goals, preferred companies and learning
progress. The user can review everything here, edit the items they own, delete single items, or
clear whole sections. Nothing is remembered anywhere else, and every query is scoped to the user.
"""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.career_intelligence import aggregate_skill_gaps
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.utils.helpers import get_owned_or_404, public, utcnow

router = APIRouter(prefix="/memory", tags=["memory"])

SectionName = Literal[
    "applications",
    "resume_versions",
    "interview_feedback",
    "career_goals",
    "skill_assessments",
    "learning_plans",
    "company_research",
]
# Section name == MongoDB collection name.
RECENT = 10


def _recent(collection: str, user_id, projection: dict | None = None) -> list[dict]:
    docs = get_db()[collection].find({"user_id": user_id}, projection).sort("created_at", -1).limit(RECENT)
    return [public(d) for d in docs]


@router.get("")
def memory_overview(user: dict = Depends(get_current_user)) -> dict:
    """Everything Kithi remembers about your career, grouped by topic."""
    db = get_db()
    uid = user["_id"]

    status_counts = {row["_id"]: row["n"] for row in db.applications.aggregate([{"$match": {"user_id": uid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    applications = {
        "total": sum(status_counts.values()),
        "by_status": status_counts,
        "recent": [
            {k: v for k, v in public(d).items() if k in ("id", "company", "job_title", "status", "application_date", "updated_at")}
            for d in db.applications.find({"user_id": uid}).sort("updated_at", -1).limit(RECENT)
        ],
    }

    resumes = [
        {
            "id": str(r["_id"]),
            "filename": r.get("original_filename"),
            "is_primary": bool(r.get("is_primary")),
            "health_score": (r.get("analysis") or {}).get("health_score"),
            "created_at": r.get("created_at"),
        }
        for r in db.resumes.find({"user_id": uid}, {"text": 0}).sort("created_at", -1)
    ]
    versions = _recent("resume_versions", uid, {"content": 0, "text": 0, "removed_sentences": 0})

    gaps = aggregate_skill_gaps(uid)
    assessments = [public(d, "skill_key") for d in db.skill_assessments.find({"user_id": uid}).sort("updated_at", -1)]

    plans = []
    for plan in db.learning_plans.find({"user_id": uid}, {"title": 1, "target_role": 1, "created_at": 1, "items.done": 1}).sort("created_at", -1).limit(RECENT):
        items = plan.get("items", [])
        plans.append(
            {
                "id": str(plan["_id"]),
                "title": plan.get("title"),
                "target_role": plan.get("target_role"),
                "done": sum(1 for i in items if i.get("done")),
                "total": len(items),
                "created_at": plan.get("created_at"),
            }
        )

    goals = [public(d) for d in db.career_goals.find({"user_id": uid}).sort("created_at", -1)]
    return {
        "previous_applications": applications,
        "resumes": resumes,
        "resume_versions": versions,
        "interview_feedback": _recent("interview_feedback", uid),
        "technical_strengths": {
            "self_assessed": [a for a in assessments if a.get("kind") == "strength"],
            "seen_in_matching_jobs": gaps["strengths"][:10],
        },
        "skill_gaps": {
            "self_assessed": [a for a in assessments if a.get("kind") == "gap"],
            "seen_in_matching_jobs": gaps["gaps"][:10],
        },
        "learning_progress": {"skills_being_learned": [a for a in assessments if a.get("kind") == "learning"], "plans": plans},
        "career_goals": [g for g in goals if g.get("kind") == "goal"],
        "preferred_companies": [g for g in goals if g.get("kind") == "preferred_company"],
        "company_research": _recent("company_research", uid, {"content": 0, "sources_text": 0}),
        "manage": {
            "delete_one": "DELETE /api/memory/{section}/{id}",
            "edit_goal_or_skill": "PATCH /api/memory/{career_goals|skill_assessments}/{id}",
            "clear_sections": "POST /api/memory/clear",
            "sections": [s for s in SectionName.__args__],
            "note": "Uploaded resume files are managed under /api/resumes. Your profile is managed under /api/profile.",
        },
    }


@router.delete("/{section}/{item_id}", status_code=204)
def delete_item(section: SectionName, item_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404(section, item_id, user["_id"], {"_id": 1})
    get_db()[section].delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "memory_item_deleted", {"section": section, "id": item_id}, request)


class _GoalPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, min_length=1, max_length=300)
    status: Literal["active", "achieved", "dropped"] | None = None
    target_date: date | None = None


class _SkillPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: int | None = Field(default=None, ge=1, le=5)
    kind: Literal["strength", "gap", "learning"] | None = None
    evidence: str | None = Field(default=None, max_length=300)


_PATCH_MODELS = {"career_goals": _GoalPatch, "skill_assessments": _SkillPatch}


@router.patch("/{section}/{item_id}")
def edit_item(
    section: SectionName,
    item_id: str,
    request: Request,
    body: dict = Body(...),
    user: dict = Depends(get_current_user),
) -> dict:
    """Edit a stored goal/preferred company or a skill assessment."""
    model = _PATCH_MODELS.get(section)
    if not model:
        raise HTTPException(status_code=422, detail=f"'{section}' cannot be edited here. You can delete it instead.")
    try:
        changes = model.model_validate(body).model_dump(mode="json", exclude_unset=True)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=[{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()])
    doc = get_owned_or_404(section, item_id, user["_id"])
    if "text" in changes:
        changes["text"] = changes["text"].strip()
    if changes:
        changes["updated_at"] = utcnow()
        get_db()[section].update_one({"_id": doc["_id"], "user_id": user["_id"]}, {"$set": changes})
        log_activity(user["_id"], "memory_item_edited", {"section": section, "id": item_id, "fields": sorted(changes)}, request)
    return public(get_db()[section].find_one({"_id": doc["_id"]}), "skill_key")


class ClearIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[SectionName] = Field(min_length=1)
    confirm: str = Field(description='Type the exact word "CLEAR"')


@router.post("/clear")
def clear_sections(body: ClearIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Permanently delete everything you have stored in the chosen sections."""
    if body.confirm != "CLEAR":
        raise HTTPException(status_code=422, detail='Type "CLEAR" to confirm')
    db = get_db()
    deleted = {}
    for section in dict.fromkeys(body.sections):
        deleted[section] = db[section].delete_many({"user_id": user["_id"]}).deleted_count
    log_activity(user["_id"], "memory_cleared", {"deleted": deleted}, request)
    return {"deleted": deleted}
