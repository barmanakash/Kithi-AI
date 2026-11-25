from bson import ObjectId

from app.agents.job_analysis import DEFAULT_WEIGHTS, score_job
from app.database.mongo import get_db
from app.utils.helpers import utcnow


def get_weights(user: dict) -> dict:
    stored = (user.get("settings") or {}).get("match_weights") or {}
    return {**DEFAULT_WEIGHTS, **stored}


def score_and_store(user: dict, job: dict, cand: dict) -> dict:
    """Score one job for the user and upsert the result into job_matches.

    Any previously stored AI explanation is cleared because it described the old score.
    """
    result = score_job(job, cand, get_weights(user))
    doc = {
        "user_id": user["_id"],
        "job_id": job["_id"],
        "score": result["score"],
        "label": result["label"],
        "components": result["components"],
        "matched_skills": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "weights": result["weights"],
        "notes": result["notes"],
        "computed_at": utcnow(),
    }
    get_db().job_matches.update_one(
        {"user_id": user["_id"], "job_id": job["_id"]},
        {"$set": doc, "$unset": {"explanation": "", "explanation_at": ""}},
        upsert=True,
    )
    return result


def rescore_all(user: dict, cand: dict, limit: int = 500) -> int:
    """Re-score the user's most recent jobs (e.g. after a profile or weight change)."""
    count = 0
    for job in get_db().jobs.find({"user_id": user["_id"]}).sort("created_at", -1).limit(limit):
        score_and_store(user, job, cand)
        count += 1
    return count
