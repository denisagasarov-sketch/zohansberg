"""
Stage 13: сборщик индекса постов.

Запускает apify/instagram-scraper (resultsType=posts),
сохраняет нормализованный индекс без GPT и без медиа.

Режимы:
  content_mode="period" — собрать посты за последние months_back месяцев (resultsLimit=200)
  content_mode="count"  — набрать target_count постов нужных типов (батчами по 50, макс 5 батчей)

Использование:
  python -m pipeline.stages.collect_posts --account vlada_kliuiko
  python -m pipeline.stages.collect_posts --account vlada_kliuiko --months-back 6 --dry-run
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

_BATCH_SIZE   = 50
_MAX_BATCHES  = 5


def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video"}.get(raw_type, "photo")


def _fetch_batch(url: str, limit: int) -> list:
    return run_actor(
        actor_id="apify/instagram-scraper",
        input_data={
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": limit,
            "proxy": {"useApifyProxy": True},
        },
    )


def collect(
    username: str,
    limit: int = 200,
    months_back: int = 6,
    dry_run: bool = False,
    post_types: list = None,       # None = все типы; ["photo", "carousel", "video"]
    content_mode: str = "period",  # "period" или "count"
    target_count: int = 30,        # используется когда content_mode="count"
    exclude_codes: list = None,    # shortCode постов, уже записанных в таблицу (режим append)
) -> dict:
    """
    Собирает индекс постов аккаунта.

    content_mode="period": посты за последние months_back месяцев (resultsLimit=limit).
    content_mode="count":  накапливает батчами по 50 до target_count отфильтрованных постов.

    # TODO: поддержать настройки content_mode/target_count/post_types на уровне аккаунта
    #       через accounts.json (ключи: content_mode, target_count, post_types)
    """
    acc = get_account(username)
    url = f"https://www.instagram.com/{username}/"

    logger.info(
        "[13] collect_posts | @%s | mode=%s | limit=%s | months_back=%s | "
        "post_types=%s | target_count=%s | dry_run=%s",
        username, content_mode, limit, months_back, post_types, target_count, dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {
            "dry_run": True, "account": username,
            "limit": limit, "months_back": months_back,
            "content_mode": content_mode,
        }

    # ------------------------------------------------------------------
    # Сбор сырых данных
    # ------------------------------------------------------------------
    if content_mode == "count":
        accumulated: list = []
        batches_done = 0
        for _ in range(_MAX_BATCHES):
            batch = _fetch_batch(url, _BATCH_SIZE)
            batches_done += 1
            logger.info("Батч %d: получено %d items", batches_done, len(batch))
            for item in batch:
                pt = _post_type(item.get("type", "Image"))
                if post_types is None or pt in post_types:
                    accumulated.append(item)
            if len(accumulated) >= target_count:
                break
            if len(batch) < _BATCH_SIZE:
                break  # Apify больше не отдаёт
        raw_items = accumulated[:target_count]
        skipped_old = 0
        logger.info(
            "count-режим: %d батчей, накоплено %d → обрезано до %d",
            batches_done, len(accumulated), len(raw_items),
        )

    else:  # content_mode == "period"
        raw_items = _fetch_batch(url, limit)
        cutoff = datetime.now(timezone.utc) - timedelta(days=months_back * 30)
        filtered: list = []
        skipped_old = 0
        for item in raw_items:
            ts = item.get("timestamp", "")
            if ts:
                try:
                    post_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if post_dt >= cutoff:
                        filtered.append(item)
                    else:
                        skipped_old += 1
                except Exception:
                    filtered.append(item)
            else:
                filtered.append(item)
        logger.info("Дата-фильтр: оставлено %d, пропущено старых %d", len(filtered), skipped_old)
        raw_items = filtered

    # ------------------------------------------------------------------
    # Фильтр по типу (для period-режима; в count-режиме уже отфильтровано)
    # ------------------------------------------------------------------
    if post_types is not None and content_mode == "period":
        before = len(raw_items)
        raw_items = [
            item for item in raw_items
            if _post_type(item.get("type", "Image")) in post_types
        ]
        logger.info("Тип-фильтр: %d → %d (разрешены: %s)", before, len(raw_items), post_types)

    # ------------------------------------------------------------------
    # Дедупликация (режим append): исключаем посты, уже записанные в таблицу
    # ------------------------------------------------------------------
    if exclude_codes:
        exclude_set = {str(c).strip() for c in exclude_codes if str(c).strip()}
        before = len(raw_items)
        raw_items = [
            item for item in raw_items
            if (item.get("shortCode") or "") not in exclude_set
        ]
        logger.info(
            "Дедуп-фильтр: %d → %d (исключено уже записанных: %d)",
            before, len(raw_items), before - len(raw_items),
        )

    # ------------------------------------------------------------------
    # Сохраняем сырые данные
    # ------------------------------------------------------------------
    raw_path = raw(username, "stage5e0_posts_raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Raw: %s (%d items)", raw_path, len(raw_items))

    # ------------------------------------------------------------------
    # Нормализуем
    # ------------------------------------------------------------------
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
        "content_mode": content_mode,
        "apify_limit":  limit,
        "months_back":  months_back,
        "total":        len(posts),
        "by_type":      by_type,
        "posts":        posts,
    }

    norm_path = normalized(username, "stage5e0_posts_index.json")
    norm_path.parent.mkdir(parents=True, exist_ok=True)
    norm_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Index: %s", norm_path)

    print(f"\n=== Stage 13: Posts Index | @{username} ===")
    print(f"Режим: {content_mode} | Собрано: {len(posts)} постов")
    if content_mode == "period":
        print(f"  Глубина: {months_back} мес., пропущено старых: {skipped_old}")
    for t, n in by_type.items():
        print(f"  {t}: {n}")
    print(f"Сохранено: {norm_path}")

    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 13: collect posts index")
    parser.add_argument("--account",      required=True,            help="Instagram username")
    parser.add_argument("--limit",        type=int, default=200,    help="Лимит для period-режима (default: 200)")
    parser.add_argument("--months-back",  type=int, default=6,      help="Глубина выборки в месяцах (default: 6)")
    parser.add_argument("--mode",         default="period",         help="period или count (default: period)")
    parser.add_argument("--target-count", type=int, default=30,     help="Целевое кол-во постов для count-режима (default: 30)")
    parser.add_argument("--post-types",   nargs="+",                help="Фильтр типов: photo carousel video")
    parser.add_argument("--dry-run",      action="store_true",      help="Не вызывать Apify")
    args = parser.parse_args()
    collect(
        args.account,
        limit=args.limit,
        months_back=args.months_back,
        dry_run=args.dry_run,
        post_types=args.post_types,
        content_mode=args.mode,
        target_count=args.target_count,
    )
