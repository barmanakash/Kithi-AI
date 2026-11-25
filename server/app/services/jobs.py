import hashlib
import re

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.agents.scam_detection import assess_text
from app.core.prompt_guard import detect_injection, sanitize_untrusted
from app.database.mongo import get_db
from app.utils.helpers import utcnow


def dedupe_hash(company: str, title: str, location: str | None) -> str:
    def norm(value: str | None) -> str:
        return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()

    raw = f"{norm(company)}|{norm(title)}|{norm(location)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_job(user_id: ObjectId, data: dict) -> tuple[dict, bool]:
    """Insert a job for the user. Returns (job_document, created). Duplicates return the existing job."""
    db = get_db()
    description = sanitize_untrusted(data["description"], 30000)
    scam = assess_text(description, company=data["company"], url=data.get("url"))
    doc = {
        "user_id": user_id,
        "title": data["title"].strip()[:200],
        "company": data["company"].strip()[:200],
        "location": (data.get("location") or "").strip()[:200] or None,
        "remote": bool(data.get("remote")),
        "job_type": data.get("job_type"),
        "url": data.get("url"),
        "salary_text": data.get("salary_text"),
        "description": description,
        "source": data.get("source", "manual"),
        "source_id": data.get("source_id"),
        "posted_at": data.get("posted_at"),
        "injection_flags": detect_injection(description),
        "scam_level": scam["risk_level"],
        "scam_score": scam["concern_score"],
        "dedupe_hash": dedupe_hash(data["company"], data["title"], data.get("location")),
        "created_at": utcnow(),
    }
    try:
        result = db.jobs.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc, True
    except DuplicateKeyError:
        existing = db.jobs.find_one({"user_id": user_id, "dedupe_hash": doc["dedupe_hash"]})
        return existing, False
