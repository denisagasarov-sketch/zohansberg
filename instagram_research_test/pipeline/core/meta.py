from datetime import datetime
import json
from pipeline.core.paths import normalized

BLOCK_TTL_DAYS = {
    "profile":    30,
    "pinned":     30,
    "bio":        30,
    "landing":    30,
    "highlights": 14,
    "reels":       7,
    "posts":       7,
}

STAGE_TO_BLOCK = {
    "01": "profile", "02": "pinned", "03": "pinned", "04": "pinned",
    "05": "bio",     "06": "landing", "07": "landing",
    "08": "highlights", "09": "highlights", "10": "highlights",
    "11": "reels",   "12": "reels",
    "13": "posts",   "14": "posts",
    "15": None,      "15b": None,    "16": None,
}

def get_meta(username: str) -> dict:
    path = normalized(username, "meta.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def update_meta(username: str, block: str) -> None:
    path = normalized(username, "meta.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = get_meta(username)
    meta[block] = datetime.now().strftime("%d.%m.%Y %H:%M")
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

def get_staleness(username: str) -> dict:
    meta = get_meta(username)
    result = {}
    for block, ttl in BLOCK_TTL_DAYS.items():
        last = meta.get(block)
        if not last:
            result[block] = {"last_run": None, "days_ago": None, "is_stale": True}
            continue
        try:
            dt = datetime.strptime(last, "%d.%m.%Y %H:%M")
            days_ago = (datetime.now() - dt).days
        except Exception:
            result[block] = {"last_run": last, "days_ago": None, "is_stale": True}
            continue
        result[block] = {
            "last_run": last,
            "days_ago": days_ago,
            "is_stale": days_ago >= ttl,
        }
    return result
