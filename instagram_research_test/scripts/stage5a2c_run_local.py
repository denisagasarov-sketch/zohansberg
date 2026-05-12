"""Stage 5A-2C local runner: Caption-only semantic analyzer for pinned posts.

Usage:
    python3 scripts/stage5a2c_run_local.py --dry-run
    python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10
    python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10 --force
    python3 scripts/stage5a2c_run_local.py --create-report
"""

import argparse
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from stage5a2c_analyze_pinned_posts_caption import (
    ACCOUNT,
    CACHE_DIR,
    CELL_LIMITS,
    COST_PER_CALL,
    DEFAULT_MODEL,
    EXPECTED_POSTS,
    GS_ROWS_OUTPUT_PATH,
    PROMPT_VERSION,
    SEMANTIC_OUTPUT_PATH,
    STAGE5A2B_PATH,
    ALLOWED_FUNNEL_ROLES,
    ALLOWED_CTA_DESTINATIONS,
    GS_FIELD_ORDER,
    build_user_prompt,
    load_stage5a2b,
    run_analysis,
    validate_inputs,
)
from stage5a2c_create_report import create_report


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(model: str = DEFAULT_MODEL):
    print("[DRY-RUN] No external calls. No files will be written.\n")

    # Check stage5a2b input
    if not STAGE5A2B_PATH.exists():
        print(f"[ERROR] {STAGE5A2B_PATH.relative_to(BASE)} not found.")
        print("  Run Stage 5A-2B first to collect pinned post details.")
        sys.exit(1)

    stage5a2b, load_errors = load_stage5a2b()
    if load_errors:
        print("[ERROR] Cannot load Stage 5A-2B output:")
        for e in load_errors:
            print(f"  - {e}")
        sys.exit(1)

    val_errors = validate_inputs(stage5a2b)
    if val_errors:
        print("[ERROR] Stage 5A-2B input validation failed:")
        for e in val_errors:
            print(f"  - {e}")
        sys.exit(1)

    posts = stage5a2b.get("posts") or []

    print(f"Source:       {STAGE5A2B_PATH.relative_to(BASE)}")
    print(f"Account:      {ACCOUNT}")
    print(f"Posts found:  {len(posts)}")
    print(f"Model:        {model}")
    print(f"Prompt ver:   {PROMPT_VERSION}")
    print()

    # Per-post preview
    print("── Posts to analyze ────────────────────────────────────────────────")
    for p in posts:
        cap     = p.get("full_caption") or p.get("caption_for_analysis") or ""
        cap_len = p.get("caption_length", len(cap))
        readiness = p.get("analysis_readiness", {})
        cap_ok  = readiness.get("caption_semantic_possible", False)
        print(f"  Post {p.get('position')}:")
        print(f"    shortcode:                {p.get('shortcode') or '—'}")
        print(f"    media_type:               {p.get('media_type') or '—'}")
        print(f"    caption_length:           {cap_len} chars")
        print(f"    caption_semantic_possible:{cap_ok}")
        if not cap_ok:
            print(f"    *** WARNING: caption_semantic_possible=False; analysis may be poor")
    print()

    # Cost estimate
    cost_per_call = COST_PER_CALL.get(model, 0.001)
    total_est     = cost_per_call * len(posts)
    print("── Cost estimate ───────────────────────────────────────────────────")
    print(f"  Model:             {model}")
    print(f"  Cost per call:     ${cost_per_call:.4f} (conservative estimate)")
    print(f"  Posts:             {len(posts)}")
    print(f"  Total estimate:    ${total_est:.4f}")
    print(f"  Cache dir:         {CACHE_DIR.relative_to(BASE)}")
    print(f"  Cached results will be reused (no charge). Use --force to bypass.")
    print()

    # Field constraints summary
    print("── Field constraints ───────────────────────────────────────────────")
    for field, limit in CELL_LIMITS.items():
        note = "always empty (visual/OCR not done)" if limit == 0 else f"max {limit} chars"
        print(f"  {field:<24} {note}")
    print()
    print(f"  Allowed Роль values:     {sorted(ALLOWED_FUNNEL_ROLES)}")
    print(f"  Allowed CTA dest values: {sorted(ALLOWED_CTA_DESTINATIONS)}")
    print()

    # Prompt preview (first post only)
    if posts:
        p0 = posts[0]
        prompt = build_user_prompt(p0)
        prompt_lines = prompt.splitlines()
        print("── Prompt preview (post 1, first 15 lines) ─────────────────────────")
        for line in prompt_lines[:15]:
            print(f"  {line}")
        if len(prompt_lines) > 15:
            print(f"  ... ({len(prompt_lines) - 15} more lines)")
        print()

    # Environment
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    key_ok = bool(openai_key and openai_key.startswith("sk-"))
    print("── Environment ─────────────────────────────────────────────────────")
    print(f"  OPENAI_API_KEY: {'SET (format OK)' if key_ok else 'NOT SET or invalid format — required for --analyze'}")
    print()

    # Planned outputs
    print("── Planned runtime outputs (gitignored) ────────────────────────────")
    print(f"  {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {GS_ROWS_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {CACHE_DIR.relative_to(BASE)}/<post_id>__<model>__pv{PROMPT_VERSION}__<cap_hash>.json")
    print(f"  report/stage_5a2c_pinned_posts_caption_analysis_report.md")
    print()

    # Google Sheets columns
    print("── Google Sheets output columns ────────────────────────────────────")
    for i, col in enumerate(GS_FIELD_ORDER, 1):
        print(f"  {i:2}. {col}")
    print()

    print("[DRY-RUN] Complete. To run analysis:")
    print(f"  set -a; source .env; set +a")
    print(f"  python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10")


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

def run_analyze_mode(budget_usd: float, model: str, force: bool):
    print(f"Mode: --analyze  model={model}  budget=${budget_usd:.2f}  force={force}")

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        print("[ERROR] OPENAI_API_KEY is not set in environment.")
        print("  Run: set -a; source .env; set +a")
        sys.exit(1)
    if not openai_key.startswith("sk-"):
        print("[ERROR] OPENAI_API_KEY format looks invalid (expected sk- prefix).")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        print("[ERROR] openai package not installed. Run: pip install openai")
        sys.exit(1)

    if not STAGE5A2B_PATH.exists():
        print(f"[ERROR] {STAGE5A2B_PATH.relative_to(BASE)} not found.")
        print("  Run Stage 5A-2B first.")
        sys.exit(1)

    stage5a2b, load_errors = load_stage5a2b()
    if load_errors:
        print("[ERROR] Cannot load Stage 5A-2B output:")
        for e in load_errors:
            print(f"  - {e}")
        sys.exit(1)

    client = OpenAI(api_key=openai_key)
    print(f"  Posts to analyze: {len(stage5a2b.get('posts') or [])}")
    print()

    try:
        output = run_analysis(client, stage5a2b, model=model, budget_usd=budget_usd, force=force)
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    _print_analysis_summary(output)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def run_create_report_mode():
    print("Mode: --create-report")
    if not SEMANTIC_OUTPUT_PATH.exists():
        print(f"[ERROR] {SEMANTIC_OUTPUT_PATH.relative_to(BASE)} not found.")
        print("  Run --analyze first.")
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

def _print_analysis_summary(output: dict):
    cache = output.get("cache_summary", {})
    print()
    print("=== Analysis Summary ===")
    print(f"  Account:         {output.get('account', '—')}")
    print(f"  Total posts:     {output.get('total_posts', 0)}")
    print(f"  Model:           {output.get('model', '—')}")
    print(f"  Prompt version:  {output.get('prompt_version', '—')}")
    print(f"  Cache hits:      {cache.get('hits', 0)}")
    print(f"  New API calls:   {cache.get('new', 0)}")
    print(f"  Failed:          {cache.get('failed', 0)}")
    print(f"  Total tokens:    {output.get('total_tokens_used', 0)}")
    print(f"  Estimated cost:  ${output.get('estimated_cost_usd', 0):.4f}")
    print()

    for sem in output.get("posts") or []:
        gf = sem.get("google_sheet_fields") or {}
        conf = sem.get("confidence") or {}
        print(f"  Post {sem.get('position')} [{sem.get('openai_status')}]:")
        print(f"    Тема поста:      {(gf.get('Тема поста') or '')[:80] or '—'}")
        print(f"    Роль в воронке:  {gf.get('Роль в воронке') or '—'}")
        print(f"    Какой CTA:       {(gf.get('Какой CTA') or '')[:60] or '—'}")
        print(f"    Куда ведет CTA:  {gf.get('Куда ведет CTA') or '—'}")
        print(f"    Cache status:    {sem.get('cache_status')}")
        print(f"    Tokens used:     {sem.get('tokens_used') or 0}")
        warns = sem.get("validation_warnings") or []
        if warns:
            print(f"    Validation warns: {len(warns)}")
            for w in warns[:3]:
                print(f"      - {w}")
        print()

    print(f"Semantic JSON: {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}")
    print(f"GS rows JSON:  {GS_ROWS_OUTPUT_PATH.relative_to(BASE)}")
    print()
    print("Next step: python3 scripts/stage5a2c_run_local.py --create-report")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2C: Caption-only semantic analyzer for pinned posts"
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Print plan; no external calls (default)",
    )
    mode_group.add_argument(
        "--analyze", action="store_true",
        help="Run OpenAI caption analysis (requires OPENAI_API_KEY)",
    )
    mode_group.add_argument(
        "--create-report", action="store_true",
        help="Generate report from existing semantic output",
    )
    parser.add_argument(
        "--budget-max-usd", type=float, default=1.0,
        help="Maximum allowed spend in USD for --analyze (default 1.00)",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"OpenAI model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass cache and re-run all OpenAI calls",
    )
    args = parser.parse_args()

    if args.analyze:
        run_analyze_mode(
            budget_usd=args.budget_max_usd,
            model=args.model,
            force=args.force,
        )
    elif args.create_report:
        run_create_report_mode()
    else:
        run_dry_run(model=args.model)


if __name__ == "__main__":
    main()
