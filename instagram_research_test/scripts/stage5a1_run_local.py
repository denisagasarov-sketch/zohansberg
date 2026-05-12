#!/usr/bin/env python3
"""
Stage 5A-1: Local runner.

Запускает:
  1. stage5a1_collect_profile_and_pinned.py  — 2 actor calls + normalized JSON
  2. stage5a1_create_report.py               — Markdown report

Использование:
  python scripts/stage5a1_run_local.py --dry-run   # без Apify
  python scripts/stage5a1_run_local.py             # реальный запуск
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN = "--dry-run" in sys.argv


def main():
    if DRY_RUN:
        import stage5a1_collect_profile_and_pinned as collector
        collector.dry_run()
        print("\n(Report is not generated in dry-run mode — no data collected.)")
        return

    # Real run
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE / ".env", override=True)

    token = os.environ.get("APIFY_TOKEN", "")
    if not token or not token.startswith("apify_api_"):
        print("[ERROR] APIFY_TOKEN invalid or missing in .env", file=sys.stderr)
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client = ApifyClient(token)

    print("=== Stage 5A-1: Profile + Pinned Index Collector ===")

    import stage5a1_collect_profile_and_pinned as collector
    collector.collect(client)

    print("\n=== Creating report ===")
    import stage5a1_create_report as reporter
    reporter.main()

    print("\n=== Stage 5A-1 complete ===")
    print("Next:")
    print("  cat report/stage_5a1_profile_pinned_report.md")
    print("  cat data/normalized/profile_summary.json")
    print("  cat data/normalized/bio_analysis.json")
    print("  cat data/normalized/pinned_posts_index.json")
    print("  cat data/normalized/stage5a_summary.json")


if __name__ == "__main__":
    main()
