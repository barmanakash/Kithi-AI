from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException

from app.database.mongo import get_db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=404, detail="Resource not found")


def serialize(value: Any) -> Any:
    """Convert Mongo documents into JSON-friendly data (ObjectId -> str, _id -> id)."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {("id" if k == "_id" else k): serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def public(doc: dict, *drop: str) -> dict:
    """Serialize a document for API output, removing user_id and any extra keys."""
    out = serialize(doc)
    out.pop("user_id", None)
    for key in drop:
        out.pop(key, None)
    return out


def get_owned_or_404(collection: str, doc_id: str, user_id: ObjectId, projection: dict | None = None) -> dict:
    """Fetch a document only if it belongs to the user. Enforces user-level data isolation."""
    doc = get_db()[collection].find_one({"_id": to_object_id(doc_id), "user_id": user_id}, projection)
    if not doc:
        raise HTTPException(status_code=404, detail="Resource not found")
    return doc


def clamp_limit(limit: int, maximum: int = 200) -> int:
    return max(1, min(limit, maximum))
