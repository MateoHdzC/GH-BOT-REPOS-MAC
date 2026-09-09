import re
from typing import Optional

DEBOUNCE_PRESETS = [
    "1m",
    "4m",
    "5m (Recomendado)",
    "10m",
    "15m",
    "30m",
    "1h",
    "2h",
    "3h",
    "4h",
    "8h",
    "24h",
]


def parse_duration_string(value: str) -> Optional[int]:
    if not value:
        return None
    val = value.strip().lower()
    if val.isdigit():
        parsed = int(val)
        return parsed if parsed > 0 else None

    token = val.split()[0].rstrip(":,()")
    pattern = r"^(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?$"
    match = re.match(pattern, token) or re.match(pattern, val)
    if match and any(match.groups()):
        days, hours, minutes, seconds = match.groups()
        total = 0
        if days:
            total += int(days) * 86400
        if hours:
            total += int(hours) * 3600
        if minutes:
            total += int(minutes) * 60
        if seconds:
            total += int(seconds)
        return total if total > 0 else None

    return None


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    if seconds >= 86400 and seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds >= 3600 and seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds < 3600 and seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}m"
    if seconds < 60:
        return f"{seconds}s"

    h = seconds // 3600
    rem = seconds % 3600
    m = rem // 60
    s = rem % 60
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts)


def format_duration_display(seconds: int) -> str:
    short_fmt = format_duration(seconds)
    if short_fmt == "5m":
        return "5m (Recomendado)"
    return short_fmt
