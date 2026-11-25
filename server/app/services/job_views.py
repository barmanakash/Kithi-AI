from bson import ObjectId

from app.database.mongo import get_db
from app.utils.helpers import public

EXCERPT_CHARS = 280


def safe_url(value: str | None) -> str | None:
    """Job URLs come from untrusted sources. Only plain http(s) links are ever passed on."""
    if value and str(value).lower().startswith(("http://", "https://")):
        return str(value)[:2000]
    return None


def match_summaries(user_id: ObjectId, job_ids: list[ObjectId]) -> dict[ObjectId, dict]:
    rows = get_db().job_matches.find(
        {"user_id": user_id, "job_id": {"$in": job_ids}}, {"score": 1, "label": 1, "job_id": 1}
    )
    return {row["job_id"]: {"score": row.get("score"), "label": row.get("label")} for row in rows}


def job_out(doc: dict, match: dict | None = None, full: bool = False) -> dict:
    """Serialize a job for the API. Lists get a short excerpt; detail views get the full description."""
    out = public(doc, "dedupe_hash")
    out["url"] = safe_url(doc.get("url"))
    description = doc.get("description") or ""
    if not full:
        out.pop("description", None)
        out["excerpt"] = description[:EXCERPT_CHARS] + ("..." if len(description) > EXCERPT_CHARS else "")
    out["match"] = match
    return out
