#!/usr/bin/env python3
"""
Stage 5B-1: Local runner.

Запускает:
  1. stage5b1_collect_highlights_index.py  — 1 actor call + normalized JSON
  2. stage5b1_create_report.py             — Markdown report (runtime, не коммитить)

Использование:
  python scripts/stage5b1_run_local.py --dry-run   # без Apify
  python scripts/stage5b1_run_local.py             # реальный запуск
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN = "--dry-run" in sys.argv

ACCOUNT = "vlada_kliuiko"
for i, arg in enumerate(sys.argv):
    if arg == "--account" and i + 1 < len(sys.argv):
        ACCOUNT = sys.argv[i + 1]
        break


def main():
    import stage5b1_collect_highlights_index as collector

    payload = collector.load_payload_from_registry()

    if DRY_RUN:
        token = os.environ.get("APIFY_TOKEN", "")
        token_errors = collector.validate_token(token)
        collector.run_dry_run(token_errors, payload)
        # sys.exit called inside run_dry_run
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

    payload["username"] = ACCOUNT

    print("=== Stage 5B-1: Highlights Index Collector ===")
    summary = collector.collect(client, payload)

    print("\n=== Creating report ===")
    import stage5b1_create_report as reporter
    reporter.main()

    print("\n=== Stage 5B-1 complete ===")
    print("Runtime outputs (not committed):")
    print("  data/raw/stage5b1_highlights_index_raw.json")
    print("  data/normalized/highlights_index.json")
    print("  data/normalized/stage5b1_highlights_index_summary.json")
    print("  report/stage_5b1_highlights_index_report.md")
    print()
    print("Next:")
    print("  cat report/stage_5b1_highlights_index_report.md")
    print("  cat data/normalized/highlights_index.json")
    print("  cat data/normalized/stage5b1_highlights_index_summary.json")


if __name__ == "__main__":
    main()
