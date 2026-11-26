"""LangGraph orchestrator for the AI Career Coach.

classify -> one specialised agent node -> END

Most nodes are deterministic and read the user's own saved data (skill gaps, progress, resume
analysis, scam signals, salary maths), so they work even when Ollama is off. Only the general coach
node calls the local model, and it is given a compact summary of the user's verified data. Every
user message is treated as untrusted text. Nothing here can send, submit or change anything.
"""
import re
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, field_validator

from app.agents.career_intelligence import aggregate_skill_gaps, career_progress
from app.agents.salary_intelligence import estimate
from app.agents.scam_detection import assess_text
from app.core.prompt_guard import wrap_untrusted
from app.database.mongo import get_db
from app.services.ai_service import get_ai_service
from app.services.candidate import load_candidate_context, summarize_candidate
from app.services.prompts import SYSTEM_BASE

INTENTS = ("scam", "salary", "interview", "skill_gap", "progress", "resume", "coach")

_PATTERNS = {
    "scam": re.compile(r"\bscam|fake\s+job|fraud|suspicious|too\s+good\s+to\s+be\s+true|is\s+this\s+(job\s+)?(legit|real|genuine)", re.I),
    "salary": re.compile(r"\bsalary|\bctc\b|in[\s-]?hand|take[\s-]?home|\blpa\b|\blakhs?\b|negotiat", re.I),
    "interview": re.compile(r"\binterview|mock\s+(test|round)|practice\s+questions", re.I),
    "skill_gap": re.compile(r"skill\s+gap|missing\s+skills?|what\s+(skills?\s+)?should\s+i\s+learn|learn\s+next|roadmap|up-?skill", re.I),
    "progress": re.compile(r"\bprogress\b|how\s+am\s+i\s+doing|where\s+do\s+i\s+stand", re.I),
    "resume": re.compile(r"\bresume\b|\bcv\b", re.I),
}
_LPA = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lacs?)\b", re.I)


class CoachState(TypedDict, total=False):
    user: dict
    message: str
    history: list
    intent: str
    agent: str
    reply: str
    data: Any
    action: dict | None


def _inr(value: float) -> str:
    return f"₹{value:,.0f}"


def classify(state: CoachState) -> dict:
    text = state["message"]
    for intent in INTENTS[:-1]:
        if _PATTERNS[intent].search(text):
            if intent == "salary" and not _LPA.search(text) and not re.search(r"\d", text):
                continue  # a salary question with no numbers goes to the general coach
            return {"intent": intent}
    return {"intent": "coach"}


def route(state: CoachState) -> str:
    return state["intent"]


# ---------------------------------------------------------------- deterministic agent nodes

def scam_node(state: CoachState) -> dict:
    text = state["message"]
    if len(text) < 80:
        return {
            "agent": "Job Scam Detection",
            "reply": "Paste the full text of the job post or recruiter message and I will check it for warning signs, showing the exact text behind each one.",
            "action": {"label": "Open Scam Detection", "path": "/scam-detection"},
        }
    result = assess_text(text)
    level = result["risk_level"].replace("_", " ")
    lines = [f"Concern level: {level} (confidence: {result['confidence']})."]
    for signal in result["signals"][:5]:
        lines.append(f"- {signal['description']}: \"{signal['evidence'][:100]}\"")
    if not result["signals"]:
        lines.append("I found no warning signs in this text, but that does not prove the offer is genuine.")
    lines.append(result["uncertainty"])
    return {"agent": "Job Scam Detection", "reply": "\n".join(lines), "data": result, "action": {"label": "Open Scam Detection", "path": "/scam-detection"}}


def salary_node(state: CoachState) -> dict:
    match = _LPA.search(state["message"])
    if not match:
        return coach_node(state)
    fixed = float(match.group(1)) * 100_000
    est = estimate(fixed)
    reply = (
        f"If {match.group(1)} LPA is your fixed annual pay, a rough estimate is {_inr(est['monthly_in_hand_regular'])} per month in hand "
        f"({_inr(est['annual_in_hand'])} per year), after about {_inr(est['income_tax_annual'])} income tax and PF. "
        "This uses the Indian new tax regime and assumes basic pay is 40% of fixed pay. "
        "Use the Salary Intelligence page to add variable pay, compare offers and draft a negotiation email."
    )
    return {"agent": "Salary Intelligence", "reply": reply, "data": est, "action": {"label": "Open Salary Intelligence", "path": "/salary"}}


def interview_node(state: CoachState) -> dict:
    uid = state["user"]["_id"]
    scores = [f["overall_score"] for f in get_db().interview_feedback.find({"user_id": uid}, {"overall_score": 1}).sort("created_at", -1).limit(5) if "overall_score" in f]
    note = f" Your last {len(scores)} practice scores averaged {sum(scores) / len(scores):.1f}/10." if scores else " You have no completed practice sessions yet."
    return {
        "agent": "Interview Preparation",
        "reply": "Interview Lab generates technical and HR questions for a role or a saved job, scores each answer and tells you what to improve." + note,
        "action": {"label": "Open Interview Lab", "path": "/interview-lab"},
    }


def skill_gap_node(state: CoachState) -> dict:
    gaps = aggregate_skill_gaps(state["user"]["_id"])
    if not gaps["gaps"]:
        reply = gaps["note"] or "No skill gaps found across your saved jobs yet."
    else:
        top = ", ".join(f"{g['skill']} ({g['jobs_requiring']} of {gaps['jobs_analyzed']} jobs)" for g in gaps["gaps"][:6])
        reply = f"Across {gaps['jobs_analyzed']} scored jobs, the skills you are missing most often are: {top}. I can turn these into a learning roadmap from the Skill gaps & roadmap tab."
    return {"agent": "Career Intelligence", "reply": reply, "data": gaps, "action": {"label": "Build a roadmap", "tab": "roadmap"}}


def progress_node(state: CoachState) -> dict:
    cand = load_candidate_context(state["user"]["_id"], state["user"])
    progress = career_progress(state["user"]["_id"], cand)
    if progress["overall_percent"] is None:
        reply = "There is not enough data to measure progress yet."
    else:
        parts = "; ".join(f"{c['label']}: {c['percent']}%" for c in progress["components"])
        reply = f"Your overall progress is {progress['overall_percent']}%, the plain average of: {parts}."
    return {"agent": "Career Progress Tracker", "reply": reply, "data": progress, "action": {"label": "See progress", "tab": "progress"}}


def resume_node(state: CoachState) -> dict:
    cand = load_candidate_context(state["user"]["_id"], state["user"])
    resume = cand.get("resume")
    analysis = (resume or {}).get("analysis") or {}
    if not resume:
        return {"agent": "Resume Intelligence", "reply": "You have not uploaded a resume yet. Upload one in My Resume and I can analyse it.", "action": {"label": "Open My Resume", "path": "/resume"}}
    if not analysis:
        return {"agent": "Resume Intelligence", "reply": "Your resume has not been analysed yet. Run Resume Intelligence to get a health score with evidence.", "action": {"label": "Open Resume Intelligence", "path": "/resume-intelligence"}}
    tips = analysis.get("rule_based_suggestions", [])[:4]
    reply = f"Your primary resume's health score is {analysis.get('health_score')}/100."
    if tips:
        reply += " Top fixes:\n" + "\n".join(f"- {t}" for t in tips)
    return {"agent": "Resume Intelligence", "reply": reply, "action": {"label": "Open Resume Intelligence", "path": "/resume-intelligence"}}


# ---------------------------------------------------------------- general coach (local AI)

class _CoachReply(BaseModel):
    reply: str = ""

    @field_validator("reply", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v).strip()


def coach_node(state: CoachState) -> dict:
    user = state["user"]
    cand = load_candidate_context(user["_id"], user)
    gaps = aggregate_skill_gaps(user["_id"])["gaps"][:5]
    goals = [g["text"] for g in get_db().career_goals.find({"user_id": user["_id"], "kind": "goal", "status": "active"}).limit(3)]
    counts = {r["_id"]: r["n"] for r in get_db().applications.aggregate([{"$match": {"user_id": user["_id"]}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}])}

    context = [summarize_candidate(cand, max_skills=20)]
    if gaps:
        context.append("Most common missing skills in saved jobs: " + ", ".join(g["skill"] for g in gaps))
    if goals:
        context.append("Career goals: " + "; ".join(goals))
    if counts:
        context.append("Applications by status: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    wrapped_ctx, _ = wrap_untrusted("user_career_data", "\n".join(context), max_chars=3500)

    history = "\n".join(f"{h['role']}: {h['content']}" for h in (state.get("history") or [])[-6:])
    wrapped_msg, _ = wrap_untrusted("user_message", (history + "\n" if history else "") + f"user: {state['message']}", max_chars=3000)

    prompt = (
        "You are a practical, honest career coach. Answer the user's latest message.\n"
        'Return JSON: {"reply": string}\n'
        "Rules:\n"
        "- Use only the user's career data below plus general, well-established career advice.\n"
        "- If the data needed is missing, say what is missing instead of guessing.\n"
        "- Never promise outcomes. Never claim you sent, applied or changed anything.\n"
        "- Keep the reply under 180 words, concrete and kind.\n\n" + wrapped_ctx + "\n\n" + wrapped_msg
    )
    out = get_ai_service().generate_structured(SYSTEM_BASE, prompt, _CoachReply)
    reply = out.reply[:1500] or "I could not form a useful answer. Try rephrasing your question."
    return {"agent": "Career Coach", "reply": reply, "action": None}


@lru_cache
def get_graph():
    graph = StateGraph(CoachState)
    graph.add_node("classify", classify)
    nodes = {
        "scam": scam_node, "salary": salary_node, "interview": interview_node, "skill_gap": skill_gap_node,
        "progress": progress_node, "resume": resume_node, "coach": coach_node,
    }
    for name, fn in nodes.items():
        graph.add_node(name, fn)
        graph.add_edge(name, END)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route, {name: name for name in nodes})
    return graph.compile()


def run_coach(user: dict, message: str, history: list | None = None) -> dict:
    final = get_graph().invoke({"user": user, "message": message, "history": history or []})
    return {
        "intent": final.get("intent", "coach"),
        "agent": final.get("agent", "Career Coach"),
        "reply": final.get("reply", ""),
        "data": final.get("data"),
        "action": final.get("action"),
    }
