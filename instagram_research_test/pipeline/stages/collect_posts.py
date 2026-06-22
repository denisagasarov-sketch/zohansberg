"""
Stage 13: сборщик индекса постов.

Запускает apify/instagram-scraper (resultsType=posts),
сохраняет нормализованный индекс без GPT и без медиа.

Использование:
  python pipeline/stages/13_collect_posts.py --account vlada_kliuiko
  python pipeline/stages/13_collect_posts.py --account vlada_kliuiko --months-back 6 --dry-run
"""

import argparse
import json
import logging
from datetime import datetime, timezone, timedelta

from pipeline.core.apify_client import run_actor
from pipeline.core.config import get_account
from pipeline.core.paths import raw, normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video"}.get(raw_type, "photo")


def collect(username: str, limit: int = 200, months_back: int = 6, dry_run: bool = False) -> dict:
    """
    Собирает индекс постов аккаунта за последние months_back месяцев.
    Возвращает нормализованный индекс (dict).
    """
    acc = get_account(username)
    url = f"https://www.instagram.com/{username}/"

    logger.info(f"[13] collect_posts | @{username} | limit={limit} | months_back={months_back} | dry_run={dry_run}")

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {"dry_run": True, "account": username, "limit": limit, "months_back": months_back}

    raw_items = run_actor(
        actor_id="apify/instagram-scraper",
        input_data={
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": limit,
            "proxy": {"useApifyProxy": True},
        },
    )

    # Фильтрация по дате: оставляем посты за последние months_back месяцев
    cutoff = datetime.now(timezone.utc) - timedelta(days=months_back * 30)
    filtered_items = []
    skipped_old = 0
    for item in raw_items:
        ts = item.get("timestamp", "")
        if ts:
            try:
                post_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if post_dt >= cutoff:
                    filtered_items.append(item)
                else:
                    skipped_old += 1
            except Exception:
                filtered_items.append(item)
        else:
            filtered_items.append(item)
    logger.info(f"Дата-фильтр: оставлено {len(filtered_items)}, пропущено старых {skipped_old}")
    raw_items = filtered_items

    # Сохраняем сырые данные
    raw_path = raw(username, "stage5e0_posts_raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Raw: {raw_path} ({len(raw_items)} items)")

    # Нормализуем
    posts = []
    by_type: dict = {"photo": 0, "carousel": 0, "video": 0}
    for post in raw_items:
        pt = _post_type(post.get("type", "Image"))
        by_type[pt] = by_type.get(pt, 0) + 1
        posts.append({
            "url":             post.get("url", ""),
            "short_code":      post.get("shortCode", ""),
            "post_type":       pt,
            "raw_type":        post.get("type", "Image"),
            "likes":           int(post.get("likesCount") or 0),
            "comments":        int(post.get("commentsCount") or 0),
            "views":           int(post.get("videoPlayCount") or post.get("videoViewCount") or 0),
            "slides_count":    len(post.get("childPosts") or post.get("images") or []),
            "timestamp":       post.get("timestamp", ""),
            "caption_preview": (post.get("caption") or "")[:120],
        })

    index = {
        "account":      username,
        "collected_at": datetime.utcnow().isoformat(),
        "apify_limit":  limit,
        "months_back":  months_back,
        "total":        len(posts),
        "by_type":      by_type,
        "posts":        posts,
    }

    norm_path = normalized(username, "stage5e0_posts_index.json")
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    norm_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Index: {norm_path}")

    print(f"\n=== Stage 13: Posts Index | @{username} ===")
    print(f"Собрано: {len(posts)} постов (за {months_back} мес., пропущено старых: {skipped_old})")
    for t, n in by_type.items():
        print(f"  {t}: {n}")
    print(f"Сохранено: {norm_path}")

    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 13: collect posts index")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--limit", type=int, default=200, help="Лимит запроса к Apify (default: 200)")
    parser.add_argument("--months-back", type=int, default=6, help="Глубина выборки в месяцах (default: 6)")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать Apify")
    args = parser.parse_args()
    collect(args.account, args.limit, args.months_back, args.dry_run)
