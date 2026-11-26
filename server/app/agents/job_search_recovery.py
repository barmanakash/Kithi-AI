"""Job Search Recovery Agent.

Fully deterministic and evidence-based: it reads the user's own applications, match scores, resume
analysis and profile, then reports specific findings with the numbers behind them and concrete next
actions. It does not guess causes it cannot see (for example, it cannot know why a recruiter did not
reply), and it says so when there is too little data to conclude anything.
"""
from datetime import date

from bson import ObjectId

from app.database.mongo import get_db

SUBMITTED = {"applied", "interview_scheduled", "interview_completed", "offer_received", "rejected", "no_response"}
INTERVIEW = {"interview_scheduled", "interview_completed", "offer_received"}
ACTIVE = {"applied", "interview_scheduled", "interview_completed"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _applied_on(app: dict) -> date | None:
    value = app.get("application_date")
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    stamp = app.get("applied_at")
    return stamp.date() if stamp else None


def _finding(fid: str, severity: str, title: str, evidence: str, actions: list[str]) -> dict:
    return {"id": fid, "severity": severity, "title": title, "evidence": evidence, "actions": actions}


def analyze_recovery(user_id: ObjectId, cand: dict) -> dict:
    db = get_db()
    apps = list(db.applications.find({"user_id": user_id}).limit(1000))
    today = date.today()

    submitted = [a for a in apps if a["status"] in SUBMITTED or a.get("applied_at")]
    interviews = [a for a in apps if a["status"] in INTERVIEW]
    rejected = [a for a in apps if a["status"] == "rejected"]
    n = len(submitted)

    job_ids = [a["job_id"] for a in submitted if a.get("job_id")]
    scores = {
        m["job_id"]: m["score"]
        for m in db.job_matches.find({"user_id": user_id, "job_id": {"$in": job_ids}, "score": {"$ne": None}}, {"job_id": 1, "score": 1})
    } if job_ids else {}
    scored_submitted = [scores[a["job_id"]] for a in submitted if a.get("job_id") in scores]

    stale = [a for a in apps if a["status"] == "applied" and (d := _applied_on(a)) and (today - d).days > 14]
    overdue = [a for a in apps if a["status"] in ACTIVE and a.get("follow_up_date") and a["follow_up_date"] < today.isoformat()]
    recent = [a for a in submitted if (d := _applied_on(a)) and (today - d).days <= 14]
    tailored = [a for a in submitted if a.get("resume_version_id")]

    resume_score = (((cand.get("resume") or {}).get("analysis")) or {}).get("health_score")
    completeness = cand["completeness"]["percent"]

    metrics = {
        "applications_total": len(apps),
        "submitted": n,
        "interviews_or_offers": len(interviews),
        "rejections": len(rejected),
        "interview_rate_percent": round(100 * len(interviews) / n) if n else None,
        "response_rate_percent": round(100 * (len(interviews) + len(rejected)) / n) if n else None,
        "submitted_last_14_days": len(recent),
        "average_match_score_submitted": round(sum(scored_submitted) / len(scored_submitted)) if scored_submitted else None,
        "share_with_tailored_resume_percent": round(100 * len(tailored) / n) if n else None,
        "resume_health_score": resume_score,
        "profile_completeness_percent": completeness,
    }

    findings: list[dict] = []
    if n < 5:
        findings.append(_finding(
            "not_enough_data", "info", "Not enough submitted applications to find patterns",
            f"You have {n} submitted application(s). Patterns need at least 5, ideally 15 or more.",
            ["Keep tracking every application and status change in Applications.", "Mark applications as applied only after you submit them yourself."],
        ))
    if n >= 10 and metrics["interview_rate_percent"] is not None and metrics["interview_rate_percent"] < 5:
        findings.append(_finding(
            "low_interview_rate", "high", "Very few applications are reaching interviews",
            f"{len(interviews)} of {n} submitted applications ({metrics['interview_rate_percent']}%) reached an interview or offer.",
            ["Compare your resume with the job descriptions: add the missing skills you genuinely have.", "Apply to jobs with a higher match score first.", "Ask for feedback or a referral for roles you really want."],
        ))
    low_match = [s for s in scored_submitted if s < 50]
    if len(scored_submitted) >= 5 and len(low_match) / len(scored_submitted) > 0.4:
        findings.append(_finding(
            "low_match_targeting", "medium", "Many applications target jobs that match your profile weakly",
            f"{len(low_match)} of {len(scored_submitted)} scored applications had a match score under 50.",
            ["Filter AI Job Search results by match score before applying.", "Use the skill gaps view to decide which skills to learn before applying to stretch roles."],
        ))
    if n >= 5 and metrics["share_with_tailored_resume_percent"] is not None and metrics["share_with_tailored_resume_percent"] < 30:
        findings.append(_finding(
            "no_tailoring", "medium", "Most applications use a generic resume",
            f"Only {len(tailored)} of {n} submitted applications used a tailored resume.",
            ["Generate a tailored resume and cover letter for roles you really want (My Resume > Generate).", "Review each tailored version, because every claim must be true."],
        ))
    if len(stale) >= 3:
        findings.append(_finding(
            "stale_applications", "medium", "Several applications have had no movement for over 2 weeks",
            f"{len(stale)} applications are still 'applied' more than 14 days after the application date.",
            ["Send a short, polite follow-up (Recruiter Hub drafts it; you approve before sending).", "Mark applications with no reply as 'No response' to keep your funnel accurate."],
        ))
    if overdue:
        findings.append(_finding(
            "overdue_follow_ups", "medium", "Follow-ups are overdue",
            f"{len(overdue)} active application(s) have a follow-up date in the past.",
            ["Send those follow-ups today, then set a new follow-up date."],
        ))
    if n >= 1 and len(recent) < 3:
        findings.append(_finding(
            "low_recent_activity", "low", "Few applications in the last two weeks",
            f"{len(recent)} application(s) submitted in the last 14 days.",
            ["Set a small weekly target, such as 5 well-matched applications."],
        ))
    if resume_score is not None and resume_score < 60:
        findings.append(_finding(
            "weak_resume", "high", "Your resume health score is low",
            f"Resume health score: {resume_score}/100.",
            ["Open Resume Intelligence and fix the lowest-scoring areas first.", "Add measurable results to your bullet points where they are true."],
        ))
    if completeness < 70:
        findings.append(_finding(
            "incomplete_profile", "medium", "Your profile is incomplete, so matching and tailoring are less accurate",
            f"Profile completeness: {completeness}%. Missing: {', '.join(cand['completeness']['missing'][:6])}.",
            ["Complete the missing profile sections. Matching and tailoring only use information you provide."],
        ))

    findings.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])
    real = [f for f in findings if f["id"] != "not_enough_data"]
    if real:
        summary = f"{len(real)} issue(s) found. Start with: {real[0]['title']}."
    elif n < 5:
        summary = "There is not enough application history yet to find patterns."
    else:
        summary = "No clear problems found in the data available. Keep going and keep tracking."

    return {
        "summary": summary,
        "metrics": metrics,
        "findings": findings,
        "limits": "This analysis only sees what you track in Kithi. It cannot know why a recruiter did not reply, so treat findings as hypotheses to test.",
    }
