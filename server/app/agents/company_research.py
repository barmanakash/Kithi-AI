"""Company Research Agent.

Researches PUBLIC information only:
- the company's own website (a few pages, fetched politely, honouring robots.txt, SSRF-safe), and
- the job postings you already saved for that company.

Design (nothing is invented):
1. Technologies, strengths to highlight and gaps to prepare are computed deterministically from the
   fetched text and your saved jobs. They work even when Ollama is off.
2. The local model only writes a short overview and a list of products/services from the website text.
   Every sentence and item must be grounded in that text (its words, numbers and skills must appear in
   the source) or it is dropped. If nothing survives, the website's own meta description is quoted instead.
3. Website text is untrusted input: it is wrapped, scanned for injection phrases and never obeyed.
4. The result lists its sources and says plainly what it could not find.
"""
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from pydantic import BaseModel, Field, field_validator

from app.core.prompt_guard import wrap_untrusted
from app.services.ai_service import AIServiceError, get_ai_service
from app.services.prompts import SYSTEM_BASE
from app.services.safe_fetch import USER_AGENT, FetchError, UnsafeURLError, fetch_public_page
from app.utils.coerce import as_str_list
from app.utils.html_text import extract_page_info
from app.utils.skills import extract_skills

MAX_PAGES = 4
MAX_PAGE_CHARS = 6000
PROMPT_CHARS = 5000
_PAGE_HINTS = ("about", "product", "solution", "service", "platform", "technology", "engineering", "career", "customer")

LIMITS = (
    "Only public information was used. Websites can be incomplete or out of date, and a small local model "
    "can miss things, so verify anything important on the company's own channels before an interview."
)


# --------------------------------------------------------------------------------------------------
# Fetching (network)
# --------------------------------------------------------------------------------------------------
class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def pick_links(html: str, base_url: str, limit: int = MAX_PAGES - 1) -> list[str]:
    """Same-site links that look like about/product/technology/careers pages (no query strings)."""
    parser = _LinkParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    base = urlparse(base_url)
    seen = {base_url.rstrip("/")}
    found: list[str] = []
    for href in parser.hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(base_url, href).split("#")[0]
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.hostname != base.hostname or parsed.query:
            continue
        if not any(hint in parsed.path.lower() for hint in _PAGE_HINTS):
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        found.append(url)
        if len(found) >= limit:
            break
    return found


def _robots(base_url: str) -> RobotFileParser | None:
    parsed = urlparse(base_url)
    try:
        _, text = fetch_public_page(f"{parsed.scheme}://{parsed.netloc}/robots.txt", timeout=8)
    except (FetchError, UnsafeURLError):
        return None
    parser = RobotFileParser()
    parser.parse(text.splitlines())
    return parser


def _page_record(url: str, html: str) -> dict:
    info = extract_page_info(html)
    return {"url": url, "title": info["title"][:150], "description": info["description"][:400], "text": info["text"][:MAX_PAGE_CHARS]}


def collect_pages(website: str) -> tuple[list[dict], list[str]]:
    """Read the homepage and a few relevant same-site pages.

    Returns (pages, warnings). Raises UnsafeURLError for a private/local address.
    """
    try:
        final_url, html = fetch_public_page(website)
    except FetchError as exc:
        return [], [f"Could not read the website: {exc}"]

    robots = _robots(final_url)
    if robots and not robots.can_fetch(USER_AGENT, final_url):
        return [], ["The site's robots.txt asks automated tools not to read it, so nothing was fetched."]

    pages = [_page_record(final_url, html)]
    for link in pick_links(html, final_url):
        if robots and not robots.can_fetch(USER_AGENT, link):
            continue
        try:
            url, page_html = fetch_public_page(link)
        except (FetchError, UnsafeURLError):
            continue
        pages.append(_page_record(url, page_html))
    return pages, []


# --------------------------------------------------------------------------------------------------
# Grounding (pure)
# --------------------------------------------------------------------------------------------------
_WORD = re.compile(r"[a-z][a-z0-9+#]{2,}")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_STOP = frozenset(
    "the and for with that this from are was were has have had will would can our your their its they them you not but all any "
    "more most into over under about than then also such per via using use used including include provides provide offers offer "
    "helps help make makes made based work works".split()
)


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text or "")}


def is_grounded(sentence: str, source_words: set[str], source_numbers: set[str], source_skills: set[str], min_ratio: float = 0.6) -> bool:
    """A sentence is kept only if the website text itself supports it."""
    words = _words(sentence)
    if len(words) < 3 or len(words & source_words) / len(words) < min_ratio:
        return False
    if not _numbers(sentence) <= source_numbers:
        return False
    return set(extract_skills(sentence)) <= source_skills


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# --------------------------------------------------------------------------------------------------
# AI (overview only)
# --------------------------------------------------------------------------------------------------
class OverviewOut(BaseModel):
    overview: str = ""
    products_services: list[str] = Field(default_factory=list)

    @field_validator("overview", mode="before")
    @classmethod
    def _text(cls, value):
        if isinstance(value, list):
            return " ".join(str(v) for v in value)
        return "" if value is None else str(value).strip()

    @field_validator("products_services", mode="before")
    @classmethod
    def _items(cls, value):
        return as_str_list(value)


_TASK = (
    "Describe what the company does using ONLY the website text below.\n"
    'Return JSON: {"overview": string, "products_services": [string]}\n'
    "Rules:\n"
    "- overview: 2 or 3 factual sentences, under 70 words.\n"
    "- products_services: up to 6 short items (2 to 6 words each) that the text explicitly names.\n"
    "- Do not add anything that is not in the text: no funding, headcount, revenue, dates, customers, awards or opinions.\n"
    "- If the text does not say what the company does, return an empty overview and an empty list.\n"
)


def _write_overview(company: str, site_text: str, source_skills: set[str]) -> tuple[str, list[str], dict]:
    wrapped, flags = wrap_untrusted("company_website", site_text, max_chars=PROMPT_CHARS)
    out = get_ai_service().generate_structured(SYSTEM_BASE, f"{_TASK}\nCompany: {company}\n\n{wrapped}", OverviewOut)

    source_words, source_numbers = _words(site_text), _numbers(site_text)
    kept = [s for s in _sentences(out.overview) if is_grounded(s, source_words, source_numbers, source_skills)]
    products = []
    for item in out.products_services[:8]:
        item = item.strip()[:80]
        words = _words(item)
        if item and words and len(words & source_words) / len(words) >= 0.8 and item.lower() not in {p.lower() for p in products}:
            products.append(item)
    return " ".join(kept)[:600], products[:6], flags


# --------------------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------------------
def build_research(company: str, pages: list[dict], job_texts: list[str], candidate_skills: set[str], use_ai: bool = True) -> dict:
    """Combine fetched pages and saved jobs into a research result. Pure apart from the optional AI call."""
    warnings: list[str] = []
    site_text = "\n\n".join(p["text"] for p in pages)
    site_skills = set(extract_skills(site_text)) if site_text else set()

    job_counts: Counter = Counter()
    for text in job_texts:
        job_counts.update(set(extract_skills(text)))

    technologies = []
    for skill in sorted(job_counts, key=lambda s: (-job_counts[s], s)):
        technologies.append({"skill": skill, "source": "both" if skill in site_skills else "your saved jobs", "jobs": job_counts[skill]})
    for skill in sorted(site_skills - set(job_counts)):
        technologies.append({"skill": skill, "source": "website", "jobs": 0})
    technologies = technologies[:20]
    for item in technologies:
        item["you_have"] = item["skill"] in candidate_skills

    strengths = [t["skill"] for t in technologies if t["you_have"]][:8]
    gaps = [t["skill"] for t in technologies if not t["you_have"]][:8]
    topics = [f"{s}: be ready to describe a real project where you used it." for s in strengths[:5]]
    topics += [f"{s}: it is not in your profile, so prepare an honest answer and say what you are doing to learn it." for s in gaps[:5]]

    overview, products, ai_error, flags, ai_used = "", [], None, [], False
    if site_text and len(site_text) >= 300:
        if use_ai:
            try:
                overview, products, flags = _write_overview(company, site_text, site_skills)
                ai_used = bool(overview or products)
                if not overview:
                    ai_error = "The local model's overview did not pass the fact check, so it was left out."
            except AIServiceError as exc:
                ai_error = str(exc)
        if not overview:
            description = next((p["description"] for p in pages if p["description"]), "")
            if description:
                overview = f"From the company's website: {description}"[:400]
    elif pages:
        warnings.append("The website had very little readable text (it may load content with JavaScript), so no overview could be written.")
    if flags:
        warnings.append("The website text contains wording aimed at AI tools. It was treated as data and ignored.")
    if ai_error:
        warnings.append(ai_error)
    if not pages and job_texts:
        warnings.append("No website was read. Technologies below come only from your saved jobs for this company.")

    return {
        "overview": overview,
        "products_services": products,
        "technologies": technologies,
        "strengths_to_highlight": strengths,
        "gaps_to_prepare": gaps,
        "interview_topics": topics,
        "sources": [{"url": p["url"], "title": p["title"]} for p in pages],
        "source_kind": "website" if pages else "saved_jobs" if job_texts else "none",
        "jobs_used": len(job_texts),
        "ai_used": ai_used,
        "ai_error": ai_error,
        "injection_flags": flags,
        "warnings": warnings,
        "limits": LIMITS,
    }
