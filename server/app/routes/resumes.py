import hashlib
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.agents.resume_intelligence import analyze_resume
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.services.resume_parser import ResumeParseError, parse_resume
from app.services.tasks import record_task
from app.utils.helpers import get_owned_or_404, public, utcnow

router = APIRouter(prefix="/resumes", tags=["resumes"])

ALLOWED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}
MAX_RESUMES = 20


def _display_name(name: str | None) -> str:
    base = Path((name or "resume").replace("\\", "/")).name
    base = re.sub(r"[^\w.\- ]", "_", base)[:120]
    return base or "resume"


def _out(doc: dict, include_text: bool = False) -> dict:
    out = public(doc, "stored_filename")
    if not include_text:
        out.pop("text", None)
    return out


def _file_path(user_id, stored_filename: str) -> Path:
    return get_settings().upload_path / str(user_id) / stored_filename


@router.post("/upload", status_code=201)
def upload_resume(request: Request, file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> dict:
    settings = get_settings()
    db = get_db()
    name = _display_name(file.filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX files are allowed")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB")
    if db.resumes.count_documents({"user_id": user["_id"]}) >= MAX_RESUMES:
        raise HTTPException(status_code=409, detail=f"Resume limit reached ({MAX_RESUMES}). Delete one first.")

    file_type = ALLOWED_EXTENSIONS[ext]
    try:
        parsed = parse_resume(data, file_type)
    except ResumeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    stored_filename = f"{uuid.uuid4().hex}{ext}"
    path = _file_path(user["_id"], stored_filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    first = db.resumes.count_documents({"user_id": user["_id"]}) == 0
    doc = {
        "user_id": user["_id"],
        "original_filename": name,
        "stored_filename": stored_filename,
        "file_type": file_type,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "text": parsed["text"],
        "text_length": len(parsed["text"]),
        "page_count": parsed["page_count"],
        "warnings": parsed["warnings"],
        "is_primary": first,
        "analysis": None,
        "created_at": utcnow(),
    }
    try:
        result = db.resumes.insert_one(doc)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    doc["_id"] = result.inserted_id
    log_activity(user["_id"], "resume_uploaded", {"resume_id": str(result.inserted_id)}, request)
    return _out(doc)


@router.get("")
def list_resumes(user: dict = Depends(get_current_user)) -> list[dict]:
    docs = get_db().resumes.find({"user_id": user["_id"]}, {"text": 0}).sort("created_at", -1)
    return [_out(d) for d in docs]


@router.get("/{resume_id}")
def get_resume(resume_id: str, user: dict = Depends(get_current_user)) -> dict:
    return _out(get_owned_or_404("resumes", resume_id, user["_id"]), include_text=True)


@router.post("/{resume_id}/primary")
def set_primary(resume_id: str, user: dict = Depends(get_current_user)) -> dict:
    doc = get_owned_or_404("resumes", resume_id, user["_id"], {"text": 0})
    db = get_db()
    db.resumes.update_many({"user_id": user["_id"]}, {"$set": {"is_primary": False}})
    db.resumes.update_one({"_id": doc["_id"]}, {"$set": {"is_primary": True}})
    return {"id": str(doc["_id"]), "is_primary": True}


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("resumes", resume_id, user["_id"], {"text": 0})
    db = get_db()
    _file_path(user["_id"], doc["stored_filename"]).unlink(missing_ok=True)
    db.resumes.delete_one({"_id": doc["_id"]})
    if doc.get("is_primary"):
        newest = db.resumes.find_one({"user_id": user["_id"]}, {"_id": 1}, sort=[("created_at", -1)])
        if newest:
            db.resumes.update_one({"_id": newest["_id"]}, {"$set": {"is_primary": True}})
    log_activity(user["_id"], "resume_deleted", {"resume_id": resume_id}, request)


@router.post("/{resume_id}/analyze")
def analyze(resume_id: str, user: dict = Depends(get_current_user)) -> dict:
    doc = get_owned_or_404("resumes", resume_id, user["_id"])
    result = analyze_resume(doc["text"])
    now = utcnow()
    get_db().resumes.update_one(
        {"_id": doc["_id"], "user_id": user["_id"]},
        {"$set": {"analysis": result, "analyzed_at": now}},
    )
    record_task(
        user["_id"], "resume_intelligence", "completed" if result["ai"] else "partial",
        f"Resume health score {result['health_score']}", {"resume_id": resume_id},
    )
    return {"resume_id": resume_id, "analyzed_at": now, **result}
