import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.agents.job_discovery import SOURCES, discover
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.jobs import DiscoverIn, JobIn
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.jobs import save_job
from app.services.matching import score_and_store
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public

logger = logging.getLogger("kithi.jobs")

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_JOBS_PER_USER = 2000
MAX_SAVED_PER_DISCOVERY = 100


def _match_summary(match: dict | None) -> dict | None:
    if not match:
        return None
    return {
        "score": match.get("score"),
        "label": match.get("label"),
        "matched_count": len(match.get("matched_skills", [])),
        "missing_count": len(match.get("missing_skills", [])),
        "computed_at": match.get("computed_at"),
    }


def _job_out(job: dict, match: dict | None, include_description: bool = False) -> dict:
    out = public(job, "dedupe_hash")
    if not include_description:
        description = out.pop("description", "") or ""
        out["description_preview"] = description[:280]
    out["match"] = _match_summary(match)
    return out


def _matches_for(user_id, job_ids: list) -> dict:
    if not job_ids:
        return {}
    cursor = get_db().job_matches.find({"user_id": user_id, "job_id": {"$in": job_ids}})
    return {m["job_id"]: m for m in cursor}


@router.get("/sources")
def list_sources(user: dict = Depends(get_current_user)) -> dict:
    """The fixed allow-list of public job-board APIs the discovery agent may use."""
    return {"sources": sorted(SOURCES)}


@router.post("/discover")
def discover_jobs(body: DiscoverIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Fetch jobs from permitted sources, drop duplicates, save them and score them against your profile."""
    db = get_db()
    room = MAX_JOBS_PER_USER - db.jobs.count_documents({"user_id": user["_id"]})
    if room <= 0:
        raise HTTPException(status_code=409, detail=f"Job limit reached ({MAX_JOBS_PER_USER}). Delete some jobs first.")

    found, errors = discover(body.query.strip(), (body.location or "").strip() or None, body.limit, body.sources)
    cand = load_candidate_context(user["_id"], user)

    saved_new = duplicates = scored = 0
    results: list[dict] = []
    for item in found[: min(MAX_SAVED_PER_DISCOVERY, room)]:
        try:
            job, created = save_job(user["_id"], item)
        except Exception:  # one malformed listing must not abort the whole run
            logger.exception("Could not save a discovered job")
            continue
        if not job:
            continue
        saved_new += 1 if created else 0
        duplicates += 0 if created else 1
        match = None
        if created and cand["has_data"]:
            try:
                score_and_store(user, job, cand)
                scored += 1
            except Exception:
                logger.exception("Could not score job %s", job.get("_id"))
        if created:
            match = db.job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
            results.append(_job_out(job, match))

    status = "completed" if not errors else ("partial" if found else "failed")
    record_task(
        user["_id"], "job_discovery", status,
        f"'{body.query}': {saved_new} new, {duplicates} duplicates",
        {"sources": body.sources, "errors": errors},
    )
    log_activity(user["_id"], "jobs_discovered", {"query": body.query, "new": saved_new, "duplicates": duplicates}, request)

    results.sort(key=lambda j: (j["match"] or {}).get("score") or -1, reverse=True)
    return {
        "query": body.query,
        "found": len(found),
        "saved_new": saved_new,
        "duplicates_skipped": duplicates,
        "scored": scored,
        "source_errors": errors,
        "scoring_note": None if cand["has_data"] else "Upload a resume or complete your profile to get match scores.",
        "jobs": results,
    }


@router.post("", status_code=201)
def add_job(body: JobIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Add a job manually (pasted description). Duplicates return the existing job with created=false."""
    db = get_db()
    if db.jobs.count_documents({"user_id": user["_id"]}) >= MAX_JOBS_PER_USER:
        raise HTTPException(status_code=409, detail=f"Job limit reached ({MAX_JOBS_PER_USER}). Delete some jobs first.")
    data = body.model_dump()
    data["url"] = str(body.url) if body.url else None
    data["source"] = "manual"
    job, created = save_job(user["_id"], data)

    cand = load_candidate_context(user["_id"], user)
    if created and cand["has_data"]:
        score_and_store(user, job, cand)
    match = db.job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if created:
        log_activity(user["_id"], "job_added", {"job_id": str(job["_id"])}, request)
    return {"created": created, "job": _job_out(job, match, include_description=True)}


@router.get("")
def list_jobs(
    q: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=30),
    skip: int = Query(default=0, ge=0, le=100000),
    limit: int = Query(default=50),
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_db()
    query: dict = {"user_id": user["_id"]}
    if source:
        query["source"] = source
    if q and q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"company": {"$regex": pattern, "$options": "i"}},
            {"location": {"$regex": pattern, "$options": "i"}},
        ]
    total = db.jobs.count_documents(query)
    docs = list(db.jobs.find(query).sort("created_at", -1).skip(skip).limit(clamp_limit(limit, 100)))
    matches = _matches_for(user["_id"], [d["_id"] for d in docs])
    return {"total": total, "jobs": [_job_out(d, matches.get(d["_id"])) for d in docs]}


@router.get("/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)) -> dict:
    job = get_owned_or_404("jobs", job_id, user["_id"])
    match = get_db().job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    out = _job_out(job, match, include_description=True)
    if match:
        out["match_detail"] = public(match)
    return out


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    job = get_owned_or_404("jobs", job_id, user["_id"], {"_id": 1})
    db = get_db()
    db.jobs.delete_one({"_id": job["_id"], "user_id": user["_id"]})
    db.job_matches.delete_many({"job_id": job["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "job_deleted", {"job_id": job_id}, request)
