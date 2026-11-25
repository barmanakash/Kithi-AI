"""Resume Generation routes: tailored resumes, bullet rewrites and cover letters.

Everything produced here is a private draft. Nothing is attached to an application, sent or submitted
automatically; the user reviews, edits and decides what to use.
"""
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.agents.resume_generation import (
    generate_cover_letter,
    generate_tailored_resume,
    render_resume_text,
    rewrite_bullets,
)
from app.api.deps import get_current_user
from app.core.prompt_guard import sanitize_untrusted
from app.database.mongo import get_db
from app.schemas.generation import BulletsIn, CoverLetterIn, TailorIn, VersionUpdate
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.docx_export import letter_docx, resume_docx
from app.services.matching import get_weights
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, to_object_id, utcnow
from app.utils.skills import extract_skills

router = APIRouter(prefix="/generate", tags=["generate"])

MAX_VERSIONS = 100
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
FILE_PREFIX = {"tailored_resume": "Resume", "cover_letter": "CoverLetter"}


def _check_capacity(user_id) -> None:
    if get_db().resume_versions.count_documents({"user_id": user_id}) >= MAX_VERSIONS:
        raise HTTPException(status_code=409, detail=f"Saved document limit reached ({MAX_VERSIONS}). Delete some drafts first.")


def _context(user: dict) -> dict:
    ctx = load_candidate_context(user["_id"], user)
    if not ctx["has_data"]:
        raise HTTPException(status_code=422, detail="Upload a resume or complete your candidate profile before generating documents.")
    return ctx


def _save(user: dict, kind: str, job: dict, result: dict, base_resume_id) -> dict:
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "kind": kind,
        "title": f"{job.get('title', '')} - {job.get('company', '')}"[:150],
        "job_id": job["_id"],
        "job_title": job.get("title"),
        "company": job.get("company"),
        "base_resume_id": base_resume_id,
        "content": result["content"],
        "text": result["text"],
        "source": result["source"],  # "ai" = model-written and fact-checked, "template" = verified-facts template
        "ai_error": result["ai_error"],
        "warnings": result["warnings"],
        "removed_sentences": result["removed_sentences"][:20],
        "injection_flags": result["injection_flags"],
        "edited": False,
        "created_at": now,
        "updated_at": now,
    }
    doc["_id"] = get_db().resume_versions.insert_one(doc).inserted_id
    return doc


@router.post("/tailored-resume", status_code=201)
def tailored_resume(body: TailorIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Build a job-specific resume from your verified profile. Reorders and selects; never invents."""
    _check_capacity(user["_id"])
    job = get_owned_or_404("jobs", body.job_id, user["_id"])
    ctx = _context(user)
    result = generate_tailored_resume(ctx, job, get_weights(user), body.improve_bullets)
    doc = _save(user, "tailored_resume", job, result, (ctx.get("resume") or {}).get("_id"))
    record_task(
        user["_id"], "resume_generation", "completed" if result["source"] == "ai" else "partial",
        f"Tailored resume for {job.get('title')}", {"job_id": body.job_id, "version_id": str(doc["_id"])},
    )
    log_activity(user["_id"], "tailored_resume_generated", {"version_id": str(doc["_id"]), "job_id": body.job_id}, request)
    return {"version": public(doc)}


@router.post("/cover-letter", status_code=201)
def cover_letter(body: CoverLetterIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Draft a cover letter. Every AI sentence is fact-checked against your data before it is kept."""
    _check_capacity(user["_id"])
    job = get_owned_or_404("jobs", body.job_id, user["_id"])
    ctx = _context(user)
    result = generate_cover_letter(ctx, job, get_weights(user), body.tone)
    doc = _save(user, "cover_letter", job, result, (ctx.get("resume") or {}).get("_id"))
    record_task(
        user["_id"], "resume_generation", "completed" if result["source"] == "ai" else "partial",
        f"Cover letter for {job.get('title')}", {"job_id": body.job_id, "version_id": str(doc["_id"])},
    )
    log_activity(user["_id"], "cover_letter_generated", {"version_id": str(doc["_id"]), "job_id": body.job_id}, request)
    return {"version": public(doc)}


@router.post("/improve-bullets")
def improve_bullets(body: BulletsIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Suggest clearer wording for your own bullets. Rewrites that add facts are rejected, not returned as accepted."""
    ctx = load_candidate_context(user["_id"], user)
    role_title = (body.target_role or "").strip()
    target_skills: list[str] = []
    if body.job_id:
        job = get_owned_or_404("jobs", body.job_id, user["_id"], {"title": 1, "description": 1})
        role_title = role_title or job.get("title", "")
        target_skills = list(extract_skills(f"{job.get('title', '')}\n{job.get('description', '')}"))
    results = rewrite_bullets(list(body.bullets), role_title or "the target role", target_skills, set(ctx["skills"]))
    accepted = sum(1 for r in results if r["accepted"])
    record_task(user["_id"], "resume_generation", "completed", f"Reworded {accepted} of {len(results)} bullets")
    log_activity(user["_id"], "bullets_improved", {"count": len(results), "accepted": accepted}, request)
    return {"results": results}


@router.get("/versions")
def list_versions(
    kind: str | None = Query(default=None, pattern="^(tailored_resume|cover_letter)$"),
    job_id: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=100),
    user: dict = Depends(get_current_user),
) -> dict:
    query: dict = {"user_id": user["_id"]}
    if kind:
        query["kind"] = kind
    if job_id:
        query["job_id"] = to_object_id(job_id)
    docs = (
        get_db().resume_versions.find(query, {"content": 0, "text": 0, "removed_sentences": 0})
        .sort("created_at", -1)
        .limit(clamp_limit(limit, 100))
    )
    return {"versions": [public(d) for d in docs]}


@router.get("/versions/{version_id}")
def get_version(version_id: str, user: dict = Depends(get_current_user)) -> dict:
    return public(get_owned_or_404("resume_versions", version_id, user["_id"]))


@router.put("/versions/{version_id}")
def update_version(version_id: str, body: VersionUpdate, request: Request, user: dict = Depends(get_current_user)) -> dict:
    doc = get_owned_or_404("resume_versions", version_id, user["_id"])
    updates: dict = {}

    if body.title is not None:
        title = sanitize_untrusted(body.title, 150).strip()
        if not title:
            raise HTTPException(status_code=422, detail="Title must not be blank")
        updates["title"] = title

    if body.summary is not None:
        if doc["kind"] != "tailored_resume":
            raise HTTPException(status_code=422, detail="A summary can only be edited on a tailored resume")
        content = doc["content"]
        content["summary"] = sanitize_untrusted(body.summary, 1000).strip()
        updates["content"] = content
        updates["text"] = render_resume_text(content)
        updates["edited"] = True

    if body.text is not None:
        if doc["kind"] != "cover_letter":
            raise HTTPException(status_code=422, detail="Free text can only be edited on a cover letter")
        text = sanitize_untrusted(body.text, 8000).strip()
        if not text:
            raise HTTPException(status_code=422, detail="The letter must not be blank")
        updates["text"] = text
        updates["edited"] = True

    updates["updated_at"] = utcnow()
    db = get_db()
    db.resume_versions.update_one({"_id": doc["_id"], "user_id": user["_id"]}, {"$set": updates})
    log_activity(user["_id"], "generated_document_edited", {"version_id": version_id}, request)
    return public(db.resume_versions.find_one({"_id": doc["_id"], "user_id": user["_id"]}))


@router.delete("/versions/{version_id}", status_code=204)
def delete_version(version_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("resume_versions", version_id, user["_id"], {"_id": 1})
    get_db().resume_versions.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    log_activity(user["_id"], "generated_document_deleted", {"version_id": version_id}, request)


@router.get("/versions/{version_id}/export")
def export_version(version_id: str, request: Request, user: dict = Depends(get_current_user)) -> Response:
    """Download a draft as a Word document."""
    doc = get_owned_or_404("resume_versions", version_id, user["_id"])
    data = resume_docx(doc["content"]) if doc["kind"] == "tailored_resume" else letter_docx(doc["text"])
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", doc.get("title", "")).strip("_")[:80] or "document"
    filename = f"{FILE_PREFIX.get(doc['kind'], 'Document')}_{stem}.docx"
    log_activity(user["_id"], "generated_document_exported", {"version_id": version_id}, request)
    return Response(
        content=data,
        media_type=DOCX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
