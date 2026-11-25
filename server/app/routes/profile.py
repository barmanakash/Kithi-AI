from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.schemas.profile import CandidateProfileIn
from app.services.audit import log_activity
from app.services.candidate import profile_completeness
from app.utils.helpers import public, utcnow

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
def get_profile(user: dict = Depends(get_current_user)) -> dict:
    doc = get_db().candidate_profiles.find_one({"user_id": user["_id"]})
    if not doc:
        empty = CandidateProfileIn(full_name=user["full_name"]).model_dump(mode="json")
        return {"exists": False, "profile": empty, "completeness": profile_completeness(empty)}
    profile = public(doc)
    return {"exists": True, "profile": profile, "completeness": profile_completeness(profile)}


@router.put("")
def save_profile(body: CandidateProfileIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    data = body.model_dump(mode="json")
    now = utcnow()
    get_db().candidate_profiles.update_one(
        {"user_id": user["_id"]},
        {"$set": {**data, "updated_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    log_activity(user["_id"], "profile_saved", request=request)
    return {"exists": True, "profile": data, "completeness": profile_completeness(data)}


@router.delete("", status_code=204)
def delete_profile(request: Request, user: dict = Depends(get_current_user)) -> None:
    get_db().candidate_profiles.delete_one({"user_id": user["_id"]})
    log_activity(user["_id"], "profile_deleted", request=request)
