from fastapi import APIRouter, Depends, Query, Request

from app.agents.scam_detection import assess_text
from app.api.deps import get_current_user
from app.core.prompt_guard import sanitize_untrusted
from app.database.mongo import get_db
from app.schemas.jobs import ScamCheckIn
from app.services.audit import log_activity
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/scam", tags=["scam-detection"])

MAX_ASSESSMENTS = 500


@router.post("/assess", status_code=201)
def assess(body: ScamCheckIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Rule-based check with evidence for every signal. Reports concern levels, never a verdict."""
    db = get_db()
    job = None
    if body.job_id:
        job = get_owned_or_404("jobs", body.job_id, user["_id"])

    text = sanitize_untrusted(body.text or (job or {}).get("description", ""), 30000)
    company = (body.company or (job or {}).get("company") or "").strip() or None
    url = str(body.url) if body.url else (job or {}).get("url")

    result = assess_text(text, company=company, url=url, contact_email=body.contact_email)

    doc = {
        "user_id": user["_id"],
        "job_id": job["_id"] if job else None,
        "company": company,
        "title": (job or {}).get("title"),
        "url": url,
        "excerpt": " ".join(text.split())[:400],
        "risk_level": result["risk_level"],
        "concern_score": result["concern_score"],
        "confidence": result["confidence"],
        "signals": result["signals"],
        "created_at": utcnow(),
    }
    if db.scam_assessments.count_documents({"user_id": user["_id"]}) >= MAX_ASSESSMENTS:
        oldest = db.scam_assessments.find_one({"user_id": user["_id"]}, {"_id": 1}, sort=[("created_at", 1)])
        if oldest:
            db.scam_assessments.delete_one({"_id": oldest["_id"]})
    inserted = db.scam_assessments.insert_one(doc)

    if job:
        db.jobs.update_one(
            {"_id": job["_id"], "user_id": user["_id"]},
            {"$set": {"scam_level": result["risk_level"], "scam_score": result["concern_score"]}},
        )

    record_task(user["_id"], "scam_detection", "completed", f"{result['risk_level']} ({result['concern_score']})")
    log_activity(user["_id"], "scam_assessed", {"assessment_id": str(inserted.inserted_id), "level": result["risk_level"]}, request)
    return {"id": str(inserted.inserted_id), "job_id": body.job_id, "company": company, **result}


@router.get("/assessments")
def list_assessments(limit: int = Query(default=50), user: dict = Depends(get_current_user)) -> list[dict]:
    docs = get_db().scam_assessments.find({"user_id": user["_id"]}).sort("created_at", -1).limit(clamp_limit(limit, 200))
    return [public(d) for d in docs]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, user: dict = Depends(get_current_user)) -> dict:
    return public(get_owned_or_404("scam_assessments", assessment_id, user["_id"]))


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("scam_assessments", assessment_id, user["_id"], {"_id": 1})
    get_db().scam_assessments.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "scam_assessment_deleted", {"assessment_id": assessment_id}, request)
