import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.database.mongo import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic, _password_rules
from app.services.audit import log_activity
from app.utils.helpers import utcnow

router = APIRouter(prefix="/auth", tags=["auth"])

# Basic brute-force protection: 5 failed attempts per email per 15 minutes (in-memory, single process).
_FAILS: dict[str, list[float]] = {}
_WINDOW_SECONDS = 15 * 60
_MAX_FAILS = 5


def _recent_fails(email: str) -> list[float]:
    cutoff = time.time() - _WINDOW_SECONDS
    _FAILS[email] = [t for t in _FAILS.get(email, []) if t > cutoff]
    return _FAILS[email]


def _public(user: dict) -> UserPublic:
    return UserPublic(id=str(user["_id"]), email=user["email"], full_name=user["full_name"], created_at=user["created_at"])


def _authenticate(email: str, password: str, request: Request) -> TokenResponse:
    email = email.lower().strip()
    if len(_recent_fails(email)) >= _MAX_FAILS:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
    user = get_db().users.find_one({"email": email})
    ok = verify_password(password, user["password_hash"] if user else DUMMY_HASH)
    if not user or not ok or not user.get("is_active", False):
        _FAILS.setdefault(email, []).append(time.time())
        if user:
            log_activity(user["_id"], "login_failed", request=request)
        raise HTTPException(status_code=401, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    _FAILS.pop(email, None)
    log_activity(user["_id"], "login", request=request)
    return TokenResponse(
        access_token=create_access_token(str(user["_id"])),
        expires_in=get_settings().access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(body: RegisterRequest, request: Request) -> UserPublic:
    now = utcnow()
    doc = {
        "email": body.email.lower(),
        "full_name": body.full_name,
        "password_hash": hash_password(body.password),
        "is_active": True,
        "settings": {},
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = get_db().users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    doc["_id"] = result.inserted_id
    log_activity(doc["_id"], "register", request=request)
    return _public(doc)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    return _authenticate(body.email, body.password, request)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def token_form(request: Request, form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2 form login used by the Swagger 'Authorize' button (username = email)."""
    return _authenticate(form.username, form.password, request)


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)) -> UserPublic:
    return _public(user)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=72)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordRequest, request: Request, user: dict = Depends(get_current_user)) -> None:
    try:
        _password_rules(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": utcnow()}},
    )
    log_activity(user["_id"], "password_changed", request=request)
