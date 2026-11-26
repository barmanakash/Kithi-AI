"""Company Research routes. Public information only; one saved record per company per user."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pymongo import ReturnDocument

from app.agents.company_research import build_research, collect_pages
from app.api.deps import get_current_user
from app.core.prompt_guard import sanitize_untrusted
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.safe_fetch import UnsafeURLError
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/company-research", tags=["company-research"])

MAX_RECORDS = 100
CONTENT_KEYS = (
    "overview", "products_services", "technologies", "strengths_to_highlight", "gaps_to_prepare",
    "interview_topics",
)


class ResearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=100)
    website: HttpUrl | None = None
    job_id: str | None = Field(default=None, max_length=24)


@router.post("")
def research(body: ResearchIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Research a company from its public website and the jobs you saved for it. Re-running refreshes the record."""
    db = get_db()
    uid = user["_id"]
    job = get_owned_or_404("jobs", body.job_id, uid) if body.job_id else None
    company = sanitize_untrusted(body.company or (job or {}).get("company") or "", 100).strip()
    if not company:
        raise HTTPException(status_code=422, detail="Enter a company name or choose a saved job.")
    key = company.lower()

    existing = db.company_research.find_one({"user_id": uid, "company_key": key}, {"_id": 1})
    if not existing and db.company_research.count_documents({"user_id": uid}) >= MAX_RECORDS:
        raise HTTPException(status_code=409, detail=f"Research limit reached ({MAX_RECORDS}). Delete an old record first.")

    website = str(body.website) if body.website else None
    pages, fetch_warnings = [], []
    if website:
        try:
            pages, fetch_warnings = collect_pages(website)
        except UnsafeURLError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    pattern = {"$regex": f"^\\s*{re.escape(company)}\\s*$", "$options": "i"}
    job_texts = [
        f"{j.get('title', '')}\n{j.get('description', '')}"
        for j in db.jobs.find({"user_id": uid, "company": pattern}, {"title": 1, "description": 1}).limit(30)
    ]
    if not pages and not job_texts:
        detail = "Add the company's website, or save a job at this company first, so there is something to research."
        raise HTTPException(status_code=422, detail=" ".join([*fetch_warnings, detail]))

    cand = load_candidate_context(uid, user)
    result = build_research(company, pages, job_texts, set(cand["skills"]))
    result["warnings"] = fetch_warnings + result["warnings"]
    if not cand["has_data"]:
        result["warnings"].append("Your profile and resume are empty, so every technology is shown as a gap. Add them for a useful comparison.")

    now = utcnow()
    fields = {
        "company": company,
        "website": website,
        "job_id": job["_id"] if job else None,
        "content": {k: result[k] for k in CONTENT_KEYS},
        "sources": result["sources"],
        "source_kind": result["source_kind"],
        "jobs_used": result["jobs_used"],
        "ai_used": result["ai_used"],
        "ai_error": result["ai_error"],
        "injection_flags": result["injection_flags"],
        "warnings": result["warnings"],
        "limits": result["limits"],
        "updated_at": now,
    }
    doc = db.company_research.find_one_and_update(
        {"user_id": uid, "company_key": key},
        {"$set": fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    record_task(uid, "company_research", "completed", f"Researched {company}", {"source_kind": result["source_kind"]})
    log_activity(uid, "company_researched", {"company": company, "sources": len(result["sources"])}, request)
    return public(doc)


@router.get("")
def list_research(limit: int = 100, user: dict = Depends(get_current_user)) -> dict:
    docs = (
        get_db().company_research.find({"user_id": user["_id"]}, {"content": 0})
        .sort("updated_at", -1)
        .limit(clamp_limit(limit, 200))
    )
    return {"items": [public(d) for d in docs]}


@router.get("/{research_id}")
def get_research(research_id: str, user: dict = Depends(get_current_user)) -> dict:
    return public(get_owned_or_404("company_research", research_id, user["_id"]))


@router.delete("/{research_id}", status_code=204)
def delete_research(research_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("company_research", research_id, user["_id"], {"_id": 1})
    get_db().company_research.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "company_research_deleted", {"id": research_id}, request)
