import shutil

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.constants import USER_COLLECTIONS
from app.core.security import verify_password
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.utils.helpers import serialize

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/export")
def export_my_data(request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Download everything stored about you (privacy-first: your data is yours)."""
    db = get_db()
    data: dict = {
        "user": {"email": user["email"], "full_name": user["full_name"], "created_at": user["created_at"], "settings": user.get("settings", {})}
    }
    for name in USER_COLLECTIONS:
        data[name] = [serialize(d) for d in db[name].find({"user_id": user["_id"]})]
    log_activity(user["_id"], "data_exported", request=request)
    return data


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(description='Type the exact word "DELETE"')


@router.post("/delete", status_code=204)
def delete_account(body: DeleteAccountRequest, user: dict = Depends(get_current_user)) -> None:
    """Permanently deletes the account, all stored data and uploaded files."""
    if body.confirm != "DELETE":
        raise HTTPException(status_code=422, detail='Type "DELETE" to confirm')
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Password is incorrect")
    db = get_db()
    for name in USER_COLLECTIONS:
        db[name].delete_many({"user_id": user["_id"]})
    db.users.delete_one({"_id": user["_id"]})
    shutil.rmtree(get_settings().upload_path / str(user["_id"]), ignore_errors=True)
