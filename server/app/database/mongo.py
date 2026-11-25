import logging

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import get_settings
from app.core.constants import ALL_COLLECTIONS, APPLICATION_STATUSES

logger = logging.getLogger("kithi.db")

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = MongoClient(settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=3000)
    return _client


def get_db() -> Database:
    return get_client()[get_settings().mongodb_db]


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except PyMongoError:
        return False


def _schema(required: list[str], properties: dict) -> dict:
    return {"$jsonSchema": {"bsonType": "object", "required": required, "properties": properties}}


VALIDATORS = {
    "users": _schema(
        ["email", "password_hash", "is_active", "created_at"],
        {
            "email": {"bsonType": "string"},
            "password_hash": {"bsonType": "string"},
            "is_active": {"bsonType": "bool"},
            "created_at": {"bsonType": "date"},
        },
    ),
    "candidate_profiles": _schema(["user_id"], {"user_id": {"bsonType": "objectId"}}),
    "resumes": _schema(
        ["user_id", "text", "file_type"],
        {
            "user_id": {"bsonType": "objectId"},
            "text": {"bsonType": "string"},
            "file_type": {"enum": ["pdf", "docx"]},
        },
    ),
    "jobs": _schema(
        ["user_id", "title", "company"],
        {
            "user_id": {"bsonType": "objectId"},
            "title": {"bsonType": "string"},
            "company": {"bsonType": "string"},
        },
    ),
    "applications": _schema(
        ["user_id", "company", "job_title", "status"],
        {
            "user_id": {"bsonType": "objectId"},
            "company": {"bsonType": "string"},
            "job_title": {"bsonType": "string"},
            "status": {"enum": APPLICATION_STATUSES},
        },
    ),
}

# (keys, options) per collection. Collections not listed get a plain user_id index.
INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "users": [([("email", 1)], {"unique": True})],
    "candidate_profiles": [([("user_id", 1)], {"unique": True})],
    "resumes": [([("user_id", 1), ("created_at", -1)], {})],
    "jobs": [
        ([("user_id", 1), ("created_at", -1)], {}),
        (
            [("user_id", 1), ("dedupe_hash", 1)],
            {"unique": True, "partialFilterExpression": {"dedupe_hash": {"$type": "string"}}},
        ),
    ],
    "job_matches": [([("user_id", 1), ("job_id", 1)], {"unique": True})],
    "resume_versions": [([("user_id", 1), ("kind", 1), ("created_at", -1)], {})],
    "applications": [
        ([("user_id", 1), ("status", 1)], {}),
        ([("user_id", 1), ("follow_up_date", 1)], {}),
    ],
    "recruiters": [([("user_id", 1), ("updated_at", -1)], {})],
    "recruiter_messages": [
        ([("user_id", 1), ("status", 1), ("updated_at", -1)], {}),
        ([("user_id", 1), ("recruiter_id", 1)], {}),
    ],
    "agent_tasks": [([("user_id", 1), ("status", 1), ("created_at", -1)], {})],
    "activity_logs": [([("user_id", 1), ("created_at", -1)], {})],
}


def init_db() -> None:
    """Create collections, validators and indexes. Safe to run on every startup."""
    db = get_db()
    existing = set(db.list_collection_names())

    for name in ALL_COLLECTIONS:
        validator = VALIDATORS.get(name)
        if name not in existing:
            if validator:
                db.create_collection(
                    name, validator=validator, validationLevel="moderate", validationAction="error"
                )
            else:
                db.create_collection(name)
        elif validator:
            db.command(
                "collMod", name, validator=validator, validationLevel="moderate", validationAction="error"
            )

        specs = INDEXES.get(name)
        if specs is None and name != "users":
            specs = [([("user_id", 1)], {})]
        for keys, options in specs or []:
            db[name].create_index(keys, **options)

    logger.info("MongoDB ready: %d collections verified", len(ALL_COLLECTIONS))
