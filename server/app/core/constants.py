APPLICATION_STATUSES = [
    "saved",
    "interested",
    "preparing",
    "ready_for_review",
    "applied",
    "interview_scheduled",
    "interview_completed",
    "offer_received",
    "rejected",
    "withdrawn",
    "no_response",
]

# Every collection except "users" is scoped to a single user via a `user_id` field.
USER_COLLECTIONS = [
    "candidate_profiles",
    "resumes",
    "resume_versions",
    "jobs",
    "job_matches",
    "applications",
    "recruiters",
    "recruiter_messages",
    "interviews",
    "interview_feedback",
    "career_goals",
    "skill_assessments",
    "learning_plans",
    "company_research",
    "salary_offers",
    "scam_assessments",
    "agent_tasks",
    "activity_logs",
]

ALL_COLLECTIONS = ["users"] + USER_COLLECTIONS
