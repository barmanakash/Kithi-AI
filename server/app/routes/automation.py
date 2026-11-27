"""Application Assistant API: opens a visible browser on this computer and fills form fields you approve.

Kithi never submits an application. Filling needs your explicit approval of an exact list of fields,
bound to the plan you reviewed. You press the form's own submit button yourself.
"""
import importlib.util
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.api.deps import get_current_user
from app.automation.form_assistant import (
    FILL_TIMEOUT,
    LOCAL_HOSTS,
    MAX_VALUE_CHARS,
    OPEN_TIMEOUT,
    AssistError,
    build_plan,
    build_source,
    get_manager,
    plan_hash,
    validate_fill,
)
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.safe_fetch import UnsafeURLError, assert_public_url
from app.utils.helpers import get_owned_or_404

router = APIRouter(prefix="/form-assist", tags=["application-assistant"])

NOTICE = (
    "Kithi fills only the fields you approve, using verified data from your profile. It never presses "
    "submit, never answers open-ended or sensitive questions, and never touches passwords, uploads or "
    "agreements. Review the form in the browser window and submit it yourself."
)


class OpenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: HttpUrl | None = None
    application_id: str | None = Field(default=None, max_length=24)
    cover_letter_id: str | None = Field(default=None, max_length=24)


class FillItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=40)
    value: str = Field(max_length=MAX_VALUE_CHARS)


class FillIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FillItem] = Field(min_length=1, max_length=150)
    plan_hash: str = Field(min_length=64, max_length=64)
    confirmed_by_user: bool = False


def _require_local(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail="The browser assistant only works when Kithi is running on your own computer.")


def _fail(exc: AssistError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _call(session, command: dict, timeout: float) -> dict:
    try:
        return session.call(command, timeout)
    except AssistError as exc:
        raise _fail(exc)


def _summary(plan: list[dict]) -> dict:
    return {
        "total": len(plan),
        "fillable": sum(1 for f in plan if f["action"] == "fill" and f["proposed"] is not None),
        "manual": sum(1 for f in plan if f["action"] == "manual"),
        "skipped": sum(1 for f in plan if f["action"] == "skip"),
    }


def _plan_response(session, reply: dict, notes: list[str]) -> dict:
    return {
        "session_id": session.id,
        "url": reply.get("url"),
        "title": reply.get("title"),
        "plan": session.plan,
        "plan_hash": plan_hash(session.plan),
        "summary": _summary(session.plan),
        "notes": notes,
        "notice": NOTICE,
    }


def _session_for(session_id: str, user: dict):
    try:
        return get_manager().get(session_id, user["_id"])
    except AssistError as exc:
        raise _fail(exc)


@router.get("/status")
def status(request: Request, user: dict = Depends(get_current_user)) -> dict:
    host = request.client.host if request.client else ""
    return {
        "playwright_installed": importlib.util.find_spec("playwright") is not None,
        "local": host in LOCAL_HOSTS,
        "setup": ["pip install playwright", "playwright install chromium"],
        "notice": NOTICE,
    }


@router.post("/sessions", status_code=201)
def open_session(body: OpenIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    _require_local(request)
    uid = user["_id"]
    app_doc = get_owned_or_404("applications", body.application_id, uid) if body.application_id else None
    url = str(body.url) if body.url else (app_doc or {}).get("job_url")
    if not url:
        raise HTTPException(status_code=422, detail="Enter the address of the application form, or choose an application that has a posting link.")
    try:
        assert_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    notes: list[str] = []
    cover_letter = None
    letter_id = body.cover_letter_id or (app_doc or {}).get("cover_letter_version_id")
    if letter_id:
        letter = get_owned_or_404("resume_versions", str(letter_id), uid)
        if letter.get("kind") != "cover_letter":
            raise HTTPException(status_code=422, detail="That document is not a cover letter.")
        text = (letter.get("text") or "").strip()
        if len(text) > MAX_VALUE_CHARS:
            notes.append(f"Your cover letter is longer than {MAX_VALUE_CHARS} characters, so it is not proposed. Paste it yourself if the form asks for it.")
        else:
            cover_letter = text or None

    ctx = load_candidate_context(uid, user)
    source = build_source(ctx, cover_letter)

    manager = get_manager()
    try:
        session = manager.open(uid)
    except AssistError as exc:
        raise _fail(exc)
    try:
        reply = _call(session, {"cmd": "open", "url": url}, OPEN_TIMEOUT)
    except HTTPException:
        try:
            manager.close(session.id, uid)
        except AssistError:
            pass
        raise

    session.source = source
    session.url = reply.get("url")
    session.plan = build_plan(reply.get("fields") or [], source)
    if not session.plan:
        notes.append("No form fields were found on this page. If the form is on another step or behind a button, open it in the browser window and press Rescan.")
    host = urlparse(url).hostname or ""
    log_activity(uid, "form_assist.opened", {"host": host, "fields": len(session.plan)}, request)
    return _plan_response(session, reply, notes)


@router.post("/sessions/{session_id}/scan")
def rescan(session_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Re-read the page now showing in the browser (for example after you moved to the next step)."""
    _require_local(request)
    session = _session_for(session_id, user)
    reply = _call(session, {"cmd": "scan"}, OPEN_TIMEOUT)
    session.url = reply.get("url")
    session.plan = build_plan(reply.get("fields") or [], getattr(session, "source", {}))
    notes = [] if session.plan else ["No form fields were found on the page that is showing now."]
    return _plan_response(session, reply, notes)


@router.post("/sessions/{session_id}/fill")
def fill(session_id: str, body: FillIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Type the approved values into the form. Needs your explicit confirmation of the plan you reviewed."""
    _require_local(request)
    session = _session_for(session_id, user)
    try:
        approved = validate_fill(session.plan, [i.model_dump() for i in body.items], body.plan_hash, body.confirmed_by_user)
    except AssistError as exc:
        raise _fail(exc)
    reply = _call(session, {"cmd": "fill", "items": approved}, FILL_TIMEOUT)

    labels = {f["id"]: f["label"] for f in session.plan}
    failed = [{"id": f.get("id"), "label": labels.get(f.get("id"), "Field"), "error": f.get("error")} for f in reply.get("failed", [])]
    filled = [{"id": fid, "label": labels.get(fid, "Field")} for fid in reply.get("filled", [])]
    # Counts only. The values are personal data and are never logged.
    log_activity(user["_id"], "form_assist.filled", {"filled": len(filled), "failed": len(failed)}, request)
    return {
        "filled": filled,
        "failed": failed,
        "message": "Check every field in the browser window, complete the rest yourself, and submit the form yourself. Kithi will not press submit.",
    }


@router.delete("/sessions/{session_id}", status_code=204)
def close_session(session_id: str, user: dict = Depends(get_current_user)) -> None:
    try:
        get_manager().close(session_id, user["_id"])
    except AssistError as exc:
        raise _fail(exc)
