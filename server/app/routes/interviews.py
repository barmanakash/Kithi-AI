"""Interview Lab routes: mock interview sessions, answer evaluation and feedback.

Flow: create a session (questions are generated) -> answer questions one at a time (each answer is
evaluated) -> complete the session (overall feedback is stored and skill assessments are updated).
Everything runs on the local model. Nothing is shared with anyone.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents.interview_prep import evaluate_answer, generate_questions
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, utcnow

router = APIRouter(prefix="/interviews", tags=["interviews"])

MAX_SESSIONS = 100


class SessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str | None = Field(default=None, max_length=24)
    role: str | None = Field(default=None, max_length=100)
    kind: Literal["technical", "hr", "mixed"] = "mixed"
    count: int = Field(default=5, ge=3, le=10)
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: int = Field(ge=0, le=20)
    answer: str = Field(min_length=1, max_length=4000)


def _out(doc: dict, include_questions: bool = True) -> dict:
    out = public(doc)
    questions = doc.get("questions", [])
    answered = [q for q in questions if q.get("evaluation")]
    out["progress"] = {"answered": len(answered), "total": len(questions)}
    out["next_index"] = next((q["index"] for q in questions if not q.get("evaluation")), None)
    if not include_questions:
        out.pop("questions", None)
    return out


def _default_role(cand: dict) -> str | None:
    experience = cand["profile"].get("experience") or []
    if experience and experience[0].get("title"):
        return experience[0]["title"]
    return cand["profile"].get("headline") or None


@router.post("/sessions", status_code=201)
def create_session(body: SessionIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Generate a set of interview questions for a role or a saved job."""
    db = get_db()
    if db.interviews.count_documents({"user_id": user["_id"]}) >= MAX_SESSIONS:
        raise HTTPException(status_code=409, detail=f"Session limit reached ({MAX_SESSIONS}). Delete old sessions first.")

    job = get_owned_or_404("jobs", body.job_id, user["_id"]) if body.job_id else None
    cand = load_candidate_context(user["_id"], user)
    role = (body.role or "").strip() or (job or {}).get("title") or _default_role(cand)
    if not role:
        raise HTTPException(status_code=422, detail="Tell me the role to practise for, or pick a saved job, or add a headline to your profile.")

    questions, flags = generate_questions(cand, body.kind, body.count, body.difficulty, role, job)
    now = utcnow()
    doc = {
        "user_id": user["_id"],
        "title": f"{body.kind.title()} interview: {role}"[:150],
        "kind": body.kind,
        "difficulty": body.difficulty,
        "role": role,
        "job_id": job["_id"] if job else None,
        "company": job.get("company") if job else None,
        "questions": questions,
        "status": "in_progress",
        "overall_score": None,
        "injection_flags": flags,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    doc["_id"] = db.interviews.insert_one(doc).inserted_id
    record_task(user["_id"], "interview_preparation", "completed", f"{len(questions)} questions for {role}", {"session_id": str(doc["_id"])})
    log_activity(user["_id"], "interview_session_created", {"session_id": str(doc["_id"])}, request)
    return _out(doc)


@router.get("/sessions")
def list_sessions(limit: int = 50, user: dict = Depends(get_current_user)) -> dict:
    docs = get_db().interviews.find({"user_id": user["_id"]}).sort("created_at", -1).limit(clamp_limit(limit, 100))
    return {"sessions": [_out(d, include_questions=False) for d in docs]}


@router.get("/sessions/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)) -> dict:
    return _out(get_owned_or_404("interviews", session_id, user["_id"]))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, request: Request, user: dict = Depends(get_current_user)) -> None:
    doc = get_owned_or_404("interviews", session_id, user["_id"], {"_id": 1})
    db = get_db()
    db.interviews.delete_one({"_id": doc["_id"], "user_id": user["_id"]})
    db.interview_feedback.delete_many({"user_id": user["_id"], "session_id": doc["_id"]})
    log_activity(user["_id"], "interview_session_deleted", {"session_id": session_id}, request)


@router.post("/sessions/{session_id}/answer")
def submit_answer(session_id: str, body: AnswerIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Submit your answer to one question. It is evaluated by the local model and stored."""
    session = get_owned_or_404("interviews", session_id, user["_id"])
    if session["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="This session is already completed.")
    questions = session.get("questions", [])
    if body.index >= len(questions):
        raise HTTPException(status_code=404, detail="Question not found")

    evaluation = evaluate_answer(questions[body.index], body.answer.strip(), session["role"])
    now = utcnow()
    get_db().interviews.update_one(
        {"_id": session["_id"], "user_id": user["_id"]},
        {"$set": {
            f"questions.{body.index}.answer": body.answer.strip(),
            f"questions.{body.index}.evaluation": evaluation,
            f"questions.{body.index}.answered_at": now,
            "updated_at": now,
        }},
    )
    log_activity(user["_id"], "interview_answer_evaluated", {"session_id": session_id, "index": body.index}, request)
    answered = sum(1 for i, q in enumerate(questions) if q.get("evaluation") or i == body.index)
    return {
        "index": body.index,
        "evaluation": evaluation,
        "progress": {"answered": answered, "total": len(questions)},
        "next_index": next((q["index"] for q in questions if not q.get("evaluation") and q["index"] != body.index), None),
    }


def _dedupe(items: list[str], limit: int) -> list[str]:
    seen, out = set(), []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item.strip())
    return out[:limit]


@router.post("/sessions/{session_id}/complete")
def complete_session(session_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Finish the session: store overall feedback and update your skill assessments."""
    db = get_db()
    session = get_owned_or_404("interviews", session_id, user["_id"])
    if session["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="This session is already completed.")
    answered = [q for q in session["questions"] if q.get("evaluation")]
    if not answered:
        raise HTTPException(status_code=422, detail="Answer at least one question before completing the session.")

    scores = [q["evaluation"]["score"] for q in answered]
    overall = round(sum(scores) / len(scores), 1)
    by_category: dict[str, list[float]] = {}
    for q in answered:
        by_category.setdefault(q["category"], []).append(q["evaluation"]["score"])
    category_scores = {c: round(sum(v) / len(v), 1) for c, v in by_category.items()}
    strengths = _dedupe([s for q in answered for s in q["evaluation"]["strengths"][:2]], 8)
    improvements = _dedupe([s for q in answered for s in q["evaluation"]["improvements"][:2]], 8)

    now = utcnow()
    feedback = {
        "user_id": user["_id"],
        "session_id": session["_id"],
        "title": session["title"],
        "kind": session["kind"],
        "role": session["role"],
        "overall_score": overall,
        "answered": len(answered),
        "total": len(session["questions"]),
        "category_scores": category_scores,
        "strengths": strengths,
        "improvements": improvements,
        "created_at": now,
    }
    feedback["_id"] = db.interview_feedback.insert_one(feedback).inserted_id

    # Update skill assessments from interview evidence, never overwriting the user's own manual ratings.
    skill_updates = []
    for q in answered:
        skill, score = q.get("focus_skill"), q["evaluation"]["score"]
        if not skill or 4 < score < 7:
            continue
        key = skill.lower()
        existing = db.skill_assessments.find_one({"user_id": user["_id"], "skill_key": key})
        if existing and existing.get("source") == "manual":
            continue
        level = max(1, min(5, round(score / 2)))
        fields = {
            "skill": skill, "skill_key": key, "level": level,
            "kind": "strength" if score >= 7 else "gap", "source": "interview",
            "evidence": f"Interview practice score {score}/10 ({session['title']})"[:300], "updated_at": now,
        }
        if existing:
            db.skill_assessments.update_one({"_id": existing["_id"], "user_id": user["_id"]}, {"$set": fields})
        else:
            db.skill_assessments.insert_one({**fields, "user_id": user["_id"], "created_at": now})
        skill_updates.append({"skill": skill, "kind": fields["kind"], "level": level})

    db.interviews.update_one(
        {"_id": session["_id"], "user_id": user["_id"]},
        {"$set": {"status": "completed", "overall_score": overall, "completed_at": now, "updated_at": now, "feedback_id": feedback["_id"]}},
    )
    log_activity(user["_id"], "interview_session_completed", {"session_id": session_id, "overall_score": overall}, request)
    return {"feedback": public(feedback), "skill_updates": skill_updates}


@router.get("/feedback")
def list_feedback(limit: int = 50, user: dict = Depends(get_current_user)) -> dict:
    docs = get_db().interview_feedback.find({"user_id": user["_id"]}).sort("created_at", -1).limit(clamp_limit(limit, 100))
    return {"feedback": [public(d) for d in docs]}
