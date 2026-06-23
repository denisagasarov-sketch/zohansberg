"""
Stage 11: сборщик Reels.

Собирает Reels через apify/instagram-reel-scraper.
Сортировка: сначала isPinned, потом топ по viewCount, до max_total.

Использование:
  python -m pipeline.stages.collect_reels --account vlada_kliuiko
  python -m pipeline.stages.collect_reels --account vlada_kliuiko --limit 30 --dry-run
"""

import argparse
import json
import logging
from datetime import datetime

from pipeline.core.apify_client import run_actor
from pipeline.core.config import get_account
from pipeline.core.paths import raw, normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTOR_ID     = "apify/instagram-reel-scraper"
MAX_SELECTED = 10

_FIELD_MAP = [
    ("reel_id",        ["id", "shortCode"]),
    ("url",            ["url", "shortCode"]),
    ("video_url",      ["videoUrl"]),
    ("thumbnail_url",  ["displayUrl"]),
    ("view_count",     ["videoPlayCount", "videoViewCount"]),
    ("likes_count",    ["likesCount"]),
    ("comments_count", ["commentsCount"]),
    ("video_duration", ["videoDuration"]),
    ("caption",        ["caption"]),
    ("transcript",     ["transcript"]),
    ("timestamp",      ["timestamp"]),
    ("is_pinned",      ["isPinned"]),
]


def _pick(item: dict, aliases: list):
    for key in aliases:
        v = item.get(key)
        if v is not None:
            return v
    return None


def _build_url(item: dict) -> str:
    url = item.get("url", "")
    if url.startswith("http"):
        return url
    short = item.get("shortCode") or item.get("id") or ""
    return f"https://www.instagram.com/p/{short}/" if short else ""


def _extract(item: dict, position: int) -> dict:
    out = {"position": position}
    for norm_key, aliases in _FIELD_MAP:
        out[norm_key] = _build_url(item) if norm_key == "url" else _pick(item, aliases)
    music = item.get("musicInfo") or {}
    out["uses_original_audio"] = music.get("uses_original_audio")
    return out


def collect(username: str, limit: int = 10, dry_run: bool = False) -> dict:
    """Собирает Reels аккаунта, возвращает нормализованный индекс."""
    acc = get_account(username)
    url = acc["url"]

    logger.info(f"[11] collect_reels | @{username} | limit={limit} | dry_run={dry_run}")

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {"dry_run": True, "account": username}

    raw_items = run_actor(
        actor_id=ACTOR_ID,
        input_data={
            "username": [username],
            "resultsLimit": limit,
            "includeTranscript": False,
            "proxy": {"useApifyProxy": True},
        },
    )

    # Сохраняем сырые данные
    raw_path = raw(username, "stage5c1_reels_raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Raw: {raw_path} ({len(raw_items)} items)")

    # Сортировка: сначала pinned, потом топ по viewCount
    pinned     = [r for r in raw_items if r.get("isPinned")]
    not_pinned = [r for r in raw_items if not r.get("isPinned")]
    not_pinned.sort(key=lambda r: int(r.get("videoPlayCount") or r.get("videoViewCount") or 0), reverse=True)
    selected = (pinned + not_pinned)[:MAX_SELECTED]

    reels = [_extract(item, i + 1) for i, item in enumerate(selected)]

    index = {
        "account":      username,
        "collected_at": datetime.utcnow().isoformat(),
        "total_raw":    len(raw_items),
        "total":        len(reels),
        "pinned_count": len(pinned),
        "reels":        reels,
    }

    norm_path = normalized(username, "stage5c1_reels_index.json")
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    norm_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Index: {norm_path}")

    print(f"\n=== Stage 11: Reels | @{username} ===")
    print(f"Собрано raw: {len(raw_items)} | выбрано: {len(reels)} | pinned: {len(pinned)}")
    print(f"Сохранено: {norm_path}")

    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 11: collect reels")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--limit",   type=int, default=10, help="Лимит (default: 10)")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать Apify")
    args = parser.parse_args()
    collect(args.account, args.limit, args.dry_run)
