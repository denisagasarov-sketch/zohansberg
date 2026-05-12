"""Stage 5A-2A local runner: pinned posts source audit.

Usage:
    python3 scripts/stage5a2a_run_local.py --dry-run
    python3 scripts/stage5a2a_run_local.py
"""

import argparse
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from stage5a2a_pinned_posts_source_audit import (
    PINNED_INDEX_PATH,
    AUDIT_JSON_PATH,
    AUDIT_REPORT_PATH,
    GOOGLE_SHEETS_FIELDS,
    load_pinned_index,
    run_audit,
)


def run_dry_run():
    print("[DRY-RUN] No files will be written.\n")

    # Load pinned index
    if not PINNED_INDEX_PATH.exists():
        print(f"[ERROR] {PINNED_INDEX_PATH} not found.")
        print("  Stage 5A-1 must be run first to produce pinned_posts_index.json.")
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

    # Print top-level fields
    top_keys = [k for k in index.keys() if k != "pinned_posts"]
    print(f"Source: {PINNED_INDEX_PATH.relative_to(BASE)}")
    print(f"Top-level fields: {', '.join(top_keys)}")
    print(f"detection_method: {index.get('detection_method', '—')}")
    print(f"posts_checked:    {index.get('posts_checked', '—')}")
    print(f"pinned_count:     {index.get('pinned_count', 0)}")
    print(f"manual_needed:    {index.get('manual_needed', False)}")
    print()

    # Per-post field inventory
    pinned_posts = index.get("pinned_posts") or []
    print(f"Posts detected: {len(pinned_posts)}")
    print()
    for item in pinned_posts:
        pos = item.get("position", "?")
        print(f"  Post {pos}:")
        for key in ("url", "content_id", "shortcode", "caption_preview", "type", "timestamp", "is_pinned"):
            field = item.get(key)
            if isinstance(field, dict):
                status = field.get("data_status", "?")
                val    = field.get("value")
                if isinstance(val, str):
                    preview = val[:60] + ("…" if len(val) > 60 else "")
                else:
                    preview = str(val)
                print(f"    {key}: status={status}, value={preview!r}")
            elif key == "position":
                print(f"    position: {item.get('position')}")
            else:
                print(f"    {key}: (not present)")
        print()

    # Google Sheets fields that will be assessed
    print(f"Google Sheets fields to be assessed ({len(GOOGLE_SHEETS_FIELDS)}):")
    for f in GOOGLE_SHEETS_FIELDS:
        print(f"  - {f}")
    print()

    # Planned outputs
    print("Planned outputs (NOT written in dry-run):")
    print(f"  {AUDIT_JSON_PATH.relative_to(BASE)}")
    print(f"  {AUDIT_REPORT_PATH.relative_to(BASE)}")
    print()
    print("[DRY-RUN] Complete. Run without --dry-run to write audit outputs.")


def run_real():
    print("Running Stage 5A-2A pinned posts source audit...")

    if not PINNED_INDEX_PATH.exists():
        print(f"[ERROR] {PINNED_INDEX_PATH} not found.")
        print("  Stage 5A-1 must be run first to produce pinned_posts_index.json.")
        sys.exit(1)

    try:
        audit = run_audit()
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    n = audit.get("total_pinned_posts", 0)
    q = audit.get("source_quality_summary", "—")
    print(f"Posts audited:  {n}")
    print(f"Source quality: {q}")
    print()

    gs = audit.get("google_sheets_field_assessment", {})
    can_now   = [f for f, v in gs.items() if v.get("can_fill_now")]
    need_vis  = [f for f, v in gs.items() if v.get("needs_visual_or_ocr")]
    need_sem  = [f for f, v in gs.items() if v.get("needs_semantic_analysis") and not v.get("can_fill_now")]

    print(f"Fields fillable now ({len(can_now)}):         {', '.join(can_now)}")
    print(f"Fields needing visual/OCR ({len(need_vis)}):  {', '.join(need_vis)}")
    print(f"Fields needing semantic ({len(need_sem)}):    {', '.join(need_sem)}")
    print()

    an = audit.get("apify_needs", {})
    print(f"New Apify call needed: {an.get('new_apify_call_needed', True)}")
    print(f"Caption-only analyzer possible now: {audit.get('caption_only_analyzer_possible', False)}")
    print()

    print(f"Audit JSON:   {AUDIT_JSON_PATH.relative_to(BASE)}")
    print(f"Audit report: {AUDIT_REPORT_PATH.relative_to(BASE)}")
    print()
    print("Recommended next step:")
    print(f"  {audit.get('recommended_next_stage', '—')}")


def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2A: pinned posts source audit"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read sources, print field inventory, write no files",
    )
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run()
    else:
        run_real()


if __name__ == "__main__":
    main()
