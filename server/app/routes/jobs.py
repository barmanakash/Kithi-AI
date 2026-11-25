"""Jobs API: manual add, discovery from permitted sources, listing, scoring and explanations."""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pymongo.errors import PyMongoError

from app.agents.job_analysis import explain_match
from app.agents.job_discovery import discover
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.jobs import DiscoverIn, JobIn
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.job_views import job_out, match_summaries, safe_url
from app.services.jobs import save_job
from app.services.matching import rescore_all, score_and_store
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

logger = logging.getLogger("kithi.jobs")
router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_JOBS_PER_USER = 2000


def _ensure_capacity(user_id) -> None:
    if get_db().jobs.count_documents({"user_id": user_id}) >= MAX_JOBS_PER_USER:
        raise HTTPException(status_code=409, detail=f"You have reached the limit of {MAX_JOBS_PER_USER} saved jobs. Delete some first.")


def _summary(result: dict | None) -> dict | None:
    return {"score": result["score"], "label": result["label"]} if result else None


@router.get("")
def list_jobs(
    q: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=30),
    limit: int = 25,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    flt: dict = {"user_id": user["_id"]}
    if q and q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"title": pattern}, {"company": pattern}]
    if source:
        flt["source"] = source
    db = get_db()
    total = db.jobs.count_documents(flt)
    docs = list(db.jobs.find(flt).sort("created_at", -1).skip(max(0, skip)).limit(clamp_limit(limit, 100)))
    matches = match_summaries(user["_id"], [d["_id"] for d in docs])
    return {"total": total, "items": [job_out(d, matches.get(d["_id"])) for d in docs]}


@router.post("", status_code=201)
def create_job(body: JobIn, request: Request, user: dict = Depends(get_current_user)):
    _ensure_capacity(user["_id"])
    data = body.model_dump(mode="json")
    doc, created = save_job(user["_id"], data)
    if not doc:
        raise HTTPException(status_code=500, detail="The job could not be saved")
    cand = load_candidate_context(user["_id"], user)
    result = score_and_store(user, doc, cand)
    if created:
        log_activity(user["_id"], "job.created", {"job_id": str(doc["_id"]), "source": "manual"}, request)
    return {"created": created, "job": job_out(doc, _summary(result), full=True)}


@router.post("/discover")
def discover_jobs(body: DiscoverIn, request: Request, user: dict = Depends(get_current_user)):
    found, errors = discover(
        body.query.strip(),
        (body.location or "").strip() or None,
        body.limit,
        list(dict.fromkeys(body.sources)),
    )
    cand = load_candidate_context(user["_id"], user)
    saved = duplicates = 0
    items: list[dict] = []
    at_capacity = False

    for item in found:
        item["url"] = safe_url(item.get("url"))
        item["salary_text"] = (str(item["salary_text"])[:100] if item.get("salary_text") else None)
        item["job_type"] = (str(item["job_type"])[:40] if item.get("job_type") else None)
        try:
            _ensure_capacity(user["_id"])
            doc, created = save_job(user["_id"], item)
        except HTTPException:
            at_capacity = True
            break
        except PyMongoError:
            logger.exception("Could not save discovered job")
            continue
        if not doc:
            continue
        saved += 1 if created else 0
        duplicates += 0 if created else 1
        result = score_and_store(user, doc, cand)
        items.append(job_out(doc, _summary(result)))

    items.sort(key=lambda j: (j["match"]["score"] is None, -(j["match"]["score"] or 0)))
    all_failed = bool(errors) and not found
    record_task(
        user["_id"],
        "job_discovery",
        "failed" if all_failed else ("partial" if errors else "completed"),
        f"query='{body.query[:60]}' found={len(found)} saved={saved} duplicates={duplicates}",
        {"errors": errors},
    )
    log_activity(user["_id"], "jobs.discover", {"query": body.query[:100], "found": len(found), "saved": saved}, request)
    return {
        "query": body.query,
        "found": len(found),
        "saved": saved,
        "duplicates": duplicates,
        "errors": errors,
        "at_capacity": at_capacity,
        "scored": cand["has_data"],
        "items": items,
    }


@router.post("/rescore-all")
def rescore_everything(request: Request, user: dict = Depends(get_current_user)):
    cand = load_candidate_context(user["_id"], user)
    count = rescore_all(user, cand)
    log_activity(user["_id"], "jobs.rescore_all", {"count": count}, request)
    return {"rescored": count, "has_candidate_data": cand["has_data"]}


@router.get("/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("jobs", job_id, user["_id"])
    match = get_db().job_matches.find_one({"user_id": user["_id"], "job_id": doc["_id"]})
    return {"job": job_out(doc, full=True), "match": public(match) if match else None}


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, request: Request, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("jobs", job_id, user["_id"], {"_id": 1})
    db = get_db()
    db.job_matches.delete_many({"user_id": user["_id"], "job_id": doc["_id"]})
    db.scam_assessments.delete_many({"user_id": user["_id"], "job_id": doc["_id"]})
    db.jobs.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "job.deleted", {"job_id": job_id}, request)


@router.post("/{job_id}/score")
def rescore_job(job_id: str, user: dict = Depends(get_current_user)):
    job = get_owned_or_404("jobs", job_id, user["_id"])
    cand = load_candidate_context(user["_id"], user)
    return score_and_store(user, job, cand)


@router.post("/{job_id}/explain")
def explain_job_match(job_id: str, request: Request, user: dict = Depends(get_current_user)):
    job = get_owned_or_404("jobs", job_id, user["_id"])
    cand = load_candidate_context(user["_id"], user)
    result = score_and_store(user, job, cand)  # always explain the current facts
    if result["score"] is None:
        raise HTTPException(status_code=409, detail="Not enough data to explain this match. Upload a resume or complete your profile first.")
    text, error = explain_match(job, result)
    if text:
        get_db().job_matches.update_one(
            {"user_id": user["_id"], "job_id": job["_id"]},
            {"$set": {"explanation": text, "explanation_at": utcnow()}},
        )
    record_task(user["_id"], "job_analysis", "completed" if text else "failed", f"explain job {job_id}", {"ai_error": error})
    log_activity(user["_id"], "job.explain", {"job_id": job_id, "ai": bool(text)}, request)
    return {"explanation": text, "ai_error": error}
