"""GitHub Portfolio Analyzer.

Reads PUBLIC data only from the GitHub REST API (no token, so GitHub's 60 requests/hour limit
applies). Everything reported is computed from that public data; nothing is invented, and no AI
is used, so results are reproducible and checkable on the user's own GitHub page.
"""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.utils.skills import extract_skills

USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_MIN_DT = datetime.min.replace(tzinfo=timezone.utc)


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def username_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if (parsed.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    first = parsed.path.strip("/").split("/")[0]
    return first if first and USERNAME_RE.match(first) else None


def _get(client: httpx.Client, path: str, params: dict | None = None):
    try:
        response = client.get(path, params=params)
    except httpx.HTTPError:
        raise GitHubError("Could not reach GitHub. Check your internet connection.", 502)
    if response.status_code == 404:
        raise GitHubError("That GitHub user was not found.", 404)
    if response.status_code in (403, 429):
        raise GitHubError("GitHub's rate limit was reached (60 requests per hour without a token). Try again later.", 429)
    if response.status_code >= 400:
        raise GitHubError(f"GitHub returned HTTP {response.status_code}.", 502)
    return response.json()


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def analyze_github(username: str, target_skills: list[str] | None = None) -> dict:
    if not USERNAME_RE.match(username or ""):
        raise GitHubError("That is not a valid GitHub username.", 422)

    with httpx.Client(
        base_url="https://api.github.com",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "KithiAI-local"},
        timeout=httpx.Timeout(10.0, connect=5.0),
    ) as client:
        user = _get(client, f"/users/{username}")
        repos = _get(client, f"/users/{username}/repos", {"per_page": 100, "type": "owner", "sort": "pushed"})

    own = [r for r in repos if not r.get("fork") and not r.get("archived")]
    cutoff = datetime.now(timezone.utc) - timedelta(days=180)
    recent = [r for r in own if (_parse(r.get("pushed_at")) or _MIN_DT) >= cutoff]
    described = [r for r in own if (r.get("description") or "").strip()]
    with_topics = [r for r in own if r.get("topics")]
    languages = Counter(r["language"] for r in own if r.get("language"))
    stars = sum(r.get("stargazers_count", 0) for r in own)

    ranked = sorted(own, key=lambda r: (r.get("stargazers_count", 0), _parse(r.get("pushed_at")) or _MIN_DT), reverse=True)
    top_repos = [
        {
            "name": r["name"],
            "url": r.get("html_url"),
            "stars": r.get("stargazers_count", 0),
            "language": r.get("language"),
            "description": (r.get("description") or "")[:160],
            "topics": (r.get("topics") or [])[:8],
            "last_pushed": r.get("pushed_at"),
        }
        for r in ranked[:5]
    ]

    strengths: list[str] = []
    improvements: list[str] = []
    if own:
        strengths.append(f"{len(own)} original (non-fork, non-archived) repositories analysed.")
    if languages:
        strengths.append("Main languages: " + ", ".join(f"{lang} ({n})" for lang, n in languages.most_common(5)) + ".")
    if recent:
        strengths.append(f"{len(recent)} repositories were updated in the last 6 months.")
    if stars:
        strengths.append(f"{stars} total stars across original repositories.")
    if own and len(described) / len(own) >= 0.7:
        strengths.append("Most repositories have a description.")

    if not own:
        improvements.append("No original public repositories found. Publish 2-3 projects that show your strongest skills.")
    else:
        if not recent:
            improvements.append("No repository has been updated in the last 6 months. Recent activity helps recruiters trust your skills.")
        if len(described) < len(own) * 0.7:
            improvements.append(f"{len(own) - len(described)} repositories have no description. Add one line saying what each project does.")
        if len(with_topics) < len(own) * 0.5:
            improvements.append("Few repositories use topics. Add topics such as the languages and frameworks used so they are searchable.")
        if not user.get("bio"):
            improvements.append("Your GitHub profile has no bio. Add a short headline that matches your resume.")

    evidence: dict[str, list[str]] = {}
    for repo in own:
        text = " ".join([repo.get("language") or "", " ".join(repo.get("topics") or []), repo.get("description") or "", repo["name"].replace("-", " ").replace("_", " ")])
        for skill in extract_skills(text):
            evidence.setdefault(skill, []).append(repo["name"])

    targets = list(dict.fromkeys(target_skills or []))
    target_evidence = {s: evidence[s][:5] for s in targets if s in evidence}
    missing = [s for s in targets if s not in evidence]

    limitations = ["Only public data is used. Private repositories are not visible."]
    if user.get("public_repos", 0) > 100:
        limitations.append("Only the 100 most recently pushed repositories were analysed.")
    limitations.append("Skills are detected from languages, topics, names and descriptions, so projects without them will not show evidence.")

    return {
        "profile": {
            "username": user.get("login"),
            "name": user.get("name"),
            "url": user.get("html_url"),
            "bio": user.get("bio"),
            "public_repos": user.get("public_repos"),
            "followers": user.get("followers"),
            "account_created": user.get("created_at"),
        },
        "metrics": {
            "original_repos": len(own),
            "recently_active_repos": len(recent),
            "repos_with_description": len(described),
            "repos_with_topics": len(with_topics),
            "total_stars": stars,
        },
        "languages": [{"language": lang, "repos": n} for lang, n in languages.most_common(8)],
        "top_repos": top_repos,
        "strengths": strengths,
        "improvements": improvements,
        "target_skill_evidence": target_evidence,
        "target_skills_without_projects": missing,
        "limitations": limitations,
    }
