"""Prompt-injection defences for untrusted content (resumes, job posts, emails, web pages).

Untrusted text is sanitised, truncated, wrapped in explicit delimiters and scanned for
known injection phrases. Detected phrases are reported to the caller as flags; they are
never obeyed. Untrusted content must never be able to authorise an external action.
"""
import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
DELIMITER_TAGS = re.compile(r"</?\s*untrusted_content[^>]*>", re.IGNORECASE)

INJECTION_PATTERNS = {
    "ignore_instructions": re.compile(
        r"ignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)", re.I
    ),
    "disregard_instructions": re.compile(r"disregard\s+.{0,40}(instructions|rules|prompt)", re.I),
    "role_override": re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(different|new)\b", re.I),
    "prompt_exfiltration": re.compile(
        r"(reveal|show|print|repeat|output)\s+.{0,30}(system\s+prompt|your\s+instructions|hidden\s+prompt)", re.I
    ),
    "action_request": re.compile(
        r"\b(send|forward|email|submit|apply)\b.{0,40}\b(resume|cv|personal\s+(data|information)|password|api\s*key)\b", re.I
    ),
    "fake_system_message": re.compile(r"^\s*(system|assistant)\s*:", re.I | re.M),
}


def sanitize_untrusted(text: str, max_chars: int) -> str:
    text = CONTROL_CHARS.sub("", text or "")
    text = DELIMITER_TAGS.sub("[removed-tag]", text)
    return text[:max_chars]


def detect_injection(text: str) -> list[str]:
    return [name for name, pattern in INJECTION_PATTERNS.items() if pattern.search(text or "")]


def wrap_untrusted(label: str, text: str, max_chars: int = 6000) -> tuple[str, list[str]]:
    """Return (wrapped_text, injection_flags) ready to embed in a prompt."""
    clean = sanitize_untrusted(text, max_chars)
    flags = detect_injection(clean)
    wrapped = f'<untrusted_content label="{label}">\n{clean}\n</untrusted_content>'
    return wrapped, flags
