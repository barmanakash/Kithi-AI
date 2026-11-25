from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.applications import ApplicationIn, ApplicationUpdate, StatusIn
from app.services.audit import log_activity
from app.utils.helpers import clamp_limit, get_owned_or_404, public, to_object_id, utcnow

router = APIRouter(prefix="/applications", tags=["applications"])

MAX_APPLICATIONS = 2000
# Statuses where the user is still working on, or waiting for, an outcome.
ACTIVE_STATUSES = {
    "saved", "interested", "preparing", "ready_for_review", "applied",
    "interview_scheduled", "interview_completed", "no_response",
}


def _today() -> str:
    return date.today().isoformat()


def _resolve_resume(user_id, resume_id: str | None) -> dict | None:
    if not resume_id:
        return None
    try:
        return get_owned_or_404("resumes", resume_id, user_id, {"original_filename": 1})
    except HTTPException:
        raise HTTPException(status_code=422, detail="Selected resume was not found")


def _resolve_job(user_id, job_id: str | None) -> dict | None:
    if not job_id:
        return None
    try:
        return get_owned_or_404("jobs", job_id, user_id, {"title": 1, "company": 1, "url": 1})
    except HTTPException:
        raise HTTPException(status_code=422, detail="Selected job was not found")


def _out(doc: dict) -> dict:
    return public(doc)


@router.post("", status_code=201)
def create_application(body: ApplicationIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    if db.applications.count_documents({"user_id": user["_id"]}) >= MAX_APPLICATIONS:
        raise HTTPException(status_code=409, detail=f"Application limit reached ({MAX_APPLICATIONS}).")
    data = body.model_dump(mode="json")
    resume = _resolve_resume(user["_id"], data.pop("resume_id"))
    job = _resolve_job(user["_id"], data.pop("job_id"))

    now = utcnow()
    if data["status"] == "applied" and not data.get("application_date"):
        data["application_date"] = _today()
    doc = {
        "user_id": user["_id"],
        **data,
        "job_id": job["_id"] if job else None,
        "resume_id": resume["_id"] if resume else None,
        "resume_label": resume["original_filename"] if resume else None,
        "status_history": [{"status": data["status"], "at": now, "note": "Created"}],
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = db.applications.insert_one(doc).inserted_id
    log_activity(user["_id"], "application_created", {"application_id": str(doc["_id"])}, request)
    return _out(doc)


@router.post("/from-job/{job_id}")
def create_from_job(job_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Start tracking a saved job. If it is already tracked, the existing application is returned."""
    db = get_db()
    job = get_owned_or_404("jobs", job_id, user["_id"], {"title": 1, "company": 1, "url": 1})
    existing = db.applications.find_one({"user_id": user["_id"], "job_id": job["_id"]})
    if existing:
        return {"created": False, "application": _out(existing)}
    if db.applications.count_documents({"user_id": user["_id"]}) >= MAX_APPLICATIONS:
        raise HTTPException(status_code=409, detail=f"Application limit reached ({MAX_APPLICATIONS}).")
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "company": job["company"],
        "job_title": job["title"],
        "job_url": job.get("url"),
        "job_id": job["_id"],
        "resume_id": None,
        "resume_label": None,
        "status": "saved",
        "application_date": None,
        "follow_up_date": None,
        "recruiter": None,
        "notes": "",
        "cover_note": "",
        "status_history": [{"status": "saved", "at": now, "note": "Saved from job search"}],
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = db.applications.insert_one(doc).inserted_id
    log_activity(user["_id"], "application_created", {"application_id": str(doc["_id"]), "from_job": job_id}, request)
    return {"created": True, "application": _out(doc)}


@router.get("")
def list_applications(
    status: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=500),
    user: dict = Depends(get_current_user),
) -> dict:
    import re

    query: dict = {"user_id": user["_id"]}
    if status:
        query["status"] = status
    if q and q.strip():
        pattern = re.escape(q.strip())
        query["$or"] = [
            {"company": {"$regex": pattern, "$options": "i"}},
            {"job_title": {"$regex": pattern, "$options": "i"}},
        ]
    db = get_db()
    docs = db.applications.find(query, {"status_history": 0}).sort("updated_at", -1).limit(clamp_limit(limit, 1000))
    items = [_out(d) for d in docs]
    return {"total": db.applications.count_documents(query), "applications": items}


@router.get("/timeline")
def timeline(limit: int = Query(default=100), user: dict = Depends(get_current_user)) -> list[dict]:
    """Every status change across all applications, newest first."""
    events = []
    for app in get_db().applications.find({"user_id": user["_id"]}, {"company": 1, "job_title": 1, "status_history": 1}):
        for item in app.get("status_history", []):
            events.append(
                {
                    "application_id": str(app["_id"]),
                    "company": app["company"],
                    "job_title": app["job_title"],
                    "status": item["status"],
                    "note": item.get("note"),
                    "at": item["at"],
                }
            )
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[: clamp_limit(limit, 500)]


@router.get("/{application_id}")
def get_application(application_id: str, user: dict = Depends(get_current_user)) -> dict:
    return _out(get_owned_or_404("applications", application_id, user["_id"]))


def _apply_status(doc: dict, updates: dict, new_status: str, note: str | None) -> None:
    """Record a status change in `updates` (mutates the dict) and return nothing."""
    updates["status"] = new_status
    if new_status == "applied" and not (updates.get("application_date") or doc.get("application_date")):
        updates["application_date"] = _today()


@router.put("/{application_id}")
def update_application(
    application_id: str, body: ApplicationUpdate, request: Request, user: dict = Depends(get_current_user)
) -> dict:
    db = get_db()
    doc = get_owned_or_404("applications", application_id, user["_id"])
    changes = body.model_dump(mode="json", exclude_unset=True)
    for required in ("company", "job_title", "status", "notes", "cover_note"):
        if required in changes and changes[required] is None:
            changes.pop(required)

    updates: dict = {}
    if "resume_id" in changes:
        resume = _resolve_resume(user["_id"], changes.pop("resume_id"))
        updates["resume_id"] = resume["_id"] if resume else None
        updates["resume_label"] = resume["original_filename"] if resume else None
    new_status = changes.pop("status", None)
    updates.update(changes)

    push = None
    if new_status and new_status != doc["status"]:
        _apply_status(doc, updates, new_status, None)
        push = {"status": new_status, "at": utcnow(), "note": "Edited"}
    updates["updated_at"] = utcnow()

    op: dict = {"$set": updates}
    if push:
        op["$push"] = {"status_history": push}
    db.applications.update_one({"_id": doc["_id"], "user_id": user["_id"]}, op)
    log_activity(user["_id"], "application_updated", {"application_id": application_id}, request)
    return _out(db.applications.find_one({"_id": doc["_id"]}))


@router.patch("/{application_id}/status")
def change_status(
    application_id: str, body: StatusIn, request: Request, user: dict = Depends(get_current_user)
) -> dict:
    db = get_db()
    doc = get_owned_or_404("applications", application_id, user["_id"])
    if body.status == doc["status"]:
        return _out(doc)
    updates: dict = {"updated_at": utcnow()}
    _apply_status(doc, updates, body.status, body.note)
    entry = {"status": body.status, "at": utcnow(), "note": (body.note or "").strip() or None}
    db.applications.update_one(
        {"_id": doc["_id"], "user_id": user["_id"]}, {"$set": updates, "$push": {"status_history": entry}}
    )
    log_activity(
        user["_id"], "application_status_changed",
        {"application_id": application_id, "from": doc["status"], "to": body.status}, request,
    )
    return _out(db.applications.find_one({"_id": doc["_id"]}))


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("applications", application_id, user["_id"], {"_id": 1})
    get_db().applications.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "application_deleted", {"application_id": application_id}, request)


@router.post("/{application_id}/quality-check")
def quality_check(application_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Application Quality Checker: validates an application before you submit it. Changes nothing."""
    db = get_db()
    app = get_owned_or_404("applications", application_id, user["_id"])
    checks: list[dict] = []

    def add(key: str, label: str, status: str, detail: str) -> None:
        checks.append({"key": key, "label": label, "status": status, "detail": detail})

    # Resume
    resume = db.resumes.find_one({"_id": app["resume_id"], "user_id": user["_id"]}, {"text": 0}) if app.get("resume_id") else None
    if not resume:
        add("resume", "Resume attached", "fail", "No resume is selected for this application. Choose the version you will submit.")
    else:
        health = ((resume.get("analysis") or {}).get("health_score"))
        if health is None:
            add("resume", "Resume attached", "warn", f"'{resume['original_filename']}' is attached but has not been analyzed. Run Resume Intelligence first.")
        elif health < 60:
            add("resume", "Resume attached", "warn", f"'{resume['original_filename']}' has a health score of {health}/100. Consider improving it first.")
        else:
            add("resume", "Resume attached", "pass", f"'{resume['original_filename']}' (health score {health}/100).")

    # Job link, match and scam signals
    job = db.jobs.find_one({"_id": app["job_id"], "user_id": user["_id"]}, {"description": 0}) if app.get("job_id") else None
    if app.get("job_url"):
        add("job_url", "Job link saved", "pass", "The job URL is recorded so you can re-check the posting.")
    else:
        add("job_url", "Job link saved", "warn", "No job URL. Save it so you can verify the posting and follow up.")

    if job:
        match = db.job_matches.find_one({"user_id": user["_id"], "job_id": job["_id"]})
        if match and match.get("score") is not None:
            missing = [m["skill"] for m in match.get("missing_skills", []) if not m.get("optional")][:6]
            if match["score"] < 35:
                add("match", "Job match", "warn", f"Weak match ({match['score']}/100). Missing required skills: {', '.join(missing) or 'none listed'}.")
            else:
                extra = f" Still missing: {', '.join(missing)}." if missing else ""
                add("match", "Job match", "pass", f"Match score {match['score']}/100 ({match['label']}).{extra}")
        else:
            add("match", "Job match", "warn", "This job has no match score yet. Complete your profile or upload a resume, then re-score.")

        level = job.get("scam_level")
        if level in ("high_concern", "medium_concern"):
            add("scam", "Listing safety", "fail" if level == "high_concern" else "warn",
                f"The scam check flagged this listing ({level.replace('_', ' ')}). Review it on the Scam Detection page and verify the employer before applying.")
        elif level:
            add("scam", "Listing safety", "pass", "No strong warning signs found by the rule-based check. This is not proof the listing is genuine.")
        if job.get("injection_flags"):
            add("injection", "Listing content", "warn", "The posting contains text that looks like instructions aimed at AI tools. It was ignored, but treat the posting with care.")
    else:
        add("match", "Job match", "info", "Not linked to a saved job, so no match or safety data is available.")

    # Application content
    note_len = len((app.get("cover_note") or "").strip())
    if note_len >= 50:
        add("cover_note", "Cover note or answers", "pass", f"{note_len} characters drafted.")
    else:
        add("cover_note", "Cover note or answers", "warn", "No cover note or application answers drafted yet.")

    rec = app.get("recruiter") or {}
    if rec.get("email") or rec.get("linkedin_url") or rec.get("name"):
        add("recruiter", "Recruiter contact", "pass", "Recruiter details are recorded.")
    else:
        add("recruiter", "Recruiter contact", "info", "No recruiter details. Optional, but useful for follow-ups.")

    if app.get("follow_up_date"):
        add("follow_up", "Follow-up date", "pass", f"Follow-up planned for {app['follow_up_date']}.")
    else:
        add("follow_up", "Follow-up date", "info", "No follow-up date set. Many applications get a response only after a nudge.")

    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    scored = [c for c in checks if c["status"] in ("pass", "warn", "fail")]
    percent = round(100 * sum(1 for c in scored if c["status"] == "pass") / len(scored)) if scored else 0
    return {
        "application_id": application_id,
        "ready": not failed,
        "readiness_percent": percent,
        "summary": (
            "Blocking issues found. Fix them before you apply." if failed
            else f"{len(warned)} suggestion(s) to review before you apply." if warned
            else "Looks ready. You decide when to submit."
        ),
        "checks": checks,
    }
