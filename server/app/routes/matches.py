import logging

from fastapi import APIRouter, Depends, Query, Request

from app.agents.job_analysis import DEFAULT_WEIGHTS, explain_match
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.jobs import WeightsIn
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.matching import get_weights, score_and_store
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public

logger = logging.getLogger("kithi.matches")

router = APIRouter(prefix="/job-matches", tags=["job-matches"])

MAX_RESCORE = 500


def _rescore_all(user: dict) -> dict:
    """Re-score the user's most recent jobs with the current weights. Deterministic and fast."""
    db = get_db()
    cand = load_candidate_context(user["_id"], user)
    if not cand["has_data"]:
        return {"rescored": 0, "note": "Upload a resume or complete your profile to get match scores."}
    jobs = db.jobs.find({"user_id": user["_id"]}).sort("created_at", -1).limit(MAX_RESCORE)
    count = 0
    for job in jobs:
        try:
            score_and_store(user, job, cand)
            count += 1
        except Exception:
            logger.exception("Could not score job %s", job.get("_id"))
    return {"rescored": count, "note": None}


@router.get("/weights")
def read_weights(user: dict = Depends(get_current_user)) -> dict:
    return {"weights": get_weights(user), "defaults": DEFAULT_WEIGHTS}


@router.put("/weights")
def update_weights(body: WeightsIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Save your match weights and re-score existing jobs so the ranking reflects them immediately."""
    weights = body.model_dump()
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"settings.match_weights": weights}})
    user.setdefault("settings", {})["match_weights"] = weights
    result = _rescore_all(user)
    log_activity(user["_id"], "match_weights_updated", {"weights": weights}, request)
    return {"weights": weights, **result}


@router.post("/recompute")
def recompute(user: dict = Depends(get_current_user)) -> dict:
    """Re-score all saved jobs, for example after updating your profile or resume."""
    result = _rescore_all(user)
    record_task(user["_id"], "job_analysis", "completed", f"Re-scored {result['rescored']} jobs")
    return result


@router.get("")
def list_matches(
    min_score: int | None = Query(default=None, ge=0, le=100),
    label: str | None = Query(default=None, pattern="^(strong|good|partial|weak|unknown)$"),
    limit: int = Query(default=50),
    user: dict = Depends(get_current_user),
) -> dict:
    """Ranked opportunities, best match first. Unscorable jobs (not enough data) are listed last."""
    db = get_db()
    query: dict = {"user_id": user["_id"]}
    if min_score is not None:
        query["score"] = {"$gte": min_score}
    if label:
        query["label"] = label
    matches = list(db.job_matches.find(query).sort("score", -1).limit(clamp_limit(limit, 200)))

    jobs = {
        j["_id"]: j
        for j in db.jobs.find(
            {"user_id": user["_id"], "_id": {"$in": [m["job_id"] for m in matches]}},
            {"description": 0, "dedupe_hash": 0},
        )
    }
    items = []
    for match in matches:
        job = jobs.get(match["job_id"])
        if not job:  # job was deleted; skip orphaned match
            continue
        items.append(
            {
                "job": public(job),
                "score": match.get("score"),
                "label": match.get("label"),
                "matched_skills": [m["skill"] for m in match.get("matched_skills", [])],
                "missing_skills": [m["skill"] for m in match.get("missing_skills", [])],
                "computed_at": match.get("computed_at"),
            }
        )
    return {"total": len(items), "weights": get_weights(user), "matches": items}


@router.get("/{job_id}")
def match_detail(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Full evidence for one match: every component with weight, score, detail and evidence."""
    job = get_owned_or_404("jobs", job_id, user["_id"], {"description": 0, "dedupe_hash": 0})
    match = get_db().job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if not match:
        match = _score_one(user, job_id)
    return {"job": public(job), "match": public(match, "job_id")}


def _score_one(user: dict, job_id: str) -> dict:
    job = get_owned_or_404("jobs", job_id, user["_id"])
    cand = load_candidate_context(user["_id"], user)
    score_and_store(user, job, cand)
    return get_db().job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})


@router.post("/{job_id}/score")
def score_job_now(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    match = _score_one(user, job_id)
    return {"match": public(match, "job_id")}


@router.post("/{job_id}/explain")
def explain(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Optional plain-language summary from the local model, written only from the computed facts."""
    job = get_owned_or_404("jobs", job_id, user["_id"])
    match = get_db().job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if not match:
        match = _score_one(user, job_id)
    text, error = explain_match(job, match)
    record_task(
        user["_id"], "job_analysis", "completed" if text else "failed",
        f"Explained match for {job.get('title')}", {"job_id": job_id},
    )
    return {"explanation": text, "ai_error": error}
