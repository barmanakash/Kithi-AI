import logging

from bson import ObjectId
from pymongo.errors import PyMongoError

from app.database.mongo import get_db
from app.utils.helpers import utcnow

logger = logging.getLogger("kithi.tasks")


def record_task(user_id: ObjectId, agent: str, status: str, summary: str | None = None, meta: dict | None = None) -> None:
    """Record an agent run in agent_tasks. Never raises."""
    try:
        get_db().agent_tasks.insert_one(
            {
                "user_id": user_id,
                "agent": agent,
                "status": status,
                "summary": (summary or "")[:300],
                "meta": meta or {},
                "created_at": utcnow(),
            }
        )
    except PyMongoError:
        logger.exception("Could not record agent task for %s", agent)
