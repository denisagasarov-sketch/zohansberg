#!/usr/bin/env python3
"""
Stage 5B-auto: Local runner.

Calls automation-lab/instagram-stories-scraper (single Apify call).
Returns active profile stories + archived highlight stories grouped by highlightId.
Canonical highlight metadata joined from singhera07 highlights_index.

COST WARNING: automation-lab charges per story item. Always use --max-highlights.

Usage:
  # dry-run — no Apify, shows planned highlights and cost estimate
  python scripts/stage5b_auto_run_local.py --dry-run --max-highlights 3

  # real run — first 3 highlights
  python scripts/stage5b_auto_run_local.py --max-highlights 3

  # real run — all highlights in index
  python scripts/stage5b_auto_run_local.py --max-highlights 32

  # normalize-only — rebuild outputs from existing raw, no Apify call
  python scripts/stage5b_auto_run_local.py --normalize-only
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN       = "--dry-run" in sys.argv
NORMALIZE_ONLY = "--normalize-only" in sys.argv

# --max-highlights N is REQUIRED unless --normalize-only
MAX_HIGHLIGHTS: int | None = None
for i, arg in enumerate(sys.argv):
    if arg == "--max-highlights" and i + 1 < len(sys.argv):
        try:
            MAX_HIGHLIGHTS = int(sys.argv[i + 1])
            if MAX_HIGHLIGHTS < 1:
                print("[ERROR] --max-highlights must be >= 1", file=sys.stderr)
                sys.exit(1)
        except ValueError:
            print(
                f"[ERROR] --max-highlights must be an integer, got: {sys.argv[i + 1]}",
                file=sys.stderr,
            )
            sys.exit(1)

if not NORMALIZE_ONLY and MAX_HIGHLIGHTS is None:
    print("[ERROR] --max-highlights N is required. Unbounded runs are not allowed.", file=sys.stderr)
    print("  Example: python scripts/stage5b_auto_run_local.py --max-highlights 3", file=sys.stderr)
    print("  Use --dry-run to preview without calling Apify.", file=sys.stderr)
    print("  Use --normalize-only to rebuild outputs from existing raw (no Apify).", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    import stage5b_auto_collect_stories as collector

    if DRY_RUN:
        collector.run_dry_run(MAX_HIGHLIGHTS)
        return  # run_dry_run calls sys.exit(0)

    if NORMALIZE_ONLY:
        print("=== Stage 5B-auto: NORMALIZE ONLY (no Apify call) ===")
        print(f"Source: {collector.RAW_OUTPUT_PATH.relative_to(BASE)}")
        print()
        summary = collector.normalize_from_raw()

        print("\n=== Creating report ===")
        import stage5b_auto_create_report as reporter
        reporter.main()

        print("\n=== Normalize-only complete ===")
        _print_outputs()
        return

    # Real run — load env and validate credentials
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE / ".env", override=True)

    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = collector.validate_token(token)
    if token_errors:
        print("[ERROR] APIFY_TOKEN validation failed:", file=sys.stderr)
        for e in token_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE", "")
    cookie_errors = collector.validate_cookie(cookie)
    if cookie_errors:
        print("[ERROR] INSTAGRAM_SESSION_COOKIE validation failed:", file=sys.stderr)
        for e in cookie_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client = ApifyClient(token)

    print("=== Stage 5B-auto: Highlight Stories Collector ===")
    print(f"Actor:           {collector.ACTOR_ID}")
    print(f"Account:         {collector.ACCOUNT}")
    print(f"max-highlights:  {MAX_HIGHLIGHTS}")
    print(f"Apify calls:     1  (single call, not per-highlight)")
    print()
    print("[COST WARNING] automation-lab is pay-per-story.")
    print(f"  Rough estimate: up to ~{MAX_HIGHLIGHTS * 60} story items billed.")
    print()

    summary = collector.collect(client, MAX_HIGHLIGHTS)

    print("\n=== Creating report ===")
    import stage5b_auto_create_report as reporter
    reporter.main()

    print("\n=== Stage 5B-auto complete ===")
    _print_outputs()


def _print_outputs() -> None:
    print("Runtime outputs (not committed):")
    print("  data/raw/stage5b_auto_stories_raw.json")
    print("  data/normalized/stage5b_auto_stories_summary.json")
    print("  data/normalized/stage5b_auto_stories_index.json")
    print("  report/stage_5b_auto_stories_report.md")
    print()
    print("Next:")
    print("  cat report/stage_5b_auto_stories_report.md")
    print("  cat data/normalized/stage5b_auto_stories_index.json")


if __name__ == "__main__":
    main()
