"""SSRF-safe page fetching for user-supplied URLs (company research, job pages).

Only public http(s) hosts are allowed. Every redirect hop is re-validated. Responses are
size-limited and must be HTML/text. (A determined DNS-rebinding attacker is out of scope for a
single-user local app, but private, loopback and link-local addresses are always blocked.)
"""
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

MAX_BYTES = 500_000
MAX_REDIRECTS = 3
USER_AGENT = "KithiAI/0.1 (+local career assistant; respectful single-page fetch)"


class UnsafeURLError(Exception):
    pass


class FetchError(Exception):
    pass


def assert_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise UnsafeURLError("Only http(s) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed")
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror:
        raise UnsafeURLError("The host name could not be resolved")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise UnsafeURLError("URLs pointing to private or local network addresses are not allowed")
    return url


def fetch_public_page(url: str, timeout: float = 15.0) -> tuple[str, str]:
    """Return (final_url, html_text). Raises UnsafeURLError or FetchError."""
    current = assert_public_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                with client.stream("GET", current) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("Redirect without a location")
                        current = assert_public_url(urljoin(current, location))
                        continue
                    if response.status_code >= 400:
                        raise FetchError(f"The site returned HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "").lower()
                    if "html" not in content_type and "text" not in content_type:
                        raise FetchError("The URL did not return an HTML page")
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        chunks.append(chunk)
                        if size >= MAX_BYTES:
                            break
                    encoding = response.encoding or "utf-8"
                    return current, b"".join(chunks)[:MAX_BYTES].decode(encoding, errors="replace")
            except httpx.HTTPError as exc:
                raise FetchError(f"Could not fetch the page ({type(exc).__name__})")
    raise FetchError("Too many redirects")
