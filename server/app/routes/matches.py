"""Job matches API: ranked matches and the user's configurable scoring weights."""
from fastapi import APIRouter, Depends, Query, Request

from app.agents.job_analysis import COMPONENT_LABELS, DEFAULT_WEIGHTS
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.jobs import MatchWeightsIn
from app.services.audit import log_activity
from app.services.job_views import job_out
from app.services.matching import get_weights
from app.utils.helpers import clamp_limit, public

router = APIRouter(prefix="/job-matches", tags=["job-matches"])


def _weights_payload(weights: dict) -> dict:
    return {
        "weights": {k: weights[k] for k in DEFAULT_WEIGHTS},
        "defaults": DEFAULT_WEIGHTS,
        "labels": COMPONENT_LABELS,
    }


@router.get("/weights")
def read_weights(user: dict = Depends(get_current_user)):
    return _weights_payload(get_weights(user))


@router.put("/weights")
def update_weights(body: MatchWeightsIn, request: Request, user: dict = Depends(get_current_user)):
    weights = body.model_dump()
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"settings.match_weights": weights}})
    log_activity(user["_id"], "match_weights.updated", weights, request)
    return _weights_payload({**DEFAULT_WEIGHTS, **weights})


@router.get("")
def list_matches(
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = 50,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    flt: dict = {"user_id": user["_id"]}
    if min_score > 0:
        flt["score"] = {"$gte": min_score}
    total = db.job_matches.count_documents(flt)
    matches = list(
        db.job_matches.find(flt, {"components": 0})
        .sort([("score", -1), ("computed_at", -1)])
        .skip(max(0, skip))
        .limit(clamp_limit(limit, 100))
    )
    jobs = {
        j["_id"]: j
        for j in db.jobs.find({"user_id": user["_id"], "_id": {"$in": [m["job_id"] for m in matches]}})
    }
    items = []
    for match in matches:
        job = jobs.get(match["job_id"])
        if not job:
            continue
        items.append({"match": public(match), "job": job_out(job)})
    return {"total": total, "items": items}
