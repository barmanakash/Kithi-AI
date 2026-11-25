"""Job Scam Detection Agent.

Rule-based and fully transparent: every signal reports the exact text that triggered it. The agent
never declares a listing "fraudulent" or "safe". It reports concern levels with evidence and an
explicit statement of uncertainty, plus steps the user can take to verify the employer.
"""
import re
from urllib.parse import urlparse

FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "yahoo.in", "outlook.com", "hotmail.com", "rediffmail.com", "proton.me", "protonmail.com", "aol.com", "live.com", "icloud.com"}
SUSPICIOUS_TLDS = {"xyz", "top", "click", "loan", "icu", "buzz", "gq", "tk", "ml", "cf", "ga", "work", "rest", "monster"}
URL_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "is.gd", "shorturl.at"}

SIGNALS = [
    ("upfront_payment", 35, "Asks the applicant to pay money",
     r"(registration|training|security|processing|joining|application|kit|refundable|verification)\s+(fee|deposit|charges?|amount)|pay\s+(a\s+)?(fee|deposit)|send\s+money|deposit\s+of\s+[₹$]"),
    ("cheque_scheme", 30, "Mentions sending funds or a cheque for equipment",
     r"(send|mail)\s+you\s+a\s+(check|cheque)|(check|cheque)\s+to\s+(purchase|buy)|reimburse\s+.{0,20}equipment"),
    ("sensitive_info_early", 25, "Requests sensitive identity or banking data",
     r"(aadhaar|aadhar|pan\s+card|bank\s+(account|details)|credit\s+card|\botp\b|passport\s+copy|\bssn\b|social\s+security)"),
    ("no_interview", 20, "Promises hiring without a normal interview process",
     r"no\s+interview|without\s+(an\s+)?interview|direct\s+(joining|selection)|instant\s+(joining|offer|hiring)"),
    ("guaranteed_income", 20, "Makes guaranteed or unrealistic income claims",
     r"guaranteed\s+(income|salary|job|placement)|earn\s+(up\s?to\s+)?[₹$]?\s?\d[\d,]*\s*(per|/)\s*(day|week|hour)|easy\s+money|work\s+from\s+home.{0,40}earn"),
    ("messaging_app_only", 15, "Directs applicants to a messaging app",
     r"(whatsapp|telegram|signal)\b.{0,60}(contact|apply|message|chat|number)|(contact|apply|message|chat).{0,60}(whatsapp|telegram)"),
    ("urgency", 8, "Uses pressure or urgency tactics",
     r"limited\s+(seats|vacanc)|apply\s+(immediately|now|today)\s+(only|or)|hurry|last\s+chance|urgently?\s+hiring"),
]


def _snippet(text: str, match: re.Match) -> str:
    start, end = max(0, match.start() - 40), min(len(text), match.end() + 40)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _domain_tokens(company: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", company.lower()) if t not in {"pvt", "ltd", "inc", "llc", "limited", "private", "technologies", "solutions", "services", "group", "corp"}}


def assess_text(text: str, company: str | None = None, url: str | None = None, contact_email: str | None = None) -> dict:
    text = text or ""
    signals: list[dict] = []

    for key, weight, description, pattern in SIGNALS:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            signals.append({"key": key, "weight": weight, "description": description, "evidence": _snippet(text, match)})

    emails = {e.lower() for e in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)}
    if contact_email:
        emails.add(contact_email.lower())
    for email in emails:
        domain = email.split("@", 1)[1]
        if domain in FREE_EMAIL_DOMAINS:
            signals.append({"key": "free_email_domain", "weight": 15, "description": "Contact uses a free personal email service instead of a company domain", "evidence": email})
        elif company:
            tokens = _domain_tokens(company)
            if tokens and not any(t in domain for t in tokens):
                signals.append({"key": "email_domain_mismatch", "weight": 10, "description": "Email domain does not appear to relate to the company name", "evidence": f"{email} vs company '{company}'"})

    urls = set(re.findall(r"https?://[^\s)>\"']+", text))
    if url:
        urls.add(url)
    for link in urls:
        host = (urlparse(link).hostname or "").lower()
        tld = host.rsplit(".", 1)[-1] if "." in host else ""
        if host in URL_SHORTENERS:
            signals.append({"key": "url_shortener", "weight": 10, "description": "Uses a link shortener that hides the real destination", "evidence": link})
        elif tld in SUSPICIOUS_TLDS:
            signals.append({"key": "suspicious_tld", "weight": 10, "description": f"Link uses a domain ending (.{tld}) often seen in throwaway sites", "evidence": link})

    word_count = len(text.split())
    if 0 < word_count < 60:
        signals.append({"key": "vague_listing", "weight": 8, "description": "Very little detail about the role or responsibilities", "evidence": f"Only {word_count} words"})

    # Collapse duplicate keys (e.g. several free emails) and cap the total.
    unique: dict[str, dict] = {}
    for signal in signals:
        unique.setdefault(signal["key"], signal)
    signals = list(unique.values())
    total = min(100, sum(s["weight"] for s in signals))

    if not signals:
        level = "no_flags_found"
    elif total >= 50:
        level = "high_concern"
    elif total >= 25:
        level = "medium_concern"
    else:
        level = "low_concern"

    confidence = "low" if word_count < 80 else "medium"
    return {
        "risk_level": level,
        "concern_score": total,
        "confidence": confidence,
        "signals": signals,
        "uncertainty": (
            "This is a rule-based check of the text you provided. It can miss scams and can flag genuine "
            "listings. It is not proof either way. Verify the employer independently before sharing "
            "personal information or paying anything."
        ),
        "verification_steps": [
            "Find the company's official website yourself (do not use links from the listing) and look for the same role on its careers page.",
            "Check that recruiter emails come from the company's own domain.",
            "Never pay fees, buy equipment or share bank or identity documents before a formal, verifiable offer.",
            "Search the company name with the words 'scam' or 'reviews' and check the registered business details.",
        ],
    }
