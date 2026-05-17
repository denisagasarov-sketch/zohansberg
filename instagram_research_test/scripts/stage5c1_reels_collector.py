"""Stage 5C-1: Reels Collector.

Collects Reels via apify/instagram-reel-scraper, saves raw data, then
normalizes: all isPinned reels first, then top by viewCount, up to max_total.

Usage:
    python scripts/stage5c1_reels_collector.py --dry-run
    python scripts/stage5c1_reels_collector.py --dry-run --limit 20
    python scripts/stage5c1_reels_collector.py --account vlada_kliuiko
    python scripts/stage5c1_reels_collector.py --account vlada_kliuiko --limit 30
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE       = Path(__file__).parent.parent
ACTOR_ID   = "apify/instagram-reel-scraper"

_RU_DAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
STAGE      = "stage5c1"
MAX_SELECTED = 10   # max reels in normalized output

# Fields to carry into normalized output (with fallback aliases)
# Real actor schema (confirmed 2026-05-16): displayUrl (not thumbnailUrl), videoPlayCount (not viewCount)
# transcript requires includeTranscript:true in input — returns plain string when available
_FIELD_MAP = [
    ("reel_id",        ["id", "shortCode"]),
    ("url",            ["url", "shortCode"]),     # post-processed below
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


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _pick(item: dict, aliases: list):
    for key in aliases:
        v = item.get(key)
        if v is not None:
            return v
    return None


def _build_reel_url(item: dict) -> str:
    # Actor returns full URL like https://www.instagram.com/p/<shortCode>/
    url = item.get("url") or ""
    if url.startswith("http"):
        return url
    short = item.get("shortCode") or item.get("id") or ""
    if short:
        return f"https://www.instagram.com/p/{short}/"
    return ""


def _extract_reel(item: dict, position: int) -> dict:
    out = {"position": position}
    for norm_key, aliases in _FIELD_MAP:
        if norm_key == "url":
            out["url"] = _build_reel_url(item)
        else:
            out[norm_key] = _pick(item, aliases)

    # Derived: uses_original_audio from nested musicInfo
    music_info = item.get("musicInfo") or {}
    out["uses_original_audio"] = music_info.get("uses_original_audio")

    # Derived: hashtags extracted from caption
    caption_raw = out.get("caption") or ""
    out["hashtags"] = ", ".join(re.findall(r"#\w+", caption_raw))

    # Derived: day_of_week from timestamp
    ts = out.get("timestamp")
    out["day_of_week"] = ""
    if ts:
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            else:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            out["day_of_week"] = _RU_DAYS[dt.weekday()]
        except Exception:
            pass

    return out


def normalize_reels(raw_items: list, max_total: int = MAX_SELECTED) -> tuple[list, str]:
    """Return (selected_reels, strategy_label).

    Strategy:
    - If any item has isPinned field: pinned first, then top by viewCount.
    - Otherwise: top by viewCount only.
    """
    has_pinned_field = any("isPinned" in r for r in raw_items)

    def view_key(r):
        return r.get("viewCount") or r.get("videoPlayCount") or 0

    if has_pinned_field:
        pinned     = [r for r in raw_items if r.get("isPinned")]
        non_pinned = sorted(
            [r for r in raw_items if not r.get("isPinned")],
            key=view_key, reverse=True,
        )
        selected  = pinned + non_pinned
        selected  = selected[:max_total]
        strategy  = "pinned_first_then_top_by_views"
    else:
        selected = sorted(raw_items, key=view_key, reverse=True)[:max_total]
        strategy = "top_by_views"

    return [_extract_reel(r, i + 1) for i, r in enumerate(selected)], strategy


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(account: str, limit: int, include_transcript: bool):
    print("[DRY-RUN] No Apify call. No files written.\n")
    print(f"Actor:              {ACTOR_ID}")
    print(f"Account:            @{account}")
    print(f"resultsLimit:       {limit}")
    print(f"includeTranscript:  {include_transcript}")
    print(f"max_selected:       {MAX_SELECTED}")
    print()
    run_input = {"username": [account], "resultsLimit": limit}
    if include_transcript:
        run_input["includeTranscript"] = True
    print("Input payload that WOULD be sent:")
    print(json.dumps(run_input, indent=2))
    print()

    raw_dir  = BASE / "data" / account / "raw"
    norm_dir = BASE / "data" / account / "normalized"
    print("Output paths that WOULD be written:")
    print(f"  {(raw_dir  / 'stage5c1_reels_raw.json').relative_to(BASE)}")
    print(f"  {(norm_dir / 'stage5c1_reels_index.json').relative_to(BASE)}")
    print()
    print("Estimated cost:")
    cost = round(limit * 0.0026, 4)
    print(f"  {limit} reels × $0.0026 = ${cost:.4f}")
    if include_transcript:
        print("  (transcript via Whisper is included in actor price — no extra cost)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5C-1: Reels Collector (apify/instagram-reel-scraper)"
    )
    parser.add_argument("--account",       default="vlada_kliuiko",
                        help="Instagram username to collect Reels for")
    parser.add_argument("--limit",         type=int, default=10,
                        help="How many Reels to collect (resultsLimit, default: 10)")
    parser.add_argument("--no-transcript", action="store_true",
                        help="Skip transcript extraction (faster, same $0.0026/reel cost)")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Show what would happen; no Apify call, no files written")
    args = parser.parse_args()

    account            = args.account
    limit              = args.limit
    include_transcript = not args.no_transcript

    if args.dry_run:
        run_dry_run(account, limit, include_transcript)
        return

    # --- Real run ---
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
    except ImportError:
        pass

    token = os.environ.get("APIFY_TOKEN", "")
    if not token:
        print("[ERROR] APIFY_TOKEN not set in .env", file=sys.stderr)
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client    = ApifyClient(token)
    run_input = {"username": [account], "resultsLimit": limit}
    if include_transcript:
        run_input["includeTranscript"] = True

    print(f"=== Stage 5C-1: Reels Collector ===")
    print(f"Actor:             {ACTOR_ID}")
    print(f"Account:           @{account}")
    print(f"Limit:             {limit} reels")
    print(f"includeTranscript: {include_transcript}")
    print(f"Input:             {json.dumps(run_input)}")
    print()
    print("Starting Apify run...")

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        print(f"[ERROR] Apify actor call failed: {e}", file=sys.stderr)
        sys.exit(1)

    run_id     = run.get("id", "")
    dataset_id = run.get("defaultDatasetId", "")
    status     = run.get("status", "")
    print(f"Run ID:     {run_id}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Status:     {status}")

    if status not in ("SUCCEEDED",):
        print(f"[ERROR] Run did not succeed (status={status})", file=sys.stderr)
        sys.exit(1)

    print("Fetching dataset items...")
    try:
        raw_items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        print(f"[ERROR] Failed to fetch dataset items: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Raw items fetched: {len(raw_items)}")

    # Save raw
    raw_dir  = BASE / "data" / account / "raw"
    norm_dir = BASE / "data" / account / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)

    raw_path = raw_dir / "stage5c1_reels_raw.json"
    raw_path.write_text(json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Raw saved: {raw_path.relative_to(BASE)}")

    # Normalize
    selected, strategy = normalize_reels(raw_items, max_total=MAX_SELECTED)

    norm_output = {
        "account":         account,
        "stage":           STAGE,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "apify_run_id":    run_id,
        "actor":           ACTOR_ID,
        "reels_total_raw": len(raw_items),
        "reels_selected":  len(selected),
        "selection_strategy": strategy,
        "reels":           selected,
    }

    norm_path = norm_dir / "stage5c1_reels_index.json"
    norm_path.write_text(json.dumps(norm_output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Normalized saved: {norm_path.relative_to(BASE)}")

    # Summary
    print()
    print("=== Summary ===")
    print(f"  Raw reels collected: {len(raw_items)}")
    print(f"  Strategy:            {strategy}")
    print(f"  Selected for index:  {len(selected)}")
    print()

    pinned_count = sum(1 for r in selected if r.get("is_pinned"))
    if pinned_count:
        print(f"  Pinned: {pinned_count}")
    for r in selected:
        views  = r.get("view_count") or 0
        pinned = " [pinned]" if r.get("is_pinned") else ""
        url    = r.get("url") or r.get("reel_id") or "?"
        print(f"  #{r['position']:2}  {views:>8} views{pinned}  {url}")

    cost = round(len(raw_items) * 0.0026, 4)
    print()
    print(f"  Estimated cost: ${cost:.4f}  ({len(raw_items)} reels × $0.0026)")


if __name__ == "__main__":
    main()
