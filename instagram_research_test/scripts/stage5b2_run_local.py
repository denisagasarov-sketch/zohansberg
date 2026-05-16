#!/usr/bin/env python3
"""
Stage 5B-2: Local runner.

Запускает:
  1. stage5b2_collect_highlight_stories.py  — N actor calls + normalized JSON
  2. stage5b2_create_report.py              — Markdown report (runtime, не коммитить)

Использование:
  python scripts/stage5b2_run_local.py --dry-run              # без Apify, первые 5 (дефолт)
  python scripts/stage5b2_run_local.py --dry-run --limit 3
  python scripts/stage5b2_run_local.py                        # реальный запуск, первые 5
  python scripts/stage5b2_run_local.py --limit 10             # первые 10 валидных highlight
  python scripts/stage5b2_run_local.py --from-position 5 --limit 5  # следующие 5 (позиции 6–10)
"""

import json
import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN       = "--dry-run"       in sys.argv
REFRESH_STALE = "--refresh-stale" in sys.argv

# Parse --limit N (default: 5)
LIMIT = 5
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        try:
            LIMIT = int(sys.argv[i + 1])
        except ValueError:
            print(f"[ERROR] --limit must be an integer, got: {sys.argv[i + 1]}", file=sys.stderr)
            sys.exit(1)

# Parse --from-position N (default: 0) — skip first N valid highlights
FROM_POSITION = 0
for i, arg in enumerate(sys.argv):
    if arg == "--from-position" and i + 1 < len(sys.argv):
        try:
            FROM_POSITION = int(sys.argv[i + 1])
        except ValueError:
            print(f"[ERROR] --from-position must be an integer, got: {sys.argv[i + 1]}", file=sys.stderr)
            sys.exit(1)

ACCOUNT = "vlada_kliuiko"
for i, arg in enumerate(sys.argv):
    if arg == "--account" and i + 1 < len(sys.argv):
        ACCOUNT = sys.argv[i + 1]
        break


def main():
    import stage5b2_collect_highlight_stories as collector

    # Load highlights index — required for both dry-run and real run
    highlights = collector.load_highlights_index()
    highlights = collector.prepare_highlights(highlights)

    valid_count   = sum(1 for h in highlights if h["id_valid"])
    invalid_count = len(highlights) - valid_count

    if valid_count == 0:
        print("[ERROR] No valid highlight IDs found in highlights_index.json.", file=sys.stderr)
        print("  Run Stage 5B-1 first and ensure the run returned highlights with IDs.",
              file=sys.stderr)
        sys.exit(1)

    # Apply FROM_POSITION: skip first N valid highlights
    if FROM_POSITION > 0:
        valid_skipped = 0
        filtered = []
        for h in highlights:
            if h["id_valid"] and valid_skipped < FROM_POSITION:
                valid_skipped += 1
            else:
                filtered.append(h)
        highlights_to_process = filtered
    else:
        highlights_to_process = highlights

    remaining_valid = sum(1 for h in highlights_to_process if h["id_valid"])

    # --refresh-stale: override highlights_to_process with only the stale IDs
    if REFRESH_STALE:
        stale_path = BASE / "data" / ACCOUNT / "normalized" / "stale_highlights.json"
        if not stale_path.exists():
            print("[INFO] stale_highlights.json not found — nothing to refresh")
            sys.exit(0)
        try:
            stale_data = json.loads(stale_path.read_text(encoding="utf-8"))
            stale_ids  = set(str(x) for x in (stale_data.get("stale_highlight_ids") or []))
        except Exception as e:
            print(f"[ERROR] Failed to read stale_highlights.json: {e}", file=sys.stderr)
            sys.exit(1)
        if not stale_ids:
            print("[INFO] stale_highlights.json is empty — nothing to refresh")
            sys.exit(0)

        def _hid(h: dict) -> str:
            return str(h.get("raw_id") or h.get("highlight_id") or h.get("id") or "")

        highlights_to_process = [h for h in highlights if _hid(h) in stale_ids]
        remaining_valid = sum(1 for h in highlights_to_process if h.get("id_valid", True))
        print(f"[REFRESH-STALE] {len(highlights_to_process)} stale highlight(s) to re-collect:")
        for h in highlights_to_process:
            print(f"  - {h.get('title', _hid(h))} (id={_hid(h)})")

    if DRY_RUN:
        collector.run_dry_run(highlights_to_process, LIMIT)
        return

    # Real run
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE / ".env", override=True)

    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = collector.validate_token(token)
    if token_errors:
        print("[ERROR] APIFY_TOKEN validation failed:", file=sys.stderr)
        for e in token_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client = ApifyClient(token)

    to_process_count = min(LIMIT, remaining_valid) if LIMIT else remaining_valid

    print("=== Stage 5B-2: Highlight Stories Collector ===")
    print(f"Actor:    {collector.ACTOR_ID}")
    print(f"Account:  {collector.ACCOUNT}")
    print(f"Source:   {collector.HIGHLIGHTS_INDEX_PATH.relative_to(BASE)}")
    print(f"highlights total:    {len(highlights)}")
    print(f"highlights valid:    {valid_count}")
    print(f"highlights invalid:  {invalid_count}")
    print(f"from-position:       {FROM_POSITION}")
    print(f"limit:               {LIMIT}")
    print(f"will process:        {to_process_count}")
    print(f"planned_apify_calls: 1  (single batch, usernames=[{ACCOUNT!r}], maxHighlights={to_process_count})")

    limit_for_collect = None if REFRESH_STALE else LIMIT
    summary = collector.collect(client, highlights_to_process, limit_for_collect)

    # After refresh-stale: remove stale_highlights.json so stage5b2v re-evaluates
    if REFRESH_STALE:
        stale_path = BASE / "data" / ACCOUNT / "normalized" / "stale_highlights.json"
        if stale_path.exists():
            stale_path.unlink()
            print(f"[REFRESH-STALE] Cleared: {stale_path.relative_to(BASE)}")

    print("\n=== Creating report ===")
    import stage5b2_create_report as reporter
    reporter.main()

    print("\n=== Stage 5B-2 complete ===")
    print("Runtime outputs (not committed):")
    print("  data/raw/stage5b2_stories_{id}_raw.json  (per highlight)")
    print("  data/normalized/stage5b2_highlights_stories_summary.json")
    print("  data/normalized/stage5b2_stories_index.json")
    print("  report/stage_5b2_highlights_stories_report.md")
    print()
    print("Next:")
    print("  cat report/stage_5b2_highlights_stories_report.md")
    print("  cat data/normalized/stage5b2_stories_index.json")


if __name__ == "__main__":
    main()
