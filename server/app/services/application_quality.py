"""Application Quality Checker.

Deterministic pre-submission review. It never contacts anyone and never submits anything: it only
tells the user what looks ready and what needs attention, with the reason for each finding.
"""
import re

from app.utils.format_labels import COMPLETENESS_LABELS

_PLACEHOLDER = re.compile(r"\[[^\]\n]{1,40}\](?!\()|\bTODO\b|lorem ipsum|\{\{.*?\}\}|\bX{3,}\b", re.I)


def _check(key: str, label: str, status: str, message: str) -> dict:
    return {"key": key, "label": label, "status": status, "message": message}


def check_application(
    app: dict,
    cand: dict,
    job: dict | None,
    match: dict | None,
    resume_doc: dict | None,
    letter_doc: dict | None,
) -> dict:
    checks: list[dict] = []

    # Job link
    if app.get("job_url"):
        checks.append(_check("job_link", "Job posting link", "pass", "A link to the posting is saved."))
    else:
        checks.append(_check("job_link", "Job posting link", "warn", "No posting link saved. Keep one so you can re-read the requirements before interviews."))

    # Resume
    primary = cand.get("resume")
    if resume_doc:
        checks.append(_check("resume", "Resume for this application", "pass", f"Tailored resume attached: {resume_doc.get('title', 'untitled')}."))
        if _PLACEHOLDER.search(resume_doc.get("content_markdown", "")):
            checks.append(_check("resume_placeholders", "Resume placeholder text", "fail", "The attached resume contains placeholder text such as [brackets] or TODO. Edit it before using it."))
    elif primary:
        checks.append(_check("resume", "Resume for this application", "warn", "No tailored resume attached. Your primary resume would be used. Generating a tailored version usually improves relevance."))
    else:
        checks.append(_check("resume", "Resume for this application", "fail", "You have no resume. Upload one or generate a tailored resume first."))

    # Resume health
    health = ((primary or {}).get("analysis") or {}).get("health_score")
    if primary and health is None:
        checks.append(_check("resume_health", "Resume health", "warn", "Your primary resume has not been analyzed yet. Run Resume Intelligence."))
    elif health is not None:
        status = "pass" if health >= 70 else "warn"
        checks.append(_check("resume_health", "Resume health", status, f"Your primary resume scores {health}/100 in Resume Intelligence."))

    # Cover letter
    if letter_doc:
        if _PLACEHOLDER.search(letter_doc.get("content_markdown", "")):
            checks.append(_check("cover_letter", "Cover letter", "fail", "The attached cover letter contains placeholder text. Edit it before sending."))
        else:
            checks.append(_check("cover_letter", "Cover letter", "pass", "A cover letter is attached."))
    else:
        checks.append(_check("cover_letter", "Cover letter", "info", "No cover letter attached. Optional, but useful when the posting asks for one."))

    # Profile data used to fill application forms
    completeness = cand.get("completeness", {})
    percent = completeness.get("percent", 0)
    if percent >= 70:
        checks.append(_check("profile", "Candidate profile", "pass", f"Your profile is {percent}% complete."))
    else:
        missing = ", ".join(COMPLETENESS_LABELS.get(k, k) for k in completeness.get("missing", [])[:5])
        checks.append(_check("profile", "Candidate profile", "warn", f"Your profile is {percent}% complete. Missing: {missing}."))
    if not (cand.get("profile") or {}).get("phone"):
        checks.append(_check("contact", "Contact details", "warn", "No phone number in your profile. Application forms usually ask for one."))

    # Match against the linked job
    if job and match:
        score = match.get("score")
        if score is None:
            checks.append(_check("match", "Fit with the job", "warn", "Not enough profile data to score this job."))
        else:
            top_missing = [m["skill"] for m in match.get("missing_skills", []) if not m.get("optional")][:5]
            detail = f" Required skills not found in your profile: {', '.join(top_missing)}." if top_missing else ""
            status = "pass" if score >= 55 else "warn"
            checks.append(_check("match", "Fit with the job", status, f"Match score {score}/100 ({match.get('label')}).{detail}"))
    else:
        checks.append(_check("match", "Fit with the job", "info", "Not linked to a saved job, so no match analysis is available."))

    # Safety of the linked job
    if job:
        level = job.get("scam_level")
        if level == "high_concern":
            checks.append(_check("safety", "Listing safety", "fail", "This listing shows several scam warning signals. Verify the employer independently before sharing any information."))
        elif level == "medium_concern":
            checks.append(_check("safety", "Listing safety", "warn", "This listing shows some scam warning signals. Check the Scam Detection report."))
        else:
            checks.append(_check("safety", "Listing safety", "pass", "No strong scam warning signals were found in the saved listing text."))
        if job.get("injection_flags"):
            checks.append(_check("injection", "Suspicious wording", "warn", "The listing contains wording aimed at AI tools. It was ignored, but treat the listing with care."))

    # Follow-up and contacts
    if app.get("follow_up_date"):
        checks.append(_check("follow_up", "Follow-up date", "pass", f"Follow-up planned for {app['follow_up_date']}."))
    else:
        checks.append(_check("follow_up", "Follow-up date", "warn", "No follow-up date set. A reminder 5 to 7 days after applying is common."))
    recruiter = app.get("recruiter") or {}
    if not (recruiter.get("name") or recruiter.get("email")):
        checks.append(_check("recruiter", "Recruiter contact", "info", "No recruiter or hiring-manager contact saved."))

    failed = [c for c in checks if c["status"] == "fail"]
    warned = [c for c in checks if c["status"] == "warn"]
    scored = [c for c in checks if c["status"] != "info"]
    passed = [c for c in scored if c["status"] == "pass"]
    score = round(100 * len(passed) / len(scored)) if scored else 0
    return {
        "ready": not failed,
        "score": score,
        "blocking": len(failed),
        "warnings": len(warned),
        "checks": checks,
        "note": "This is a checklist, not a guarantee. Review everything yourself before you apply.",
    }
