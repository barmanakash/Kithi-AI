import logging
from typing import Any

from bson import ObjectId
from fastapi import Request
from pymongo.errors import PyMongoError

from app.database.mongo import get_db
from app.utils.helpers import utcnow

logger = logging.getLogger("kithi.audit")


def log_activity(
    user_id: ObjectId,
    action: str,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Write an audit entry. Never raises: auditing must not break the request."""
    try:
        get_db().activity_logs.insert_one(
            {
                "user_id": user_id,
                "action": action,
                "details": details or {},
                "ip": request.client.host if request and request.client else None,
                "created_at": utcnow(),
            }
        )
    except PyMongoError:
        logger.exception("Failed to write audit log for action %s", action)
