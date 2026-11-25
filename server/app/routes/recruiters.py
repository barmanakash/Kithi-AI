"""Recruiter contacts: the people you write to. Messages to them live in recruiter_messages."""
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.deps import get_current_user
from app.core.prompt_guard import sanitize_untrusted
from app.database.mongo import get_db
from app.schemas.recruiter import RecruiterIn, RecruiterUpdate
from app.services.audit import log_activity
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/recruiters", tags=["recruiters"])

MAX_RECRUITERS = 500


def _clean(data: dict) -> dict:
    """Contact details are user-entered, but may be pasted from anywhere, so strip control characters."""
    out = dict(data)
    for key in ("name", "phone", "company", "title"):
        if out.get(key):
            out[key] = sanitize_untrusted(out[key], 200).strip() or None
    if out.get("notes") is not None:
        out["notes"] = sanitize_untrusted(out["notes"], 2000).strip()
    return out


@router.get("")
def list_recruiters(
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=200),
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_db()
    query: dict = {"user_id": user["_id"]}
    if q and q.strip():
        pattern = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"name": pattern}, {"company": pattern}, {"email": pattern}]
    docs = list(db.recruiters.find(query).sort("updated_at", -1).limit(clamp_limit(limit, 500)))

    counts = {
        row["_id"]: row["n"]
        for row in db.recruiter_messages.aggregate(
            [
                {"$match": {"user_id": user["_id"], "recruiter_id": {"$ne": None}}},
                {"$group": {"_id": "$recruiter_id", "n": {"$sum": 1}}},
            ]
        )
    }
    items = []
    for doc in docs:
        item = public(doc)
        item["message_count"] = counts.get(doc["_id"], 0)
        items.append(item)
    return {"total": db.recruiters.count_documents(query), "items": items}


@router.post("", status_code=201)
def create_recruiter(body: RecruiterIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    if db.recruiters.count_documents({"user_id": user["_id"]}) >= MAX_RECRUITERS:
        raise HTTPException(status_code=409, detail=f"You have reached the limit of {MAX_RECRUITERS} contacts.")
    now = utcnow()
    doc = {"user_id": user["_id"], **_clean(body.model_dump(mode="json")), "created_at": now, "updated_at": now}
    doc["_id"] = db.recruiters.insert_one(doc).inserted_id
    log_activity(user["_id"], "recruiter.created", {"recruiter_id": str(doc["_id"])}, request)
    return {**public(doc), "message_count": 0}


@router.get("/{recruiter_id}")
def get_recruiter(recruiter_id: str, user: dict = Depends(get_current_user)) -> dict:
    doc = get_owned_or_404("recruiters", recruiter_id, user["_id"])
    out = public(doc)
    out["message_count"] = get_db().recruiter_messages.count_documents({"user_id": user["_id"], "recruiter_id": doc["_id"]})
    return out


@router.put("/{recruiter_id}")
def update_recruiter(recruiter_id: str, body: RecruiterUpdate, request: Request, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    doc = get_owned_or_404("recruiters", recruiter_id, user["_id"])
    changes = _clean(body.model_dump(mode="json", exclude_unset=True))
    if "name" in changes and not changes["name"]:
        raise HTTPException(status_code=422, detail="Name must not be blank")
    if not changes:
        return public(doc)
    changes["updated_at"] = utcnow()
    db.recruiters.update_one({"_id": doc["_id"], "user_id": user["_id"]}, {"$set": changes})
    log_activity(user["_id"], "recruiter.updated", {"recruiter_id": recruiter_id, "fields": sorted(changes)}, request)
    return public(db.recruiters.find_one({"_id": doc["_id"]}))


@router.delete("/{recruiter_id}", status_code=204)
def delete_recruiter(recruiter_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    """Removes the contact. Existing messages are kept (they store the recipient's name)."""
    doc = get_owned_or_404("recruiters", recruiter_id, user["_id"], {"_id": 1})
    db = get_db()
    db.recruiters.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    db.recruiter_messages.update_many(
        {"user_id": user["_id"], "recruiter_id": doc["_id"]}, {"$set": {"recruiter_id": None}}
    )
    log_activity(user["_id"], "recruiter.deleted", {"recruiter_id": recruiter_id}, request)
