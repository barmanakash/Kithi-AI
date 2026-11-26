"""Job Search Recovery routes.

Read-only: the analysis is computed on demand from your own tracked data and nothing is stored or sent.
"""
from fastapi import APIRouter, Depends, Request

from app.agents.job_search_recovery import analyze_recovery
from app.api.deps import get_current_user
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.tasks import record_task

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.get("")
def recovery(request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Analyse your applications, match scores, resume and profile, and list what to fix first."""
    cand = load_candidate_context(user["_id"], user)
    result = analyze_recovery(user["_id"], cand)
    high = sum(1 for f in result["findings"] if f["severity"] == "high")
    record_task(user["_id"], "job_search_recovery", "completed", f"{len(result['findings'])} finding(s), {high} high")
    log_activity(user["_id"], "recovery_analyzed", {"findings": len(result["findings"])}, request)
    return result
