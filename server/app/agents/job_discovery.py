"""Job Discovery Agent.

Only fetches from an explicit allow-list of public job-board APIs that publish listings for reuse.
Users cannot point it at arbitrary URLs. Results are normalised, filtered, and de-duplicated by the
caller. Source failures are reported, never hidden.
"""
import logging
import re

import httpx

from app.utils.html_text import html_to_text

logger = logging.getLogger("kithi.discovery")

HEADERS = {"User-Agent": "KithiAI/0.1 (local career assistant)", "Accept": "application/json"}
TIMEOUT = httpx.Timeout(15.0, connect=5.0)


def _tokens(query: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9+#.]{2,}", query.lower())]


def _matches_query(job: dict, tokens: list[str]) -> bool:
    haystack = f"{job['title']} {job['description']} {' '.join(job.get('tags', []))}".lower()
    return all(t in haystack for t in tokens) if tokens else True


def fetch_remotive(query: str, location: str | None, limit: int) -> list[dict]:
    response = httpx.get(
        "https://remotive.com/api/remote-jobs",
        params={"search": query, "limit": limit * 2},
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    jobs = []
    for item in response.json().get("jobs", []):
        loc = item.get("candidate_required_location") or "Worldwide"
        jobs.append(
            {
                "title": item.get("title") or "",
                "company": item.get("company_name") or "",
                "location": loc,
                "remote": True,
                "job_type": item.get("job_type"),
                "url": item.get("url"),
                "salary_text": item.get("salary") or None,
                "description": html_to_text(item.get("description") or ""),
                "source": "remotive",
                "source_id": str(item.get("id")),
                "tags": item.get("tags") or [],
                "posted_at": item.get("publication_date"),
            }
        )
    if location:
        loc_l = location.lower()
        jobs = [j for j in jobs if loc_l in j["location"].lower() or "worldwide" in j["location"].lower()]
    return jobs


def fetch_arbeitnow(query: str, location: str | None, limit: int) -> list[dict]:
    response = httpx.get("https://www.arbeitnow.com/api/job-board-api", headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    tokens = _tokens(query)
    jobs = []
    for item in response.json().get("data", []):
        job = {
            "title": item.get("title") or "",
            "company": item.get("company_name") or "",
            "location": item.get("location") or "",
            "remote": bool(item.get("remote")),
            "job_type": (item.get("job_types") or [None])[0],
            "url": item.get("url"),
            "salary_text": None,
            "description": html_to_text(item.get("description") or ""),
            "source": "arbeitnow",
            "source_id": str(item.get("slug")),
            "tags": item.get("tags") or [],
            "posted_at": None,
        }
        if not _matches_query(job, tokens):
            continue
        if location and location.lower() not in job["location"].lower() and not job["remote"]:
            continue
        jobs.append(job)
    return jobs


SOURCES = {"remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow}


def discover(query: str, location: str | None, limit: int, sources: list[str]) -> tuple[list[dict], dict[str, str]]:
    """Return (jobs, errors_by_source)."""
    collected: list[dict] = []
    errors: dict[str, str] = {}
    for name in sources:
        try:
            batch = SOURCES[name](query, location, limit)
        except httpx.HTTPError as exc:
            errors[name] = f"{type(exc).__name__}: source unavailable"
            logger.warning("Source %s failed: %s", name, exc)
            continue
        except (ValueError, KeyError, TypeError) as exc:
            errors[name] = "unexpected response format"
            logger.warning("Source %s returned unexpected data: %s", name, exc)
            continue
        collected.extend(j for j in batch if j["title"] and j["company"] and len(j["description"]) >= 20)
    # Trim per-source results fairly, then overall limit.
    return collected[: limit * max(1, len(sources))], errors
