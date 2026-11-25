"""Applications API: tracking, status history, stats and the pre-submission quality check.

Kithi never submits an application. "applied" is recorded only when the user explicitly confirms
that they submitted it themselves.
"""
import re
from datetime import timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_user
from app.core.constants import APPLICATION_STATUSES
from app.database.mongo import get_db
from app.schemas.applications import ApplicationCreate, ApplicationUpdate, StatusChange
from app.services.application_quality import check_application
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.job_views import match_summaries, safe_url
from app.services.matching import score_and_store
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/applications", tags=["applications"])

MAX_APPLICATIONS = 1000
HISTORY_LIMIT = 100
SUBMITTED_STATUSES = ["applied", "interview_scheduled", "interview_completed", "offer_received", "rejected", "no_response"]
INTERVIEW_STATUSES = ["interview_scheduled", "interview_completed"]
ACTIVE_STATUSES = ["applied", "interview_scheduled", "interview_completed"]
CONFIRM_MESSAGE = (
    'Marking an application as "applied" needs your explicit confirmation that you submitted it yourself. '
    "Kithi never submits applications for you."
)


def _ensure_capacity(user_id: ObjectId) -> None:
    if get_db().applications.count_documents({"user_id": user_id}) >= MAX_APPLICATIONS:
        raise HTTPException(status_code=409, detail=f"You have reached the limit of {MAX_APPLICATIONS} applications.")


def _owned_job(user_id: ObjectId, value: str | None) -> ObjectId | None:
    if not value:
        return None
    return get_owned_or_404("jobs", value, user_id, {"_id": 1})["_id"]


def _owned_version(user_id: ObjectId, value: str | None, kind: str) -> ObjectId | None:
    if not value:
        return None
    doc = get_owned_or_404("resume_versions", value, user_id, {"_id": 1, "kind": 1})
    if doc.get("kind") != kind:
        raise HTTPException(status_code=422, detail=f"That document is not a {kind.replace('_', ' ')}.")
    return doc["_id"]


def _out(doc: dict, match: dict | None = None) -> dict:
    out = public(doc)
    out["job_url"] = safe_url(doc.get("job_url"))
    out["job_match"] = match
    return out


def _entry(status: str, note: str | None) -> dict:
    return {"status": status, "at": utcnow(), "note": (note or "").strip()[:500]}


@router.get("/stats")
def stats(user: dict = Depends(get_current_user)):
    db = get_db()
    uid = user["_id"]
    by_status = {s: 0 for s in APPLICATION_STATUSES}
    for row in db.applications.aggregate([{"$match": {"user_id": uid}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]):
        by_status[row["_id"]] = row["n"]
    today = utcnow().date().isoformat()
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "submitted": db.applications.count_documents(
            {"user_id": uid, "$or": [{"applied_at": {"$ne": None}}, {"status": {"$in": SUBMITTED_STATUSES}}]}
        ),
        "pending": by_status["applied"],
        "interviews": sum(by_status[s] for s in INTERVIEW_STATUSES),
        "offers": by_status["offer_received"],
        "rejections": by_status["rejected"],
        "follow_ups_due": db.applications.count_documents(
            {"user_id": uid, "status": {"$in": ACTIVE_STATUSES}, "follow_up_date": {"$ne": None, "$lte": today}}
        ),
    }


@router.get("")
def list_applications(
    status: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=100),
    limit: int = 200,
    skip: int = 0,
    user: dict = Depends(get_current_user),
):
    flt: dict = {"user_id": user["_id"]}
    if status:
        if status not in APPLICATION_STATUSES:
            raise HTTPException(status_code=422, detail="Unknown status")
        flt["status"] = status
    if q and q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        flt["$or"] = [{"company": pattern}, {"job_title": pattern}]
    db = get_db()
    docs = list(db.applications.find(flt).sort("updated_at", -1).skip(max(0, skip)).limit(clamp_limit(limit, 500)))
    job_ids = [d["job_id"] for d in docs if d.get("job_id")]
    matches = match_summaries(user["_id"], job_ids) if job_ids else {}
    return {
        "total": db.applications.count_documents(flt),
        "items": [_out(d, matches.get(d.get("job_id"))) for d in docs],
    }


@router.post("", status_code=201)
def create_application(body: ApplicationCreate, request: Request, user: dict = Depends(get_current_user)):
    if body.status == "applied" and not body.confirmed_by_user:
        raise HTTPException(status_code=422, detail=CONFIRM_MESSAGE)
    _ensure_capacity(user["_id"])
    data = body.model_dump(mode="json")
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "company": data["company"].strip(),
        "job_title": data["job_title"].strip(),
        "job_url": safe_url(data.get("job_url")),
        "job_id": _owned_job(user["_id"], data.get("job_id")),
        "status": data["status"],
        "application_date": data.get("application_date"),
        "resume_version_id": _owned_version(user["_id"], data.get("resume_version_id"), "tailored_resume"),
        "cover_letter_version_id": _owned_version(user["_id"], data.get("cover_letter_version_id"), "cover_letter"),
        "recruiter": data.get("recruiter"),
        "follow_up_date": data.get("follow_up_date"),
        "notes": (data.get("notes") or "").strip(),
        "history": [_entry(data["status"], "Created")],
        "applied_at": now if data["status"] == "applied" else None,
        "created_at": now,
        "updated_at": now,
    }
    if data["status"] == "applied" and not doc["application_date"]:
        doc["application_date"] = now.date().isoformat()
    doc["_id"] = get_db().applications.insert_one(doc).inserted_id
    log_activity(user["_id"], "application.created", {"application_id": str(doc["_id"]), "status": doc["status"]}, request)
    return _out(doc)


@router.post("/from-job/{job_id}")
def create_from_job(job_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Start tracking a saved job. If it is already tracked, the existing application is returned."""
    job = get_owned_or_404("jobs", job_id, user["_id"])
    db = get_db()
    existing = db.applications.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if existing:
        return {"created": False, "application": _out(existing)}
    _ensure_capacity(user["_id"])
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "company": job["company"],
        "job_title": job["title"],
        "job_url": safe_url(job.get("url")),
        "job_id": job["_id"],
        "status": "interested",
        "application_date": None,
        "resume_version_id": None,
        "cover_letter_version_id": None,
        "recruiter": None,
        "follow_up_date": None,
        "notes": "",
        "history": [_entry("interested", "Tracked from a saved job")],
        "applied_at": None,
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = db.applications.insert_one(doc).inserted_id
    log_activity(user["_id"], "application.created", {"application_id": str(doc["_id"]), "from_job": job_id}, request)
    return {"created": True, "application": _out(doc)}


@router.get("/{application_id}")
def get_application(application_id: str, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("applications", application_id, user["_id"])
    match = match_summaries(user["_id"], [doc["job_id"]]).get(doc["job_id"]) if doc.get("job_id") else None
    return _out(doc, match)


@router.put("/{application_id}")
def update_application(application_id: str, body: ApplicationUpdate, request: Request, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("applications", application_id, user["_id"])
    data = body.model_dump(mode="json", exclude_unset=True)
    changes: dict = {}
    for key in ("company", "job_title", "notes"):
        if key in data:
            changes[key] = data[key].strip()
    for key in ("application_date", "follow_up_date", "recruiter"):
        if key in data:
            changes[key] = data[key]
    if "job_url" in data:
        changes["job_url"] = safe_url(data["job_url"])
    if "resume_version_id" in data:
        changes["resume_version_id"] = _owned_version(user["_id"], data["resume_version_id"], "tailored_resume")
    if "cover_letter_version_id" in data:
        changes["cover_letter_version_id"] = _owned_version(user["_id"], data["cover_letter_version_id"], "cover_letter")
    if not changes:
        return _out(doc)
    changes["updated_at"] = utcnow()
    get_db().applications.update_one({"_id": doc["_id"], "user_id": user["_id"]}, {"$set": changes})
    log_activity(user["_id"], "application.updated", {"application_id": application_id, "fields": sorted(changes)}, request)
    return _out(get_db().applications.find_one({"_id": doc["_id"]}))


@router.post("/{application_id}/status")
def change_status(application_id: str, body: StatusChange, request: Request, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("applications", application_id, user["_id"])
    if body.status == "applied" and not body.confirmed_by_user:
        raise HTTPException(status_code=422, detail=CONFIRM_MESSAGE)
    if doc["status"] == body.status:
        return _out(doc)
    now = utcnow()
    sets: dict = {"status": body.status, "updated_at": now}
    if body.status == "applied":
        sets["applied_at"] = doc.get("applied_at") or now
        if not doc.get("application_date"):
            sets["application_date"] = now.date().isoformat()
    get_db().applications.update_one(
        {"_id": doc["_id"], "user_id": user["_id"]},
        {"$set": sets, "$push": {"history": {"$each": [_entry(body.status, body.note)], "$slice": -HISTORY_LIMIT}}},
    )
    log_activity(user["_id"], "application.status", {"application_id": application_id, "from": doc["status"], "to": body.status}, request)
    return _out(get_db().applications.find_one({"_id": doc["_id"]}))


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, request: Request, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("applications", application_id, user["_id"], {"_id": 1})
    get_db().applications.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "application.deleted", {"application_id": application_id}, request)


@router.post("/{application_id}/quality-check")
def quality_check(application_id: str, user: dict = Depends(get_current_user)):
    app = get_owned_or_404("applications", application_id, user["_id"])
    db = get_db()
    cand = load_candidate_context(user["_id"], user)
    job = db.jobs.find_one({"_id": app["job_id"], "user_id": user["_id"]}) if app.get("job_id") else None
    match = None
    if job:
        match = score_and_store(user, job, cand)
    resume_doc = db.resume_versions.find_one({"_id": app["resume_version_id"], "user_id": user["_id"]}) if app.get("resume_version_id") else None
    letter_doc = db.resume_versions.find_one({"_id": app["cover_letter_version_id"], "user_id": user["_id"]}) if app.get("cover_letter_version_id") else None
    return check_application(app, cand, job, match, resume_doc, letter_doc)
