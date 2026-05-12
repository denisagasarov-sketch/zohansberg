#!/usr/bin/env python3
"""
Stage 5C: Local runner for OpenAI Vision story analysis.

Image input mode: base64 by default (fetched in-memory, never written to disk).
Instagram CDN URLs are NOT passed directly to OpenAI.
Use --allow-direct-url-mode ONLY for testing; it will fail on Instagram CDN.

Usage:
  # dry-run
  python scripts/stage5c_run_local.py \
    --dry-run --max-stories-per-highlight 5 --budget-max-usd 1.00

  # test media fetch without OpenAI
  python scripts/stage5c_run_local.py \
    --test-media-fetch --max-stories-per-highlight 1

  # real run
  python scripts/stage5c_run_local.py \
    --max-stories-per-highlight 5 --budget-max-usd 1.00

  # specific highlights
  python scripts/stage5c_run_local.py \
    --max-stories-per-highlight 10 --budget-max-usd 2.00 \
    --highlight-ids 17874797856565339,18110898391654002

  # high detail (better OCR, ~3-4x cost)
  python scripts/stage5c_run_local.py \
    --max-stories-per-highlight 5 --budget-max-usd 2.00 --detail high

  # force re-analyze (ignore cache)
  python scripts/stage5c_run_local.py \
    --max-stories-per-highlight 5 --budget-max-usd 1.00 --force
"""

import sys
import os
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _flag(name: str) -> bool:
    return name in sys.argv


def _arg(name: str, default=None):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


DRY_RUN          = _flag("--dry-run")
FORCE            = _flag("--force")
TEST_MEDIA_FETCH = _flag("--test-media-fetch")
ALLOW_DIRECT_URL = _flag("--allow-direct-url-mode")
IMAGE_INPUT_MODE = "direct_url" if ALLOW_DIRECT_URL else "base64"

# --max-stories-per-highlight N  (required)
_msh_raw = _arg("--max-stories-per-highlight")
if _msh_raw is None:
    print("[ERROR] --max-stories-per-highlight N is required.", file=sys.stderr)
    print("  Example: --max-stories-per-highlight 5 --budget-max-usd 1.00", file=sys.stderr)
    sys.exit(1)
try:
    MAX_STORIES_PER_HL = int(_msh_raw)
    if MAX_STORIES_PER_HL < 1:
        raise ValueError
except ValueError:
    print(f"[ERROR] --max-stories-per-highlight must be a positive integer, got: {_msh_raw}",
          file=sys.stderr)
    sys.exit(1)

# --budget-max-usd X  (required unless --test-media-fetch or --dry-run)
_budget_raw = _arg("--budget-max-usd")
BUDGET_MAX_USD: float | None = None
if _budget_raw is not None:
    try:
        BUDGET_MAX_USD = float(_budget_raw)
        if BUDGET_MAX_USD <= 0:
            raise ValueError
    except ValueError:
        print(f"[ERROR] --budget-max-usd must be a positive number, got: {_budget_raw}",
              file=sys.stderr)
        sys.exit(1)

if BUDGET_MAX_USD is None and not TEST_MEDIA_FETCH and not DRY_RUN:
    print("[ERROR] --budget-max-usd X is required for real runs.", file=sys.stderr)
    print("  Use --dry-run to estimate cost first.", file=sys.stderr)
    sys.exit(1)

# optional
SELECTION_MODE = _arg("--selection-mode", "spread")
if SELECTION_MODE not in ("first", "last", "spread"):
    print(f"[ERROR] --selection-mode must be first|last|spread, got: {SELECTION_MODE}",
          file=sys.stderr)
    sys.exit(1)

MODEL  = _arg("--model",  "gpt-4o-mini")
DETAIL = _arg("--detail", "low")
if DETAIL not in ("low", "high"):
    print(f"[ERROR] --detail must be low|high, got: {DETAIL}", file=sys.stderr)
    sys.exit(1)

_hl_ids_raw = _arg("--highlight-ids")
HIGHLIGHT_IDS: list[str] | None = (
    [h.strip() for h in _hl_ids_raw.split(",") if h.strip()]
    if _hl_ids_raw else None
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    import stage5c_analyze_stories as analyzer

    # ------------------------------------------------------------------
    # Test media fetch (no OpenAI, no API key required)
    # ------------------------------------------------------------------
    if TEST_MEDIA_FETCH:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
        cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE") or None
        # cookie never printed
        print("=== Stage 5C: TEST MEDIA FETCH (no OpenAI) ===")
        print(f"image_input_mode: {IMAGE_INPUT_MODE}")
        print(f"max_stories_per_hl: {MAX_STORIES_PER_HL}")
        print(f"selection_mode: {SELECTION_MODE}")
        print()
        analyzer.test_media_fetch(MAX_STORIES_PER_HL, SELECTION_MODE, cookie)
        return  # test_media_fetch calls sys.exit(0)

    # ------------------------------------------------------------------
    # Dry-run (no OpenAI, no API key required)
    # ------------------------------------------------------------------
    if DRY_RUN:
        analyzer.run_dry_run(
            max_stories_per_hl   = MAX_STORIES_PER_HL,
            selection_mode       = SELECTION_MODE,
            highlight_ids_filter = HIGHLIGHT_IDS,
            model                = MODEL,
            detail               = DETAIL,
            budget_max_usd       = BUDGET_MAX_USD or 0.0,
            image_input_mode     = IMAGE_INPUT_MODE,
        )
        return  # run_dry_run calls sys.exit(0)

    # ------------------------------------------------------------------
    # Real run — validate credentials
    # ------------------------------------------------------------------
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE / ".env", override=True)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY is empty — set it in .env", file=sys.stderr)
        sys.exit(1)
    if not api_key.startswith("sk-"):
        print("[ERROR] OPENAI_API_KEY does not start with 'sk-' — check .env", file=sys.stderr)
        sys.exit(1)

    cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE") or None
    # cookie never printed; used for 401/403 retry on media fetch

    if ALLOW_DIRECT_URL:
        print("[WARN] --allow-direct-url-mode is active.")
        print("  Instagram CDN URLs will be passed directly to OpenAI.")
        print("  This is known to fail with 'invalid_image_url' errors.")
        print("  Remove --allow-direct-url-mode to use base64 (default).")
        print()

    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("openai not installed — run: pip install openai")

    client = OpenAI(api_key=api_key)  # api_key never printed

    print("=== Stage 5C: Story Content Analyzer ===")
    print(f"Model:            {MODEL}")
    print(f"Detail:           {DETAIL}")
    print(f"Image input mode: {IMAGE_INPUT_MODE}")
    print(f"Selection mode:   {SELECTION_MODE}")
    print(f"Max stories/hl:   {MAX_STORIES_PER_HL}")
    print(f"Budget max:       ${BUDGET_MAX_USD:.2f}")
    print(f"Force re-analyze: {FORCE}")
    print(f"Cookie for retry: {'present' if cookie else 'not set'}")
    if HIGHLIGHT_IDS:
        print(f"Highlight filter: {HIGHLIGHT_IDS}")
    print()

    run_summary = analyzer.analyze(
        client               = client,
        max_stories_per_hl   = MAX_STORIES_PER_HL,
        selection_mode       = SELECTION_MODE,
        highlight_ids_filter = HIGHLIGHT_IDS,
        model                = MODEL,
        detail               = DETAIL,
        budget_max_usd       = BUDGET_MAX_USD,
        image_input_mode     = IMAGE_INPUT_MODE,
        cookie               = cookie,
        force                = FORCE,
    )

    print("\n=== Creating report ===")
    import stage5c_create_report as reporter
    reporter.main()

    print("\n=== Stage 5C complete ===")
    print(f"  analyzed:     {run_summary['total_analyzed']}")
    print(f"  from_cache:   {run_summary['total_from_cache']}")
    print(f"  skipped:      {run_summary['total_skipped']}")
    print(f"  errors:       {run_summary['total_errors']}")
    print(f"  cost spent:   ${run_summary['cumulative_cost_usd']:.4f}")
    print(f"  budget left:  ${BUDGET_MAX_USD - run_summary['cumulative_cost_usd']:.4f}")
    if run_summary.get("budget_reached"):
        print(f"  [WARN] Budget ${BUDGET_MAX_USD:.2f} reached — run again to continue.")
    print()
    print("Runtime outputs (not committed):")
    print("  data/raw/stage5c_cache/            ← per-story cache")
    print("  data/normalized/stage5c_stories_analysis.json")
    print("  data/normalized/stage5c_highlights_summary.json")
    print("  report/stage_5c_analysis_report.md")
    print()
    print("Next:")
    print("  cat report/stage_5c_analysis_report.md")


if __name__ == "__main__":
    main()
