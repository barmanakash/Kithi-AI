from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.database.mongo import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_prefix}/auth/token")

_UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Invalid or expired credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Return the authenticated user's document. All data access must filter by user['_id']."""
    payload = decode_access_token(token)
    if not payload:
        raise _UNAUTHORIZED
    try:
        user_id = ObjectId(payload["sub"])
    except (KeyError, InvalidId, TypeError):
        raise _UNAUTHORIZED
    user = get_db().users.find_one({"_id": user_id})
    if not user or not user.get("is_active", False):
        raise _UNAUTHORIZED
    return user
