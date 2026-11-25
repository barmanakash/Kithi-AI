"""Scam-detection API. Results are evidence-based concern levels, never a verdict of fraud."""
from fastapi import APIRouter, Depends, Request

from app.agents.scam_detection import assess_text
from app.api.deps import get_current_user
from app.core.prompt_guard import detect_injection, sanitize_untrusted
from app.database.mongo import get_db
from app.schemas.jobs import ScamAssessIn
from app.services.audit import log_activity
from app.services.job_views import safe_url
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/scam", tags=["scam-detection"])

MAX_ASSESSMENTS_PER_USER = 500


def _store(user_id, *, title, company, url, job_id, result, flags, text) -> str:
    db = get_db()
    if db.scam_assessments.count_documents({"user_id": user_id}) >= MAX_ASSESSMENTS_PER_USER:
        oldest = db.scam_assessments.find_one({"user_id": user_id}, {"_id": 1}, sort=[("created_at", 1)])
        if oldest:
            db.scam_assessments.delete_one({"_id": oldest["_id"]})
    inserted = db.scam_assessments.insert_one(
        {
            "user_id": user_id,
            "title": title,
            "company": company,
            "url": url,
            "job_id": job_id,
            "result": result,
            "injection_flags": flags,
            "excerpt": text[:300],
            "created_at": utcnow(),
        }
    )
    return str(inserted.inserted_id)


@router.post("/assess")
def assess(body: ScamAssessIn, request: Request, user: dict = Depends(get_current_user)):
    text = sanitize_untrusted(body.text, 30000)
    url = safe_url(str(body.url)) if body.url else None
    company = body.company.strip() if body.company else None
    result = assess_text(text, company=company, url=url, contact_email=body.contact_email)
    flags = detect_injection(text)
    assessment_id = None
    if body.save:
        assessment_id = _store(
            user["_id"],
            title=(body.title or "").strip() or None,
            company=company,
            url=url,
            job_id=None,
            result=result,
            flags=flags,
            text=text,
        )
    record_task(user["_id"], "scam_detection", "completed", f"{result['risk_level']} ({result['concern_score']})")
    log_activity(user["_id"], "scam.assess", {"risk_level": result["risk_level"], "saved": body.save}, request)
    return {"id": assessment_id, "injection_flags": flags, **result}


@router.post("/jobs/{job_id}")
def assess_saved_job(job_id: str, request: Request, user: dict = Depends(get_current_user)):
    job = get_owned_or_404("jobs", job_id, user["_id"])
    result = assess_text(job.get("description", ""), company=job.get("company"), url=safe_url(job.get("url")))
    flags = job.get("injection_flags") or detect_injection(job.get("description", ""))
    assessment_id = _store(
        user["_id"],
        title=job.get("title"),
        company=job.get("company"),
        url=safe_url(job.get("url")),
        job_id=job["_id"],
        result=result,
        flags=flags,
        text=job.get("description", ""),
    )
    record_task(user["_id"], "scam_detection", "completed", f"job {job_id}: {result['risk_level']}")
    log_activity(user["_id"], "scam.assess_job", {"job_id": job_id, "risk_level": result["risk_level"]}, request)
    return {"id": assessment_id, "injection_flags": flags, **result}


@router.get("/assessments")
def list_assessments(limit: int = 50, skip: int = 0, user: dict = Depends(get_current_user)):
    db = get_db()
    flt = {"user_id": user["_id"]}
    docs = list(db.scam_assessments.find(flt).sort("created_at", -1).skip(max(0, skip)).limit(clamp_limit(limit, 100)))
    return {"total": db.scam_assessments.count_documents(flt), "items": [public(d) for d in docs]}


@router.delete("/assessments/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: str, request: Request, user: dict = Depends(get_current_user)):
    doc = get_owned_or_404("scam_assessments", assessment_id, user["_id"], {"_id": 1})
    get_db().scam_assessments.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "scam.deleted", {"assessment_id": assessment_id}, request)
