"""Salary Intelligence Agent.

Transparent, rule-based pay maths (no AI) plus an AI-written negotiation message that may only use
facts the user supplied.

IMPORTANT: tax figures are an ESTIMATE for the Indian new tax regime using the slabs below. Tax
rules change every Budget, so the slab table is kept in one place and every response carries the
assumptions used. Employer-specific items (HRA, NPS, insurance, reimbursements, state professional
tax) are not modelled. No market salary data is stored locally, so this agent never claims what a
role "should" pay.
"""
import re

from pydantic import BaseModel, field_validator

from app.core.prompt_guard import wrap_untrusted
from app.services.ai_service import get_ai_service
from app.services.candidate import summarize_candidate
from app.services.prompts import SYSTEM_BASE

TAX_BASIS = "India new tax regime, FY 2025-26 slabs (verify against the current year's rules)"
SLABS = [
    (400_000, 0.00),
    (800_000, 0.05),
    (1_200_000, 0.10),
    (1_600_000, 0.15),
    (2_000_000, 0.20),
    (2_400_000, 0.25),
    (float("inf"), 0.30),
]
STANDARD_DEDUCTION = 75_000
REBATE_LIMIT = 1_200_000  # no tax when taxable income is at or below this
CESS = 0.04
EMPLOYEE_PF_RATE = 0.12


def income_tax(gross_income: float) -> int:
    taxable = max(0.0, gross_income - STANDARD_DEDUCTION)
    tax, lower = 0.0, 0.0
    for upper, rate in SLABS:
        if taxable > lower:
            tax += (min(taxable, upper) - lower) * rate
        lower = upper
    if taxable <= REBATE_LIMIT:
        tax = 0.0
    else:
        tax = min(tax, taxable - REBATE_LIMIT)  # marginal relief just above the rebate limit
    return round(tax * (1 + CESS))


def estimate(
    fixed_annual: float,
    variable_annual: float = 0.0,
    variable_payout_percent: float = 100.0,
    joining_bonus: float = 0.0,
    basic_percent: float = 40.0,
    professional_tax_annual: float = 2400.0,
) -> dict:
    basic = fixed_annual * basic_percent / 100
    employee_pf = round(basic * EMPLOYEE_PF_RATE)
    employer_pf = employee_pf
    variable_paid = variable_annual * variable_payout_percent / 100

    gross = fixed_annual + variable_paid + joining_bonus
    tax_total = income_tax(gross)
    tax_fixed_only = income_tax(fixed_annual)

    annual_in_hand = gross - tax_total - employee_pf - professional_tax_annual
    monthly_regular = (fixed_annual - tax_fixed_only - employee_pf - professional_tax_annual) / 12
    extra_net = (variable_paid + joining_bonus) - (tax_total - tax_fixed_only)
    ctc = fixed_annual + variable_annual + employer_pf

    def pct(part: float) -> float:
        return round(100 * part / ctc, 1) if ctc else 0.0

    return {
        "ctc_estimate": round(ctc),
        "fixed_annual": round(fixed_annual),
        "variable_annual": round(variable_annual),
        "variable_paid_annual": round(variable_paid),
        "joining_bonus": round(joining_bonus),
        "employer_pf_annual": employer_pf,
        "fixed_percent_of_ctc": pct(fixed_annual),
        "variable_percent_of_ctc": pct(variable_annual),
        "employee_pf_annual": employee_pf,
        "professional_tax_annual": round(professional_tax_annual),
        "income_tax_annual": tax_total,
        "annual_in_hand": round(annual_in_hand),
        "monthly_in_hand_regular": round(monthly_regular),
        "variable_and_bonus_net_annual": round(extra_net),
        "assumptions": [
            f"Tax estimate: {TAX_BASIS}, standard deduction of {STANDARD_DEDUCTION:,}.",
            f"Basic pay is assumed to be {basic_percent:g}% of fixed pay; employee PF is {EMPLOYEE_PF_RATE:.0%} of basic.",
            "Employer PF is assumed equal to employee PF and is counted in CTC but not in your take-home.",
            f"Variable pay is assumed to be paid out at {variable_payout_percent:g}% of target.",
            "Monthly in-hand covers regular fixed pay only; variable pay and any joining bonus arrive separately.",
            "HRA exemptions, NPS, insurance, reimbursements and state-specific professional tax are not modelled.",
        ],
    }


def compare_offers(offers: list[dict]) -> dict:
    rows = sorted(offers, key=lambda o: o["estimate"]["annual_in_hand"], reverse=True)
    best = rows[0]["estimate"]["annual_in_hand"] if rows else 0
    out = []
    for offer in rows:
        est = offer["estimate"]
        out.append(
            {
                "id": offer["id"],
                "company": offer["company"],
                "role": offer["role"],
                "ctc_estimate": est["ctc_estimate"],
                "fixed_annual": est["fixed_annual"],
                "variable_annual": est["variable_annual"],
                "monthly_in_hand_regular": est["monthly_in_hand_regular"],
                "annual_in_hand": est["annual_in_hand"],
                "gap_to_best_annual": best - est["annual_in_hand"],
            }
        )
    return {
        "ranked_by": "estimated annual in-hand pay",
        "offers": out,
        "note": "Compare more than pay: growth, learning, stability, location and notice-period costs are not measured here.",
    }


# ---------------------------------------------------------------- negotiation message (local AI)

class _Message(BaseModel):
    subject: str = ""
    body: str = ""

    @field_validator("subject", "body", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v).strip()


_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {m.group().replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


def draft_negotiation(cand: dict, offer: dict, options: dict) -> dict:
    est = offer["estimate"]
    facts = [
        f"Company: {offer['company']}",
        f"Role: {offer['role']}",
        f"Offered fixed pay per year: {est['fixed_annual']}",
        f"Offered variable pay per year: {est['variable_annual']}",
    ]
    if options.get("target_fixed_annual"):
        facts.append(f"Candidate's requested fixed pay per year: {round(options['target_fixed_annual'])}")
    if options.get("target_variable_annual") is not None:
        facts.append(f"Candidate's requested variable pay per year: {round(options['target_variable_annual'])}")
    for point in options.get("points_to_highlight", []):
        facts.append(f"Candidate strength to mention: {point}")
    if options.get("leverage_notes"):
        facts.append(f"Additional context from the candidate: {options['leverage_notes']}")
    facts_text = "\n".join(facts)

    wrapped_facts, _ = wrap_untrusted("negotiation_facts", facts_text, max_chars=2500)
    wrapped_profile, _ = wrap_untrusted("candidate_profile", summarize_candidate(cand), max_chars=2500)
    tone = "warm and appreciative" if options.get("tone") == "polite" else "confident and direct but respectful"
    prompt = (
        "Write a salary negotiation email from the candidate to the recruiter.\n"
        'Return JSON: {"subject": string, "body": string}\n'
        f"Tone: {tone}. Length: 120 to 200 words.\n"
        "Rules:\n"
        "- Use ONLY the facts and the candidate profile below. Do not invent competing offers, achievements, numbers or deadlines.\n"
        "- Thank them for the offer, state the request clearly, and justify it with the strengths provided.\n"
        "- Do not threaten, bluff, or mention other offers unless the candidate's context says so.\n"
        f"- Sign off with the candidate's name: {cand['full_name'] or 'the candidate'}.\n"
        "- No placeholders in square brackets.\n\n" + wrapped_facts + "\n\n" + wrapped_profile
    )
    message = get_ai_service().generate_structured(SYSTEM_BASE, prompt, _Message)

    allowed = _numbers(facts_text) | _numbers(summarize_candidate(cand))
    warnings = []
    unsupported = sorted(n for n in _numbers(message.body) if n not in allowed)
    if unsupported:
        warnings.append("Check these figures, they were not in your inputs: " + ", ".join(unsupported[:6]))
    if re.search(r"\[[^\]]+\]", message.body):
        warnings.append("The draft contains a bracketed placeholder. Replace it before sending.")
    return {"subject": message.subject[:200], "body": message.body[:2500], "warnings": warnings}
