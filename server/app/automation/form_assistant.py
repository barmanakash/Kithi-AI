"""Browser form assistant (parent side): field classification, the fill plan, the approval checks and session control.

SAFETY MODEL (this is the whole point of the module):
- Kithi NEVER submits an application. The code in this package contains no click, key-press or submit
  call at all (a test enforces that). It only types into text fields you approved.
- Filling needs your explicit approval of an exact list of fields and values, bound to the plan you saw.
- Only verified data from your own profile is proposed. Anything open-ended, sensitive, a consent
  checkbox, a file upload, a password or a captcha is left for you.
- The page is untrusted. Its text can never approve, fill or submit anything.
- The browser runs in a separate local process, opens only public http(s) sites and only on this machine.
"""
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[2]
MAX_VALUE_CHARS = 2000
IDLE_SECONDS = 20 * 60
MAX_SESSIONS = 2
OPEN_TIMEOUT = 90
FILL_TIMEOUT = 90

LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


class AssistError(Exception):
    """A problem to show the user (bad request, browser missing, page unreadable...)."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


# --------------------------------------------------------------------------------------------------
# Classification (pure)
# --------------------------------------------------------------------------------------------------
_SENSITIVE = re.compile(
    r"\b(gender|sex|race|racial|ethnic\w*|disabilit\w*|veteran|pronouns?|religio\w*|sexual orientation|date of birth|dob|birth ?date|"
    r"social security|ssn|aadhaar|aadhar|pan (number|card)|passport|national id|marital|caste|card number|cvv|iban|bank account|"
    r"criminal|conviction|visa status|immigration|citizenship)\b",
    re.I,
)
_CONSENT = re.compile(r"\b(i agree|i accept|i consent|terms|privacy policy|acknowledg\w*|certify|declare|signature|captcha|recaptcha|robot)\b", re.I)
_NOT_PERSON_NAME = re.compile(r"\b(company|school|college|university|reference|referr\w*|manager|emergency|spouse|father|mother|employer|institution|degree|supervisor)\b", re.I)

_RULES: list[tuple[str, re.Pattern]] = [
    ("email", re.compile(r"e-?mail", re.I)),
    ("phone", re.compile(r"phone|mobile|\bcell\b|telephone|contact number", re.I)),
    ("linkedin", re.compile(r"linkedin", re.I)),
    ("github", re.compile(r"github", re.I)),
    ("portfolio", re.compile(r"portfolio|personal (web ?)?site|personal url|your website|website url|\bblog\b", re.I)),
    ("first_name", re.compile(r"first name|given name|forename|\bfname\b", re.I)),
    ("last_name", re.compile(r"last name|family name|surname|\blname\b", re.I)),
    ("notice_period", re.compile(r"notice period|availability to join|how soon can you join|joining time", re.I)),
    ("salary", re.compile(r"(expected|current|desired|present) (salary|ctc|compensation|pay)|salary expectation|\bctc\b", re.I)),
    ("years_experience", re.compile(r"years? of (total |relevant |work |professional )?experience|total experience|experience \(?in years", re.I)),
    ("current_company", re.compile(r"current (company|employer|organi[sz]ation)|present (company|employer)|\bemployer\b", re.I)),
    ("current_title", re.compile(r"current (job |role |position )?title|current (role|position|designation)|job title|designation", re.I)),
    ("location", re.compile(r"\bcity\b|current location|where are you (based|located)|\blocation\b", re.I)),
    ("cover_letter", re.compile(r"cover letter", re.I)),
]
_FULL_NAME = re.compile(r"full name|your name|candidate name|applicant name|^name$|\bname\b", re.I)

CHOICE_TYPES = {"checkbox", "radio"}
NEVER_FILL_TYPES = {"password", "file", "checkbox", "radio", "hidden", "submit", "button", "image", "reset"}


def _text(desc: dict) -> str:
    raw = " ".join(str(desc.get(k) or "") for k in ("label", "placeholder", "name", "id_attr", "autocomplete"))
    return re.sub(r"[_\-]+", " ", raw).lower().strip()


def best_label(desc: dict) -> str:
    for key in ("label", "placeholder", "name", "id_attr"):
        value = (desc.get(key) or "").strip()
        if value:
            return re.sub(r"[_\-]+", " ", value)[:120]
    return "(unlabelled field)"


def classify_field(desc: dict) -> tuple[str, str, str]:
    """Return (kind, action, reason). action: 'fill' = may be proposed, 'manual' = for you, 'skip' = never touched."""
    ftype = (desc.get("type") or "text").lower()
    text = _text(desc)
    tag = (desc.get("tag") or "input").lower()

    if ftype == "password":
        return "password", "skip", "Passwords are never filled."
    if ftype == "file":
        return "file", "manual", "Attach your resume or documents yourself."
    if _SENSITIVE.search(text):
        return "sensitive", "skip", "Skipped for your privacy. Answer this yourself if you choose to."
    if _CONSENT.search(text):
        return "consent", "skip", "Agreements, signatures and captchas are always yours to complete."
    if ftype in CHOICE_TYPES:
        return "choice", "manual", "Choose this yourself."
    if ftype in NEVER_FILL_TYPES:
        return "other", "skip", "Not a text field."

    if ftype == "email":
        return "email", "fill", ""
    if ftype == "tel":
        return "phone", "fill", ""
    for kind, pattern in _RULES:
        if pattern.search(text):
            if kind == "salary":
                return "salary", "manual", "Salary figures are yours to decide. Kithi never enters them."
            return kind, "fill", ""
    if _FULL_NAME.search(text) and not _NOT_PERSON_NAME.search(text):
        return "full_name", "fill", ""
    if tag == "textarea" or len(text) > 70 or "?" in text:
        return "open_ended", "manual", "Open-ended question. Write your own answer."
    return "unknown", "manual", "Not recognised, so it is left for you."


# --------------------------------------------------------------------------------------------------
# Verified data -> proposals (pure)
# --------------------------------------------------------------------------------------------------
def build_source(ctx: dict, cover_letter: str | None = None) -> dict:
    """Pick only values the user has actually stored. Nothing is guessed."""
    profile = ctx.get("profile") or {}
    name = (ctx.get("full_name") or profile.get("full_name") or "").strip()
    parts = name.split()
    first, last = (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (name, "")

    experience = profile.get("experience") or []
    current = next((e for e in experience if e.get("current")), None)
    if current is None and experience:
        current = max(experience, key=lambda e: e.get("start_date") or "")
    years = ctx.get("years_experience")
    notice = profile.get("notice_period_days")
    return {
        "full_name": name or None,
        "first_name": first or None,
        "last_name": last or None,
        "email": ctx.get("email") or None,
        "phone": profile.get("phone") or None,
        "location": profile.get("location") or None,
        "linkedin": profile.get("linkedin_url") or None,
        "github": profile.get("github_url") or None,
        "portfolio": profile.get("portfolio_url") or None,
        "current_company": (current or {}).get("company") or None,
        "current_title": (current or {}).get("title") or None,
        "years_experience": years,
        "notice_days": notice,
        "cover_letter": (cover_letter or "").strip() or None,
    }


def _propose(kind: str, desc: dict, source: dict):
    ftype = (desc.get("type") or "text").lower()
    if kind == "years_experience":
        years = source.get("years_experience")
        return None if years is None else f"{years:g}"
    if kind == "notice_period":
        days = source.get("notice_days")
        if days is None:
            return None
        return str(days) if ftype == "number" else f"{days} days"
    if kind == "cover_letter":
        return source.get("cover_letter") if (desc.get("tag") or "") == "textarea" else None
    return source.get(kind)


def build_plan(descriptors: list[dict], source: dict) -> list[dict]:
    """Turn raw page fields into the plan the user reviews. Only 'fill' fields carry a proposed value."""
    plan = []
    for desc in descriptors:
        kind, action, reason = classify_field(desc)
        proposed = None
        if action == "fill":
            proposed = _propose(kind, desc, source)
            options = desc.get("options") or []
            if proposed is not None and desc.get("tag") == "select":
                match = next((o for o in options if o.strip().lower() == str(proposed).strip().lower()), None)
                proposed = match
                if match is None:
                    reason = "No option matches your stored value. Choose it yourself."
            if proposed is None:
                action = "manual"
                reason = reason or f"No verified {kind.replace('_', ' ')} in your profile. Add it there or type it yourself."
            elif desc.get("max_length") and len(str(proposed)) > desc["max_length"]:
                proposed, action, reason = None, "manual", "Your stored value is longer than this field allows."
            elif desc.get("current_value"):
                proposed, action, reason = None, "manual", "This field already has a value, so it was left alone."
        plan.append(
            {
                "id": desc["id"],
                "label": best_label(desc),
                "kind": kind,
                "tag": desc.get("tag"),
                "type": desc.get("type"),
                "required": bool(desc.get("required")),
                "action": action,
                "reason": reason,
                "proposed": proposed,
                "options": (desc.get("options") or [])[:40] if desc.get("tag") == "select" else [],
            }
        )
    return plan


def plan_hash(plan: list[dict]) -> str:
    material = json.dumps([[f["id"], f["kind"], f["action"], f["proposed"]] for f in plan], sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def validate_fill(plan: list[dict], items: list[dict], supplied_hash: str, confirmed: bool) -> list[dict]:
    """Check an approval request against the plan the user saw. Returns the exact list to type."""
    if confirmed is not True:
        raise AssistError("Confirm that you approve filling these fields. Nothing is typed without it.")
    if supplied_hash != plan_hash(plan):
        raise AssistError("The plan changed since you reviewed it. Open the form again and review the new plan.", 409)
    by_id = {f["id"]: f for f in plan}
    seen: set[str] = set()
    approved = []
    for item in items:
        fid, value = item.get("id"), item.get("value")
        field = by_id.get(fid)
        if field is None:
            raise AssistError(f"Unknown field '{fid}'.")
        if fid in seen:
            raise AssistError(f"Field '{field['label']}' was listed twice.")
        seen.add(fid)
        if field["action"] == "skip":
            raise AssistError(f"'{field['label']}' is never filled by Kithi. Complete it yourself in the browser.")
        if not isinstance(value, str):
            raise AssistError(f"Give a text value for '{field['label']}'.")
        value = _CTRL.sub("", value).strip()
        if not value:
            continue
        if len(value) > MAX_VALUE_CHARS:
            raise AssistError(f"The value for '{field['label']}' is too long.")
        if field["tag"] == "select":
            match = next((o for o in field["options"] if o.strip().lower() == value.lower()), None)
            if match is None:
                raise AssistError(f"'{value}' is not one of the options for '{field['label']}'.")
            value = match
        approved.append({"id": fid, "value": value, "tag": field["tag"], "type": field["type"]})
    if not approved:
        raise AssistError("Nothing to fill. Tick at least one field with a value.")
    return approved


# --------------------------------------------------------------------------------------------------
# Session control: one child process per session
# --------------------------------------------------------------------------------------------------
WORKER_COMMAND = [sys.executable, "-m", "app.automation.browser_worker"]


class Session:
    def __init__(self, user_id, proc: subprocess.Popen):
        self.id = uuid.uuid4().hex
        self.user_id = user_id
        self.proc = proc
        self.lines: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.created = self.last_used = time.monotonic()
        self.url: str | None = None
        self.plan: list[dict] = []
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        try:
            for line in self.proc.stdout:
                self.lines.put(line)
        finally:
            self.lines.put(None)

    def alive(self) -> bool:
        return self.proc.poll() is None

    def call(self, command: dict, timeout: float) -> dict:
        with self.lock:
            if not self.alive():
                raise AssistError("The browser window was closed. Open the form again.", 410)
            self.last_used = time.monotonic()
            try:
                self.proc.stdin.write(json.dumps(command) + "\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                raise AssistError("The browser window was closed. Open the form again.", 410)
            try:
                line = self.lines.get(timeout=timeout)
            except queue.Empty:
                self.close()
                raise AssistError("The browser took too long to respond and was closed.", 504)
            if line is None:
                raise AssistError("The browser closed unexpectedly. Open the form again.", 410)
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                raise AssistError("The browser sent an unreadable reply.", 502)
            if not reply.get("ok"):
                raise AssistError(str(reply.get("error") or "The browser could not do that."), int(reply.get("status") or 422))
            self.last_used = time.monotonic()
            return reply

    def close(self) -> None:
        try:
            if self.alive():
                try:
                    self.proc.stdin.write(json.dumps({"cmd": "close"}) + "\n")
                    self.proc.stdin.flush()
                except (BrokenPipeError, OSError, ValueError):
                    pass
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        finally:
            for stream in (self.proc.stdin, self.proc.stdout):
                try:
                    stream.close()
                except Exception:
                    pass


class SessionManager:
    def __init__(self, command: list[str] | None = None, max_sessions: int = MAX_SESSIONS, idle_seconds: float = IDLE_SECONDS):
        self.command = command or WORKER_COMMAND
        self.max_sessions = max_sessions
        self.idle_seconds = idle_seconds
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _reap(self) -> None:
        now = time.monotonic()
        for sid, session in list(self.sessions.items()):
            if not session.alive() or now - session.last_used > self.idle_seconds:
                session.close()
                self.sessions.pop(sid, None)

    def open(self, user_id) -> Session:
        with self._lock:
            self._reap()
            for sid, session in list(self.sessions.items()):  # one open form per user
                if session.user_id == user_id:
                    session.close()
                    self.sessions.pop(sid, None)
            if len(self.sessions) >= self.max_sessions:
                raise AssistError("Too many browser windows are open. Close one first.", 429)
            try:
                proc = subprocess.Popen(
                    self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    cwd=str(SERVER_DIR), text=True, encoding="utf-8", bufsize=1,
                )
            except OSError as exc:
                raise AssistError(f"Could not start the browser helper ({type(exc).__name__}).", 503)
            session = Session(user_id, proc)
            self.sessions[session.id] = session
            return session

    def get(self, session_id: str, user_id) -> Session:
        with self._lock:
            self._reap()
            session = self.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise AssistError("That browser session was not found. Open the form again.", 404)
        return session

    def close(self, session_id: str, user_id) -> None:
        session = self.get(session_id, user_id)
        with self._lock:
            self.sessions.pop(session_id, None)
        session.close()

    def close_all(self) -> None:
        with self._lock:
            sessions, self.sessions = list(self.sessions.values()), {}
        for session in sessions:
            session.close()


_manager: SessionManager | None = None


def get_manager() -> SessionManager:
    global _manager
    if _manager is None:
        _manager = SessionManager()
        import atexit

        atexit.register(_manager.close_all)
    return _manager
