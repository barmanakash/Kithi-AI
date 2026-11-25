import re
from typing import Any


def as_str_list(value: Any) -> list[str]:
    """Coerce sloppy small-model output into a clean list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[,\n]", value) if part.strip()]
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            if isinstance(item, dict):
                item = next((str(v) for v in item.values() if isinstance(v, str)), "")
            text = str(item).strip()
            if text:
                out.append(text)
        return out
    return [str(value).strip()]


def as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(\.\d+)?", str(value))
    return float(match.group()) if match else None


def as_int(value: Any, default: int = 0) -> int:
    number = as_float(value)
    return int(number) if number is not None else default
