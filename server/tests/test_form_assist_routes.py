"""Route tests for the Application Assistant: local-only access, confirmation, plan binding, isolation, logging.

Run from the server folder:   python -m pytest tests -q
Uses an in-memory MongoDB (mongomock) and a fake browser session. No real browser is started.
Install the test tools once:  pip install -r requirements-dev.txt
"""
import json
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "x" * 48)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mongomock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.automation.form_assistant import AssistError
from app.database import mongo
from app.routes import automation
from app.services.safe_fetch import assert_public_url as real_assert_public_url
from app.utils.helpers import utcnow


def field(fid, **kw):
    base = {"id": fid, "tag": "input", "type": "text", "label": "", "placeholder": "", "name": "", "id_attr": "", "autocomplete": ""}
    base.update(kw)
    return base


FIELDS = [
    field("0_1", type="email", label="Email"),
    field("0_2", type="password", label="Password"),
    field("0_3", label="First name"),
    field("0_4", tag="textarea", type="textarea", label="Cover letter"),
    field("0_5", tag="textarea", type="textarea", label="Why do you want this job?"),
]


class FakeSession:
    def __init__(self, user_id, fields):
        self.id = uuid.uuid4().hex
        self.user_id = user_id
        self.plan, self.source, self.url = [], {}, None
        self.fields = fields
        self.commands = []

    def call(self, command, timeout):
        self.commands.append(command)
        if command["cmd"] in ("open", "scan"):
            return {"ok": True, "url": "https://jobs.example.com/apply", "title": "Apply", "fields": self.fields}
        if command["cmd"] == "fill":
            return {"ok": True, "filled": [i["id"] for i in command["items"]], "failed": []}
        raise AssistError("Unknown command.", 400)


class FakeManager:
    def __init__(self, fields):
        self.fields = fields
        self.sessions = {}
        self.closed = []

    def open(self, user_id):
        session = FakeSession(user_id, self.fields)
        self.sessions[session.id] = session
        return session

    def get(self, session_id, user_id):
        session = self.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise AssistError("That browser session was not found. Open the form again.", 404)
        return session

    def close(self, session_id, user_id):
        self.get(session_id, user_id)
        self.sessions.pop(session_id)
        self.closed.append(session_id)


@pytest.fixture()
def env(monkeypatch):
    mongo._client = mongomock.MongoClient(tz_aware=True)
    db = mongo.get_db()
    manager = FakeManager(FIELDS)
    monkeypatch.setattr(automation, "get_manager", lambda: manager)
    monkeypatch.setattr(automation, "assert_public_url", lambda url: url)  # no DNS in tests

    def make_user(email):
        uid = db.users.insert_one({"email": email, "full_name": "Asha Verma", "password_hash": "x", "is_active": True, "created_at": utcnow()}).inserted_id
        return db.users.find_one({"_id": uid})

    alice, bob = make_user("asha@example.com"), make_user("bob@example.com")
    db.candidate_profiles.insert_one(
        {"user_id": alice["_id"], "full_name": "Asha Verma", "phone": "+91 98765 43210", "technical_skills": ["Python"],
         "experience": [{"title": "Backend Developer", "company": "Acme", "start_date": "2021-01", "current": True}]}
    )
    app = FastAPI()
    app.include_router(automation.router, prefix="/api")
    current = {"user": alice}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)
    return type("Env", (), dict(db=db, client=client, manager=manager, alice=alice, bob=bob, current=current, monkeypatch=monkeypatch))


def open_form(env, **body):
    body = body or {"url": "https://jobs.example.com/apply"}
    return env.client.post("/api/form-assist/sessions", json=body)


def approve(env, opened, values, confirmed=True, plan_hash=None):
    return env.client.post(
        f"/api/form-assist/sessions/{opened['session_id']}/fill",
        json={"items": [{"id": k, "value": v} for k, v in values.items()], "plan_hash": plan_hash or opened["plan_hash"], "confirmed_by_user": confirmed},
    )


# ------------------------------------------------------------------ opening and planning
def test_status_reports_setup_and_the_safety_notice(env):
    body = env.client.get("/api/form-assist/status").json()
    assert body["local"] is True and "playwright install chromium" in body["setup"]
    assert "never presses" in body["notice"]


def test_open_builds_a_plan_from_verified_profile_data_only(env):
    r = open_form(env)
    assert r.status_code == 201, r.text
    opened = r.json()
    plan = {f["id"]: f for f in opened["plan"]}
    assert plan["0_1"]["proposed"] == "asha@example.com"
    assert plan["0_3"]["proposed"] == "Asha"
    assert plan["0_2"]["action"] == "skip" and plan["0_2"]["proposed"] is None        # password
    assert plan["0_5"]["action"] == "manual" and plan["0_5"]["proposed"] is None      # open-ended
    assert plan["0_4"]["proposed"] is None                                            # no cover letter chosen
    assert len(opened["plan_hash"]) == 64 and opened["summary"]["skipped"] == 1


def test_open_needs_an_address_and_refuses_private_or_local_ones(env):
    assert env.client.post("/api/form-assist/sessions", json={}).status_code == 422
    env.monkeypatch.setattr(automation, "assert_public_url", real_assert_public_url)
    for url in ("http://127.0.0.1:8000/", "http://169.254.169.254/latest/meta-data/", "http://10.1.2.3/apply"):
        r = open_form(env, url=url)
        assert r.status_code == 422 and "private or local" in r.json()["detail"], url
    assert env.manager.sessions == {}                      # no browser was ever started


def test_only_requests_from_this_computer_are_served(env):
    env.monkeypatch.setattr(automation, "LOCAL_HOSTS", set())
    assert open_form(env).status_code == 403
    assert env.client.post("/api/form-assist/sessions/abc/scan").status_code == 403
    assert env.client.post("/api/form-assist/sessions/abc/fill", json={"items": [{"id": "0_1", "value": "x"}], "plan_hash": "0" * 64, "confirmed_by_user": True}).status_code == 403
    assert env.manager.sessions == {}


def test_application_link_and_attached_cover_letter_are_used(env):
    letter_id = env.db.resume_versions.insert_one({"user_id": env.alice["_id"], "kind": "cover_letter", "title": "CL", "text": "Dear team, I am keen to join.", "created_at": utcnow()}).inserted_id
    app_id = env.db.applications.insert_one(
        {"user_id": env.alice["_id"], "company": "Globex", "job_title": "Python Developer", "job_url": "https://jobs.example.com/apply",
         "status": "preparing", "cover_letter_version_id": letter_id, "history": [], "created_at": utcnow(), "updated_at": utcnow()}
    ).inserted_id
    opened = open_form(env, application_id=str(app_id)).json()
    assert env.manager.sessions[opened["session_id"]].commands[0]["url"] == "https://jobs.example.com/apply"
    assert {f["id"]: f for f in opened["plan"]}["0_4"]["proposed"] == "Dear team, I am keen to join."


def test_an_overlong_cover_letter_is_not_proposed_and_the_user_is_told(env):
    letter_id = env.db.resume_versions.insert_one({"user_id": env.alice["_id"], "kind": "cover_letter", "text": "x" * 2500, "created_at": utcnow()}).inserted_id
    opened = open_form(env, url="https://jobs.example.com/apply", cover_letter_id=str(letter_id)).json()
    assert {f["id"]: f for f in opened["plan"]}["0_4"]["proposed"] is None
    assert any("longer than" in n for n in opened["notes"])


def test_a_document_that_is_not_a_cover_letter_is_refused(env):
    doc_id = env.db.resume_versions.insert_one({"user_id": env.alice["_id"], "kind": "tailored_resume", "text": "CV", "created_at": utcnow()}).inserted_id
    assert open_form(env, url="https://jobs.example.com/apply", cover_letter_id=str(doc_id)).status_code == 422


# ------------------------------------------------------------------ approval
def test_nothing_is_typed_without_confirmation_and_the_browser_is_never_told(env):
    opened = open_form(env).json()
    session = env.manager.sessions[opened["session_id"]]
    for confirmed in (False,):
        assert approve(env, opened, {"0_1": "asha@example.com"}, confirmed=confirmed).status_code == 422
    r = env.client.post(f"/api/form-assist/sessions/{opened['session_id']}/fill", json={"items": [{"id": "0_1", "value": "a@b.c"}], "plan_hash": opened["plan_hash"]})
    assert r.status_code == 422                            # confirmation missing entirely = false
    assert [c["cmd"] for c in session.commands] == ["open"]


def test_a_plan_that_changed_since_review_is_refused(env):
    opened = open_form(env).json()
    r = approve(env, opened, {"0_1": "asha@example.com"}, plan_hash="0" * 64)
    assert r.status_code == 409
    assert [c["cmd"] for c in env.manager.sessions[opened["session_id"]].commands] == ["open"]


def test_passwords_and_unknown_fields_cannot_be_filled(env):
    opened = open_form(env).json()
    assert approve(env, opened, {"0_2": "hunter2"}).status_code == 422
    assert approve(env, opened, {"9_9": "x"}).status_code == 422
    assert [c["cmd"] for c in env.manager.sessions[opened["session_id"]].commands] == ["open"]


def test_approved_fields_are_filled_and_values_are_never_logged(env):
    opened = open_form(env).json()
    r = approve(env, opened, {"0_1": "asha@example.com", "0_5": "Because I enjoy building APIs, secret-answer-42."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [f["id"] for f in body["filled"]] == ["0_1", "0_5"] and body["failed"] == []
    assert "submit" in body["message"] and "will not press submit" in body["message"]
    sent = env.manager.sessions[opened["session_id"]].commands[-1]
    assert sent["cmd"] == "fill" and {i["id"] for i in sent["items"]} == {"0_1", "0_5"}

    logs = list(env.db.activity_logs.find({}))
    assert any(l.get("action") == "form_assist.filled" for l in logs)
    blob = json.dumps(logs, default=str)
    assert "secret-answer-42" not in blob and "asha@example.com" not in blob and "98765" not in blob


def test_rescan_rebuilds_the_plan_with_the_same_verified_data(env):
    opened = open_form(env).json()
    again = env.client.post(f"/api/form-assist/sessions/{opened['session_id']}/scan").json()
    assert {f["id"]: f for f in again["plan"]}["0_1"]["proposed"] == "asha@example.com"
    assert again["plan_hash"] == opened["plan_hash"]


# ------------------------------------------------------------------ privacy and lifecycle
def test_other_users_cannot_see_fill_or_close_my_session(env):
    opened = open_form(env).json()
    sid = opened["session_id"]
    env.current["user"] = env.bob
    assert approve(env, opened, {"0_1": "x@y.com"}).status_code == 404
    assert env.client.post(f"/api/form-assist/sessions/{sid}/scan").status_code == 404
    assert env.client.delete(f"/api/form-assist/sessions/{sid}").status_code == 404
    assert sid in env.manager.sessions


def test_another_users_application_cannot_be_used(env):
    app_id = env.db.applications.insert_one(
        {"user_id": env.bob["_id"], "company": "X", "job_title": "Y", "job_url": "https://jobs.example.com/apply", "status": "saved", "history": [], "created_at": utcnow(), "updated_at": utcnow()}
    ).inserted_id
    assert open_form(env, application_id=str(app_id)).status_code == 404


def test_closing_a_session_closes_the_browser(env):
    opened = open_form(env).json()
    assert env.client.delete(f"/api/form-assist/sessions/{opened['session_id']}").status_code == 204
    assert opened["session_id"] in env.manager.closed
    assert approve(env, opened, {"0_1": "asha@example.com"}).status_code == 404
