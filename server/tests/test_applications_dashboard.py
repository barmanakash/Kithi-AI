"""Integration tests: the applications API, the dashboard/analytics built on it, and recruiter follow-ups
drafted from an application.

Run from the server folder:   python -m pytest tests -q
Uses an in-memory MongoDB (mongomock) and a scripted fake AI model. No Ollama or MongoDB needed.
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "x" * 48)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mongomock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import mongo
from app.routes import applications, dashboard, recruiter_messages, recruiters
from app.services.candidate import load_candidate_context
from app.services.matching import score_and_store
from app.utils.helpers import utcnow


class FakeAI:
    def __init__(self):
        self.reply, self.error, self.prompts = None, None, []

    def generate_structured(self, system, prompt, model_cls, max_retries=1):
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return model_cls.model_validate(self.reply)


@pytest.fixture()
def env(monkeypatch):
    mongo._client = mongomock.MongoClient(tz_aware=True)
    db = mongo.get_db()
    fake = FakeAI()
    monkeypatch.setattr("app.agents.recruiter_outreach.get_ai_service", lambda: fake)

    def make_user(email):
        uid = db.users.insert_one({"email": email, "full_name": "Asha Verma", "password_hash": "x", "is_active": True, "created_at": utcnow()}).inserted_id
        return db.users.find_one({"_id": uid})

    alice, bob = make_user("a@example.com"), make_user("b@example.com")
    db.candidate_profiles.insert_one(
        {"user_id": alice["_id"], "full_name": "Asha Verma", "headline": "Backend developer",
         "technical_skills": ["Python", "FastAPI", "MongoDB"],
         "experience": [{"title": "Backend Developer", "company": "Acme", "start_date": "2021-01", "current": True,
                         "description": "Built REST APIs with Python and FastAPI.", "achievements": []}]}
    )
    jobs = []
    for title, company in [("Python Developer", "Globex"), ("Platform Engineer", "Initech")]:
        jid = db.jobs.insert_one(
            {"user_id": alice["_id"], "title": title, "company": company,
             "description": "Requirements: Python, FastAPI, React and Docker experience required. Build APIs.",
             "url": "https://example.com/job", "created_at": utcnow()}
        ).inserted_id
        jobs.append(str(jid))

    app = FastAPI()
    for module in (applications, dashboard, recruiters, recruiter_messages):
        app.include_router(module.router, prefix="/api")
    current = {"user": alice}
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    return type("Env", (), dict(db=db, ai=fake, client=TestClient(app), alice=alice, bob=bob, current=current, jobs=jobs))


def make(env, **over):
    body = {"company": "Globex", "job_title": "Python Developer", "status": "saved"}
    body.update(over)
    return env.client.post("/api/applications", json=body)


def stats(env):
    return env.client.get("/api/dashboard/stats").json()


# ---------------------------------------------------------------- applications contract
def test_applied_needs_explicit_confirmation(env):
    assert make(env, status="applied").status_code == 422
    ok = make(env, status="applied", confirmed_by_user=True)
    assert ok.status_code == 201
    app = ok.json()
    assert app["application_date"] == utcnow().date().isoformat() and app["applied_at"]

    saved = make(env).json()
    r = env.client.post(f"/api/applications/{saved['id']}/status", json={"status": "applied"})
    assert r.status_code == 422
    r = env.client.post(f"/api/applications/{saved['id']}/status", json={"status": "applied", "confirmed_by_user": True})
    assert r.status_code == 200 and r.json()["status"] == "applied"
    assert [h["status"] for h in r.json()["history"]] == ["saved", "applied"]


def test_from_job_tracks_once(env):
    first = env.client.post(f"/api/applications/from-job/{env.jobs[0]}").json()
    again = env.client.post(f"/api/applications/from-job/{env.jobs[0]}").json()
    assert first["created"] is True and again["created"] is False
    assert first["application"]["id"] == again["application"]["id"]
    assert first["application"]["status"] == "interested"


def test_quality_check_response_shape_the_ui_depends_on(env):
    app = env.client.post(f"/api/applications/from-job/{env.jobs[0]}").json()["application"]
    q = env.client.post(f"/api/applications/{app['id']}/quality-check").json()
    assert set(q) >= {"ready", "score", "blocking", "warnings", "checks", "note"}
    assert all({"key", "label", "status", "message"} <= set(c) for c in q["checks"])


# ---------------------------------------------------------------- dashboard stats
def test_dashboard_stats_are_real_counts(env):
    s = stats(env)
    assert s["jobs_discovered"] == 2 and s["applications_total"] == 0 and s["matching_opportunities"] == 0

    make(env, status="interested")
    make(env, status="preparing")
    make(env, status="applied", confirmed_by_user=True)
    a = make(env, status="applied", confirmed_by_user=True).json()
    env.client.post(f"/api/applications/{a['id']}/status", json={"status": "interview_scheduled"})
    b = make(env, status="applied", confirmed_by_user=True).json()
    env.client.post(f"/api/applications/{b['id']}/status", json={"status": "rejected"})

    s = stats(env)
    assert s["applications_total"] == 5
    assert s["applications_pending"] == 2          # interested + preparing
    assert s["applications_submitted"] == 3        # applied, interview_scheduled, rejected
    assert s["interview_invitations"] == 1 and s["rejections"] == 1


def test_matching_opportunities_use_the_stored_scores(env):
    # A job that needs only skills the candidate has, so at least one score clears the 55 threshold.
    env.db.jobs.insert_one(
        {"user_id": env.alice["_id"], "title": "Backend Developer", "company": "Hooli",
         "description": "Requirements: Python, FastAPI and MongoDB experience required. Build REST APIs.",
         "url": "https://example.com/strong", "created_at": utcnow()}
    )
    cand = load_candidate_context(env.alice["_id"], env.alice)
    for job in env.db.jobs.find({"user_id": env.alice["_id"]}):
        score_and_store(env.alice, job, cand)
    scores = sorted(m["score"] for m in env.db.job_matches.find({"user_id": env.alice["_id"]}))
    assert scores[-1] >= 55 and scores[0] < 55, scores          # one strong match, two partial ones
    assert stats(env)["matching_opportunities"] == 1


# ---------------------------------------------------------------- analytics
def test_analytics_funnel_rates_followups_and_skill_gaps(env):
    cand = load_candidate_context(env.alice["_id"], env.alice)
    for job in env.db.jobs.find({"user_id": env.alice["_id"]}):
        score_and_store(env.alice, job, cand)

    a = make(env, status="applied", confirmed_by_user=True).json()
    env.client.post(f"/api/applications/{a['id']}/status", json={"status": "interview_scheduled"})
    make(env, status="applied", confirmed_by_user=True)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    over = make(env, status="applied", confirmed_by_user=True, follow_up_date=yesterday, company="Initech").json()

    an = env.client.get("/api/dashboard/analytics").json()
    funnel = {f["stage"]: f["value"] for f in an["funnel"]}
    assert funnel["Jobs found"] == 2 and funnel["Applications tracked"] == 3
    assert funnel["Submitted"] == 3 and funnel["Interviews"] == 1
    assert an["rates"]["submitted"] == 3
    assert an["rates"]["interview_rate"] == round(100 / 3, 1)
    assert an["rates"]["response_rate"] == round(100 / 3, 1)
    assert sum(w["applications"] for w in an["weekly_applications"]) == 3
    assert len(an["weekly_applications"]) == 12 and an["weekly_applications"][-1]["applications"] == 3

    due = {f["id"]: f for f in an["follow_ups"]}
    assert over["id"] in due and due[over["id"]]["overdue"] is True

    required_missing = {
        item["skill"]
        for m in env.db.job_matches.find({"user_id": env.alice["_id"]})
        for item in m.get("missing_skills", [])
        if not item.get("optional")
    }
    assert required_missing, "the fixture jobs should require skills the candidate lacks"
    assert {g["skill"] for g in an["top_missing_skills"]} == required_missing
    assert an["match_quality"]["average_score"] is not None


def test_rates_are_none_not_zero_when_nothing_submitted(env):
    an = env.client.get("/api/dashboard/analytics").json()
    assert an["rates"]["response_rate"] is None and an["rates"]["interview_rate"] is None


def test_dashboard_is_isolated_per_user(env):
    make(env, status="applied", confirmed_by_user=True)
    env.current["user"] = env.bob
    s = stats(env)
    assert s["jobs_discovered"] == 0 and s["applications_total"] == 0 and s["applications_submitted"] == 0
    an = env.client.get("/api/dashboard/analytics").json()
    assert an["funnel"][0]["value"] == 0 and an["follow_ups"] == [] and an["top_missing_skills"] == []


# ---------------------------------------------------------------- recruiter follow-up from an application
def test_follow_up_draft_from_an_application_uses_its_job_and_date(env):
    env.ai.error = None
    env.ai.reply = {
        "subject": "Following up on my Python Developer application",
        "paragraphs": [
            "I applied for the Python Developer role at Globex and wanted to follow up on the status of my application.",
            "I remain very interested and my Python and FastAPI experience fits the role well, so I would be glad to share anything further you need.",
        ],
    }
    app = make(env, status="applied", confirmed_by_user=True, job_id=env.jobs[0]).json()
    r = env.client.post("/api/recruiter-messages/generate", json={"kind": "follow_up", "application_id": app["id"]})
    assert r.status_code == 201, r.text
    m = r.json()["message"]
    assert m["application_id"] == app["id"] and m["job_id"] == env.jobs[0] and m["company"] == "Globex"
    assert m["status"] == "draft" and m["source"] == "ai"
    assert "Globex" in env.ai.prompts[-1] and "submitted" in env.ai.prompts[-1]


def test_follow_up_template_mentions_the_real_application_date(env):
    from app.services.ai_service import AIUnavailableError
    env.ai.error = AIUnavailableError("offline")
    app = make(env, status="applied", confirmed_by_user=True).json()
    m = env.client.post("/api/recruiter-messages/generate", json={"kind": "follow_up", "application_id": app["id"]}).json()["message"]
    assert m["source"] == "template" and app["application_date"] in m["body"]
    assert "[" not in m["body"]   # no placeholders


def test_other_users_application_cannot_be_used_for_a_draft(env):
    app = make(env).json()
    env.current["user"] = env.bob
    env.db.candidate_profiles.insert_one({"user_id": env.bob["_id"], "full_name": "Bob", "technical_skills": ["Python"]})
    r = env.client.post("/api/recruiter-messages/generate", json={"kind": "follow_up", "application_id": app["id"]})
    assert r.status_code == 422
