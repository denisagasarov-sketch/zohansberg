"""Stage 5E-0: Posts Index Collector.

Лёгкий сборщик индекса постов. Без GPT, без скачивания медиа.
Запускает apify/instagram-scraper (resultsType=posts), сохраняет
сырой ответ и нормализованный индекс постов.

Usage:
    python scripts/stage5e0_posts_index.py --account vlada_kliuiko --dry-run
    python scripts/stage5e0_posts_index.py --account vlada_kliuiko --limit 50
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

BASE     = Path(__file__).parent.parent
ACTOR_ID = "apify/instagram-scraper"
STAGE    = "stage5e0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video", "Image": "photo"}.get(raw_type, "photo")


def _build_url(item: dict) -> str:
    url = item.get("url") or ""
    if url.startswith("http"):
        return url
    short = item.get("shortCode") or item.get("id") or ""
    return f"https://www.instagram.com/p/{short}/" if short else ""


def _slides_count(item: dict, post_type: str) -> int:
    if post_type != "carousel":
        return 0
    child = item.get("childPosts") or []
    if child:
        return len(child)
    return len(item.get("images") or [])


def _extract_post(item: dict) -> dict:
    raw_type  = item.get("type") or "Image"
    post_type = _post_type(raw_type)
    caption   = item.get("caption") or ""
    return {
        "url":             _build_url(item),
        "short_code":      item.get("shortCode") or item.get("id") or "",
        "post_type":       post_type,
        "raw_type":        raw_type,
        "likes":           int(item.get("likesCount")    or 0),
        "comments":        int(item.get("commentsCount") or 0),
        "views":           int(item.get("videoPlayCount") or item.get("videoViewCount") or 0),
        "slides_count":    _slides_count(item, post_type),
        "timestamp":       item.get("timestamp") or "",
        "caption_preview": caption[:120],
    }


def _load_accounts_config() -> dict:
    path = BASE / "data" / "accounts.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _get_account_url(username: str, accounts_cfg: dict) -> str:
    """Return Instagram profile URL for username from accounts.json, or construct it."""
    for entry in (accounts_cfg.get("accounts") or []):
        if username in str(entry):
            return str(entry).rstrip("/") + "/"
    return f"https://www.instagram.com/{username}/"


def _build_run_input(account_url: str, limit: int) -> dict:
    return {
        "directUrls":   [account_url],
        "resultsType":  "posts",
        "resultsLimit": limit,
        "proxy":        {"useApifyProxy": True},
    }


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(username: str, limit: int, accounts_cfg: dict):
    account_url = _get_account_url(username, accounts_cfg)
    run_input   = _build_run_input(account_url, limit)

    print("[DRY-RUN] No Apify call. No files written.\n")
    print(f"Actor:        {ACTOR_ID}")
    print(f"Account:      @{username}")
    print(f"Account URL:  {account_url}")
    print(f"resultsLimit: {limit}")
    print()
    print("Input payload that WOULD be sent:")
    print(json.dumps(run_input, ensure_ascii=False, indent=2))
    print()

    raw_path  = BASE / "data" / username / "raw"        / "stage5e0_posts_raw.json"
    norm_path = BASE / "data" / username / "normalized" / "stage5e0_posts_index.json"
    print("Output paths that WOULD be written:")
    print(f"  {raw_path.relative_to(BASE)}")
    print(f"  {norm_path.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5E-0: Posts Index Collector (apify/instagram-scraper)"
    )
    parser.add_argument("--account", required=True,
                        help="Instagram username (обязательный)")
    parser.add_argument("--limit",   type=int, default=50,
                        help="Количество постов для Apify resultsLimit (default: 50)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать payload без вызова Apify")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    accounts_cfg = _load_accounts_config()

    if args.dry_run:
        run_dry_run(args.account, args.limit, accounts_cfg)
        return

    # --- Real run ---
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
    except ImportError:
        pass

    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        sys.exit("[ERROR] APIFY_TOKEN not set in .env")

    try:
        from apify_client import ApifyClient
    except ImportError:
        sys.exit("apify-client not installed — run: pip install apify-client")

    account_url = _get_account_url(args.account, accounts_cfg)
    run_input   = _build_run_input(account_url, args.limit)

    print(f"=== Stage 5E-0: Posts Index | @{args.account} ===")
    print(f"Actor:        {ACTOR_ID}")
    print(f"Account URL:  {account_url}")
    print(f"resultsLimit: {args.limit}")
    print(f"Input:        {json.dumps(run_input)}")
    print()
    print("Starting Apify run...")

    client = ApifyClient(token)
    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        sys.exit(f"[ERROR] Apify actor call failed: {e}")

    run_id     = run.get("id", "")
    dataset_id = run.get("defaultDatasetId", "")
    status     = run.get("status", "")
    print(f"Run ID:     {run_id}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Status:     {status}")

    if status != "SUCCEEDED":
        sys.exit(f"[ERROR] Run did not succeed (status={status})")

    print("Fetching dataset items...")
    try:
        raw_items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        sys.exit(f"[ERROR] Failed to fetch dataset: {e}")

    print(f"Raw items fetched: {len(raw_items)}")

    # Save raw
    raw_dir  = BASE / "data" / args.account / "raw"
    norm_dir = BASE / "data" / args.account / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "stage5e0_posts_raw.json"
    raw_path.write_text(json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Raw saved: %s", raw_path.relative_to(BASE))

    # Normalize
    posts   = [_extract_post(item) for item in raw_items]
    by_type = {"photo": 0, "carousel": 0, "video": 0}
    for p in posts:
        pt = p["post_type"]
        by_type[pt] = by_type.get(pt, 0) + 1

    index = {
        "account":      args.account,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "apify_limit":  args.limit,
        "total":        len(posts),
        "by_type":      by_type,
        "posts":        posts,
    }

    norm_path = norm_dir / "stage5e0_posts_index.json"
    norm_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    # Summary
    print()
    print(f"=== Stage 5E-0: Posts Index | @{args.account} ===")
    print(f"Собрано: {len(posts)} постов")
    for pt in ("photo", "carousel", "video"):
        n = by_type.get(pt, 0)
        print(f"  {pt + ':':<12}{n}")
    print(f"Сохранено: {norm_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
