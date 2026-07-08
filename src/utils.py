import re
from datetime import datetime, timezone

def parse_reddit_score(text: str) -> int:
    if not text:
        return 0
    text = text.lower().replace("points", "").replace("point", "").replace(",", "").strip()
    if text == "•" or "hidden" in text:
        return 0
    match = re.match(r"([-+]?[0-9.]+)\s*([km]?)", text)
    if not match:
        return 0
    try:
        num = float(match.group(1))
        suffix = match.group(2)
        if suffix == "k":
            num *= 1000
        elif suffix == "m":
            num *= 1000000
        return int(num)
    except ValueError:
        return 0


def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escaped = text
    for char in ["\\", "`", "*", "_", "#", "|"]:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def is_deleted_or_removed(item: dict) -> bool:
    selftext = item.get("selftext") or ""
    body = item.get("body") or ""
    author = item.get("author") or ""
    
    placeholders = {"[deleted]", "[removed]"}
    
    if selftext.strip() in placeholders or body.strip() in placeholders:
        return True
    if author == "[deleted]":
        return True
    # Detect common archive/API deletion indicators
    if item.get("removed_by_category"):
        return True
    if item.get("deleted") is True or item.get("removed") is True:
        return True
    return False


def _get_fullname(item: dict, kind: str) -> str | None:
    name = item.get("name")
    if name:
        return name
    item_id = item.get("id")
    if item_id:
        prefix = "t3_" if kind == "submitted" else "t1_"
        if not str(item_id).startswith(prefix):
            return f"{prefix}{item_id}"
        return item_id
    return None


def _hour_weekday(created_utc: float) -> tuple[int, int]:
    dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
    return dt.hour, dt.weekday()
