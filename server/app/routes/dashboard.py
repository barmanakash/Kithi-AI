from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.services.candidate import get_primary_resume, profile_completeness
from app.utils.helpers import public

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

PENDING = {"saved", "interested", "preparing", "ready_for_review"}
SUBMITTED = {"applied", "interview_scheduled", "interview_completed", "offer_received", "rejected", "no_response"}
INTERVIEW = {"interview_scheduled", "interview_completed"}
MATCH_THRESHOLD = 55  # "good" label and above
WEEKS = 12


def _status_counts(user_id) -> dict[str, int]:
    rows = get_db().applications.aggregate(
        [{"$match": {"user_id": user_id}}, {"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    )
    return {row["_id"]: row["n"] for row in rows}


def _sum(counts: dict[str, int], statuses: set[str]) -> int:
    return sum(n for status, n in counts.items() if status in statuses)


@router.get("/stats")
def stats(user: dict = Depends(get_current_user)) -> dict:
    """The Overview metrics, all computed from stored data."""
    db = get_db()
    uid = user["_id"]
    counts = _status_counts(uid)

    resume = get_primary_resume(uid)
    analysis = (resume or {}).get("analysis") or {}
    profile = db.candidate_profiles.find_one({"user_id": uid}) or {}

    return {
        "jobs_discovered": db.jobs.count_documents({"user_id": uid}),
        "matching_opportunities": db.job_matches.count_documents({"user_id": uid, "score": {"$gte": MATCH_THRESHOLD}}),
        "applications_total": sum(counts.values()),
        "applications_submitted": _sum(counts, SUBMITTED),
        "applications_pending": _sum(counts, PENDING),
        "interview_invitations": _sum(counts, INTERVIEW) + counts.get("offer_received", 0),
        "offers": counts.get("offer_received", 0),
        "rejections": counts.get("rejected", 0),
        "resume_health_score": analysis.get("health_score"),
        "resume_analyzed": bool(analysis),
        "profile_completeness": profile_completeness(profile)["percent"] if profile else 0,
        "match_threshold": MATCH_THRESHOLD,
    }


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.get("/analytics")
def analytics(user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    uid = user["_id"]
    counts = _status_counts(uid)
    today = date.today()

    jobs_total = db.jobs.count_documents({"user_id": uid})
    matched = db.job_matches.count_documents({"user_id": uid, "score": {"$gte": MATCH_THRESHOLD}})
    submitted = _sum(counts, SUBMITTED)
    interviews = _sum(counts, INTERVIEW) + counts.get("offer_received", 0)
    responded = interviews + counts.get("rejected", 0)

    funnel = [
        {"stage": "Jobs found", "value": jobs_total},
        {"stage": "Good matches", "value": matched},
        {"stage": "Applications tracked", "value": sum(counts.values())},
        {"stage": "Submitted", "value": submitted},
        {"stage": "Interviews", "value": interviews},
        {"stage": "Offers", "value": counts.get("offer_received", 0)},
    ]

    # Applications submitted per week (by application date), most recent WEEKS weeks.
    first_week = _week_start(today) - timedelta(weeks=WEEKS - 1)
    buckets = {first_week + timedelta(weeks=i): 0 for i in range(WEEKS)}
    for app in db.applications.find({"user_id": uid, "status": {"$in": list(SUBMITTED)}, "application_date": {"$ne": None}}, {"application_date": 1}):
        try:
            week = _week_start(date.fromisoformat(app["application_date"]))
        except (ValueError, TypeError):
            continue
        if week in buckets:
            buckets[week] += 1
    weekly = [{"week": w.isoformat(), "label": w.strftime("%d %b"), "applications": n} for w, n in buckets.items()]

    # Match quality and the skills most often missing across saved jobs.
    labels = Counter()
    missing = Counter()
    scores = []
    for match in db.job_matches.find({"user_id": uid}, {"label": 1, "score": 1, "missing_skills": 1}):
        labels[match.get("label", "unknown")] += 1
        if match.get("score") is not None:
            scores.append(match["score"])
        for item in match.get("missing_skills", []):
            if not item.get("optional"):
                missing[item["skill"]] += 1

    # Follow-ups due within a week (or overdue) on applications still in progress.
    horizon = (today + timedelta(days=7)).isoformat()
    due = db.applications.find(
        {"user_id": uid, "status": {"$in": ["applied", "interview_scheduled", "interview_completed", "no_response", "preparing", "ready_for_review"]},
         "follow_up_date": {"$ne": None, "$lte": horizon}},
        {"company": 1, "job_title": 1, "status": 1, "follow_up_date": 1},
    ).sort("follow_up_date", 1).limit(20)
    follow_ups = []
    for app in due:
        item = public(app)
        item["overdue"] = app["follow_up_date"] < today.isoformat()
        follow_ups.append(item)

    def rate(numerator: int) -> float | None:
        return round(100 * numerator / submitted, 1) if submitted else None

    return {
        "funnel": funnel,
        "status_counts": counts,
        "weekly_applications": weekly,
        "rates": {
            "response_rate": rate(responded),
            "interview_rate": rate(interviews),
            "no_response_rate": rate(counts.get("no_response", 0)),
            "submitted": submitted,
        },
        "match_quality": {
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "by_label": dict(labels),
        },
        "top_missing_skills": [{"skill": s, "jobs": n} for s, n in missing.most_common(10)],
        "follow_ups": follow_ups,
    }
