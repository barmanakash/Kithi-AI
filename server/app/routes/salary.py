"""Salary Intelligence routes: in-hand estimator, saved offers, comparison and negotiation drafts."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents.salary_intelligence import compare_offers, draft_negotiation, estimate
from app.api.deps import get_current_user
from app.database.mongo import get_db
from app.services.audit import log_activity
from app.services.candidate import load_candidate_context
from app.services.tasks import record_task
from app.utils.helpers import clamp_limit, get_owned_or_404, public, to_object_id, utcnow

router = APIRouter(prefix="/salary", tags=["salary"])

MAX_OFFERS = 50
MONEY_MAX = 1_000_000_000


class EstimateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixed_annual: float = Field(gt=0, le=MONEY_MAX, description="Fixed gross pay per year (excluding employer PF)")
    variable_annual: float = Field(default=0, ge=0, le=MONEY_MAX)
    variable_payout_percent: float = Field(default=100, ge=0, le=200)
    joining_bonus: float = Field(default=0, ge=0, le=MONEY_MAX)
    basic_percent: float = Field(default=40, ge=10, le=80)


class OfferIn(EstimateIn):
    company: str = Field(min_length=1, max_length=150)
    role: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=100)
    status: Literal["received", "negotiating", "accepted", "declined"] = "received"
    notes: str = Field(default="", max_length=2000)


def _calc(body: EstimateIn) -> dict:
    return estimate(body.fixed_annual, body.variable_annual, body.variable_payout_percent, body.joining_bonus, body.basic_percent)


def _out(doc: dict) -> dict:
    return public(doc)


@router.post("/estimate")
def estimate_pay(body: EstimateIn, user: dict = Depends(get_current_user)) -> dict:
    """Break down CTC and estimate in-hand pay. Nothing is saved."""
    return _calc(body)


@router.get("/offers")
def list_offers(limit: int = 50, user: dict = Depends(get_current_user)) -> dict:
    docs = get_db().salary_offers.find({"user_id": user["_id"]}).sort("created_at", -1).limit(clamp_limit(limit, MAX_OFFERS))
    return {"offers": [_out(d) for d in docs]}


@router.post("/offers", status_code=201)
def create_offer(body: OfferIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    db = get_db()
    if db.salary_offers.count_documents({"user_id": user["_id"]}) >= MAX_OFFERS:
        raise HTTPException(status_code=409, detail=f"Offer limit reached ({MAX_OFFERS}). Delete old offers first.")
    now = utcnow()
    doc = {**body.model_dump(), "user_id": user["_id"], "estimate": _calc(body), "created_at": now, "updated_at": now}
    doc["_id"] = db.salary_offers.insert_one(doc).inserted_id
    log_activity(user["_id"], "salary_offer_saved", {"offer_id": str(doc["_id"])}, request)
    return _out(doc)


@router.put("/offers/{offer_id}")
def update_offer(offer_id: str, body: OfferIn, user: dict = Depends(get_current_user)) -> dict:
    offer = get_owned_or_404("salary_offers", offer_id, user["_id"], {"_id": 1})
    changes = {**body.model_dump(), "estimate": _calc(body), "updated_at": utcnow()}
    get_db().salary_offers.update_one({"_id": offer["_id"], "user_id": user["_id"]}, {"$set": changes})
    return _out(get_db().salary_offers.find_one({"_id": offer["_id"]}))


@router.delete("/offers/{offer_id}", status_code=204)
def delete_offer(offer_id: str, user: dict = Depends(get_current_user)) -> None:
    offer = get_owned_or_404("salary_offers", offer_id, user["_id"], {"_id": 1})
    get_db().salary_offers.delete_one({"_id": offer["_id"], "user_id": user["_id"]})


class CompareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[str] = Field(min_length=2, max_length=6)


@router.post("/compare")
def compare(body: CompareIn, user: dict = Depends(get_current_user)) -> dict:
    """Rank saved offers by estimated annual in-hand pay."""
    ids = list(dict.fromkeys(body.ids))
    if len(ids) < 2:
        raise HTTPException(status_code=422, detail="Pick at least two different offers to compare.")
    docs = list(get_db().salary_offers.find({"user_id": user["_id"], "_id": {"$in": [to_object_id(i) for i in ids]}}))
    if len(docs) != len(ids):
        raise HTTPException(status_code=404, detail="One or more offers were not found.")
    return compare_offers([_out(d) for d in docs])


class NegotiationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_fixed_annual: float | None = Field(default=None, gt=0, le=MONEY_MAX)
    target_variable_annual: float | None = Field(default=None, ge=0, le=MONEY_MAX)
    tone: Literal["polite", "confident"] = "polite"
    leverage_notes: str = Field(default="", max_length=800, description="Only facts you want mentioned, e.g. another offer you really hold")
    points_to_highlight: list[str] = Field(default_factory=list, max_length=5)


@router.post("/offers/{offer_id}/negotiation-message")
def negotiation_message(offer_id: str, body: NegotiationIn, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Draft a negotiation email (local AI). It is only a draft: nothing is sent, and you stay in control."""
    offer = _out(get_owned_or_404("salary_offers", offer_id, user["_id"]))
    if body.target_fixed_annual is None and body.target_variable_annual is None:
        raise HTTPException(status_code=422, detail="Enter the fixed or variable pay you want to ask for.")
    options = body.model_dump()
    options["points_to_highlight"] = [p.strip()[:200] for p in body.points_to_highlight if p.strip()]
    cand = load_candidate_context(user["_id"], user)
    draft = draft_negotiation(cand, offer, options)
    record_task(user["_id"], "salary_intelligence", "completed", f"Negotiation draft for {offer['company']}")
    log_activity(user["_id"], "negotiation_draft_created", {"offer_id": offer_id}, request)
    return draft
