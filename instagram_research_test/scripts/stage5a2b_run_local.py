"""Stage 5A-2B local runner: Pinned Posts Details Collector.

Usage:
    python3 scripts/stage5a2b_run_local.py --dry-run
    python3 scripts/stage5a2b_run_local.py --from-existing-raw
    python3 scripts/stage5a2b_run_local.py --collect --max-posts 3
    python3 scripts/stage5a2b_run_local.py --create-report
"""

import argparse
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from stage5a2b_collect_pinned_post_details import (
    ACTOR_ID,
    ACCOUNT,
    PROFILE_URL,
    PINNED_INDEX_PATH,
    AUDIT_PATH,
    RAW_OUTPUT_PATH,
    NORM_OUTPUT_PATH,
    SCHEMA_SUMMARY_PATH,
    STAGE5A1_RAW_POSTS,
    CONFIRMED_MAP,
    CANDIDATE_DISPLAY_URL_FIELDS,
    CANDIDATE_THUMBNAIL_FIELDS,
    CANDIDATE_VIDEO_URL_FIELDS,
    CANDIDATE_CAROUSEL_FIELDS,
    load_pinned_index,
    extract_pinned_refs,
    build_direct_payload,
    build_fallback_payload,
    run_from_existing_raw,
    run_collect,
)
from stage5a2b_create_report import create_report


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run():
    print("[DRY-RUN] No external calls. No files will be written.\n")

    if not PINNED_INDEX_PATH.exists():
        print(f"[ERROR] {PINNED_INDEX_PATH.relative_to(BASE)} not found.")
        print("  Run Stage 5A-1 first to produce pinned_posts_index.json.")
        sys.exit(1)

    index, errors = load_pinned_index()
    hard_errors = [e for e in errors if not e.startswith("WARNING")]
    warnings    = [e for e in errors if e.startswith("WARNING")]

    if warnings:
        for w in warnings:
            print(f"[WARNING] {w}")
        print()

    if hard_errors:
        print("[ERROR] Validation failed:")
        for e in hard_errors:
            print(f"  - {e}")
        sys.exit(1)

    pinned_refs = extract_pinned_refs(index)

    print(f"Source:         {PINNED_INDEX_PATH.relative_to(BASE)}")
    print(f"Actor:          {ACTOR_ID}")
    print(f"Account:        {ACCOUNT}")
    print(f"Pinned posts:   {len(pinned_refs)}")
    print()

    print("── Pinned posts ────────────────────────────────────────────────")
    for ref in pinned_refs:
        print(f"  Post {ref['position']}:")
        print(f"    permalink:  {ref['permalink'] or '—'}")
        print(f"    shortcode:  {ref['shortcode'] or '—'}")
        print(f"    post_id:    {ref['post_id'] or '—'}")
        print(f"    media_type: {ref['media_type'] or '—'}")
    print()

    # Preferred strategy: direct post URLs
    post_urls = [r["permalink"] for r in pinned_refs if r.get("permalink")]
    if len(post_urls) == len(pinned_refs):
        payload_direct = build_direct_payload(post_urls)
        print("── Preferred payload (direct post URL mode) ────────────────────")
        print(f"  directUrls:   {post_urls}")
        print(f"  resultsType:  {payload_direct['resultsType']}")
        print(f"  resultsLimit: {payload_direct['resultsLimit']}")
        print(f"  proxy:        useApifyProxy=True")
        print()
    else:
        print(f"  NOTE: only {len(post_urls)}/{len(pinned_refs)} permalinks available")
        print("  Will use fallback payload (account scrape, max 30)")
        print()

    payload_fallback = build_fallback_payload()
    print("── Fallback payload (account scrape, filter by shortcodes) ─────")
    print(f"  directUrls:   [{PROFILE_URL}]")
    print(f"  resultsType:  {payload_fallback['resultsType']}")
    print(f"  resultsLimit: {payload_fallback['resultsLimit']} (hard limit; will filter by pinned shortcodes)")
    print()

    # Expected schema
    print("── Fields confirmed from Stage 5A-1 source code ────────────────")
    for actor_field, norm_field in CONFIRMED_MAP.items():
        print(f"  actor.{actor_field:15s} → {norm_field}")
    print()

    print("── Candidate media fields (NOT confirmed in local raw) ──────────")
    print(f"  display_url:  {CANDIDATE_DISPLAY_URL_FIELDS}")
    print(f"  thumbnail:    {CANDIDATE_THUMBNAIL_FIELDS}")
    print(f"  video_url:    {CANDIDATE_VIDEO_URL_FIELDS}")
    print(f"  carousel:     {CANDIDATE_CAROUSEL_FIELDS}")
    print()

    print("── Schema status ───────────────────────────────────────────────")
    stage5a1_raw_exists = STAGE5A1_RAW_POSTS.exists()
    print(f"  Stage 5A-1 raw posts file exists: {stage5a1_raw_exists}")
    if stage5a1_raw_exists:
        print(f"    Path: {STAGE5A1_RAW_POSTS.relative_to(BASE)}")
        print("    → --from-existing-raw is available")
    else:
        print(f"    Path: {STAGE5A1_RAW_POSTS.relative_to(BASE)} (missing)")
        print("    → use --collect --max-posts 3 to get fresh data")
    print()

    # Apify token status
    token = os.environ.get("APIFY_TOKEN", "")
    token_ok = bool(token and token.startswith("apify_api_"))
    print("── Environment ─────────────────────────────────────────────────")
    print(f"  APIFY_TOKEN: {'SET (format OK)' if token_ok else 'NOT SET or invalid format — required for --collect'}")
    print()

    print("── Planned runtime outputs ─────────────────────────────────────")
    print(f"  {RAW_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {NORM_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {SCHEMA_SUMMARY_PATH.relative_to(BASE)}")
    print(f"  report/stage_5a2b_pinned_post_details_report.md")
    print()

    print("[DRY-RUN] Complete. Choose a run mode:")
    if stage5a1_raw_exists:
        print("  python3 scripts/stage5a2b_run_local.py --from-existing-raw")
    print("  python3 scripts/stage5a2b_run_local.py --collect --max-posts 3")


# ---------------------------------------------------------------------------
# From-existing-raw
# ---------------------------------------------------------------------------

def run_from_existing():
    print("Mode: --from-existing-raw")
    print("Normalizing from existing Stage 5A-1 raw posts file...\n")

    if not STAGE5A1_RAW_POSTS.exists():
        print(f"[ERROR] {STAGE5A1_RAW_POSTS.relative_to(BASE)} not found.")
        print("  Run Stage 5A-1 first (python3 scripts/stage5a1_run_local.py),")
        print("  or use --collect --max-posts 3 for a fresh Apify run.")
        sys.exit(1)

    try:
        output = run_from_existing_raw()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    _print_summary(output)


# ---------------------------------------------------------------------------
# Collect
# ---------------------------------------------------------------------------

def run_collect_mode(max_posts: int):
    print(f"Mode: --collect --max-posts {max_posts}")

    if max_posts < 1:
        print(f"[ERROR] --max-posts must be at least 1, got {max_posts}.")
        sys.exit(1)

    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        print("[ERROR] APIFY_TOKEN is not set in environment.")
        sys.exit(1)
    if not token.startswith("apify_api_"):
        print("[ERROR] APIFY_TOKEN format looks invalid (expected apify_api_ prefix).")
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        print("[ERROR] apify-client not installed. Run: pip install apify-client")
        sys.exit(1)

    client = ApifyClient(token)
    print(f"Actor: {ACTOR_ID}")
    print()

    try:
        output = run_collect(client, max_posts)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    _print_summary(output)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def run_create_report():
    print("Mode: --create-report")
    if not NORM_OUTPUT_PATH.exists():
        print(f"[ERROR] {NORM_OUTPUT_PATH.relative_to(BASE)} not found.")
        print("  Run --collect or --from-existing-raw first.")
        sys.exit(1)

    try:
        result = create_report()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    print(f"Report written: {result.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(output: dict):
    s = output.get("summary", {})
    print()
    print("=== Collection Summary ===")
    print(f"  Total posts:            {output.get('total_pinned_posts', 0)}")
    print(f"  Source:                 {output.get('source', '—')}")
    print(f"  Strategy:               {output.get('strategy', '—')}")
    print(f"  Posts with full caption:{s.get('posts_with_full_caption', 0)}")
    print(f"  Posts with cover/thumb: {s.get('posts_with_cover_or_thumbnail', 0)}")
    print(f"  Posts with carousel:    {s.get('posts_with_carousel_items', 0)}")
    print(f"  Caption semantic OK:    {s.get('caption_semantic_possible', False)}")
    print(f"  Visual/OCR input OK:    {s.get('visual_ocr_input_possible', False)}")
    print()

    warns = output.get("warnings") or []
    if warns:
        print(f"  Warnings ({len(warns)}):")
        for w in warns:
            print(f"    - {w}")
        print()

    print(f"  Recommended next step:")
    print(f"    {s.get('next_stage_recommendation', '—')}")
    print()
    print(f"Normalized: {NORM_OUTPUT_PATH.relative_to(BASE)}")
    print(f"Schema:     {SCHEMA_SUMMARY_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2B: Pinned Posts Details Collector"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Print plan; no external calls (default)",
    )
    mode_group.add_argument(
        "--from-existing-raw", action="store_true",
        help="Normalize from existing Stage 5A-1 raw posts file",
    )
    mode_group.add_argument(
        "--collect", action="store_true",
        help="Run Apify to collect post details (requires APIFY_TOKEN)",
    )
    mode_group.add_argument(
        "--create-report", action="store_true",
        help="Generate report from existing normalized output",
    )
    parser.add_argument(
        "--max-posts", type=int, default=3,
        help="Safety limit for --collect (must be 3)",
    )
    parser.add_argument(
        "--account", default="vlada_kliuiko",
        help="Instagram account to process",
    )
    args = parser.parse_args()

    if args.collect:
        run_collect_mode(args.max_posts)
    elif args.from_existing_raw:
        run_from_existing()
    elif args.create_report:
        run_create_report()
    else:
        run_dry_run()


if __name__ == "__main__":
    main()
