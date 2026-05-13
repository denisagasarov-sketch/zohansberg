#!/usr/bin/env python3
"""
Stage 5B-2: Local runner.

Запускает:
  1. stage5b2_collect_highlight_stories.py  — N actor calls + normalized JSON
  2. stage5b2_create_report.py              — Markdown report (runtime, не коммитить)

Использование:
  python scripts/stage5b2_run_local.py --dry-run         # без Apify, все валидные ID
  python scripts/stage5b2_run_local.py --dry-run --limit 5
  python scripts/stage5b2_run_local.py                   # реальный запуск, все
  python scripts/stage5b2_run_local.py --limit 3         # первые 3 валидных highlight
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN = "--dry-run" in sys.argv

# Parse --limit N
LIMIT = None
for i, arg in enumerate(sys.argv):
    if arg == "--limit" and i + 1 < len(sys.argv):
        try:
            LIMIT = int(sys.argv[i + 1])
        except ValueError:
            print(f"[ERROR] --limit must be an integer, got: {sys.argv[i + 1]}", file=sys.stderr)
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

    if DRY_RUN:
        collector.run_dry_run(highlights, LIMIT)
        # sys.exit called inside
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

    to_process = [h for h in highlights if h["id_valid"]]
    if LIMIT:
        to_process_count = min(LIMIT, len(to_process))
    else:
        to_process_count = len(to_process)

    print("=== Stage 5B-2: Highlight Stories Collector ===")
    print(f"Actor:    {collector.ACTOR_ID}")
    print(f"Account:  {collector.ACCOUNT}")
    print(f"Source:   {collector.HIGHLIGHTS_INDEX_PATH.relative_to(BASE)}")
    print(f"highlights total:    {len(highlights)}")
    print(f"highlights valid:    {valid_count}")
    print(f"highlights invalid:  {invalid_count}")
    print(f"limit:               {LIMIT if LIMIT else 'none (all valid)'}")
    print(f"planned_apify_calls: {to_process_count}")

    summary = collector.collect(client, highlights, LIMIT)

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
