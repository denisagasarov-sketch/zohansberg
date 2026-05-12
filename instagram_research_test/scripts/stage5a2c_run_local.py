"""Stage 5A-2C local runner: Caption-only semantic analyzer for pinned posts.

Usage:
    python3 scripts/stage5a2c_run_local.py --dry-run
    python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10
    python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10 --force
    python3 scripts/stage5a2c_run_local.py --create-report
    python3 scripts/stage5a2c_run_local.py --validate-existing-output
    python3 scripts/stage5a2c_run_local.py --validate-existing-output --write-fixed
    python3 scripts/stage5a2c_run_local.py --validate-existing-output --write-fixed --overwrite
    python3 scripts/stage5a2c_run_local.py --regression-checks
"""

import argparse
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))

from stage5a2c_analyze_pinned_posts_caption import (
    ACCOUNT,
    ALLOWED_DESTINATION_ATOMS,
    ALLOWED_FUNNEL_ROLES,
    CACHE_DIR,
    CELL_LIMITS,
    COST_PER_CALL,
    DEFAULT_MODEL,
    EXPECTED_POSTS,
    GS_FIELD_ORDER,
    GS_ROWS_FIXED_PATH,
    GS_ROWS_OUTPUT_PATH,
    PROMPT_VERSION,
    SEMANTIC_FIXED_PATH,
    SEMANTIC_OUTPUT_PATH,
    STAGE5A2B_PATH,
    build_full_output,
    build_gs_row,
    build_gs_rows_output,
    build_semantic_post,
    build_user_prompt,
    load_stage5a2b,
    run_analysis,
    run_regression_checks,
    validate_inputs,
    validate_output,
    _validate_and_fix,
)
from stage5a2c_create_report import create_report


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(model: str = DEFAULT_MODEL):
    print("[DRY-RUN] No external calls. No files will be written.\n")

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

    cost_per_call = COST_PER_CALL.get(model, 0.001)
    total_est     = cost_per_call * len(posts)
    print("── Cost estimate ───────────────────────────────────────────────────")
    print(f"  Model:             {model}")
    print(f"  Cost per call:     ${cost_per_call:.4f} (conservative estimate)")
    print(f"  Posts:             {len(posts)}")
    print(f"  Total estimate:    ${total_est:.4f}")
    print(f"  Cache dir:         {CACHE_DIR.relative_to(BASE)}")
    print(f"  Cached results reused at zero cost. Use --force to bypass.")
    print()

    print("── Field constraints ───────────────────────────────────────────────")
    for field, limit in CELL_LIMITS.items():
        note = "always empty (visual/OCR not done)" if limit == 0 else f"max {limit} chars"
        print(f"  {field:<24} {note}")
    print()
    print(f"  Allowed Роль atoms:      {sorted(ALLOWED_FUNNEL_ROLES)}")
    print(f"  Allowed CTA dest atoms:  {sorted(ALLOWED_DESTINATION_ATOMS)}")
    print()

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

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    key_ok = bool(openai_key and openai_key.startswith("sk-"))
    print("── Environment ─────────────────────────────────────────────────────")
    print(f"  OPENAI_API_KEY: {'SET (format OK)' if key_ok else 'NOT SET or invalid — required for --analyze'}")
    print()

    print("── Planned runtime outputs (gitignored) ────────────────────────────")
    print(f"  {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {GS_ROWS_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  {CACHE_DIR.relative_to(BASE)}/<key>.json")
    print(f"  report/stage_5a2c_pinned_posts_caption_analysis_report.md")
    print()

    print("── Google Sheets output columns ────────────────────────────────────")
    for i, col in enumerate(GS_FIELD_ORDER, 1):
        print(f"  {i:2}. {col}")
    print()

    print("[DRY-RUN] Complete. To run analysis:")
    print(f"  set -a; source .env; set +a")
    print(f"  python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10")


# ---------------------------------------------------------------------------
# Regression checks
# ---------------------------------------------------------------------------

def run_regression_checks_mode():
    print("Mode: --regression-checks\n")
    passed, failed, errors = run_regression_checks()
    total = passed + failed
    print(f"Regression checks: {passed}/{total} passed")
    if errors:
        print()
        for e in errors:
            print(f"  {e}")
        print()
        print(f"[FAIL] {failed} check(s) failed.")
        sys.exit(1)
    else:
        print("[OK] All regression checks passed.")


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

def run_analyze_mode(budget_usd: float, model: str, force: bool):
    print(f"Mode: --analyze  model={model}  budget=${budget_usd:.2f}  force={force}")

    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_key:
        print("[ERROR] OPENAI_API_KEY is not set.")
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
        for e in load_errors:
            print(f"[ERROR] {e}")
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
# Validate existing output
# ---------------------------------------------------------------------------

def run_validate_existing_output(write_fixed: bool = False, overwrite: bool = False):
    print(f"Mode: --validate-existing-output  write_fixed={write_fixed}  overwrite={overwrite}\n")

    if not SEMANTIC_OUTPUT_PATH.exists():
        print(f"[ERROR] {SEMANTIC_OUTPUT_PATH.relative_to(BASE)} not found.")
        print("  Run --analyze first.")
        sys.exit(1)
    if not GS_ROWS_OUTPUT_PATH.exists():
        print(f"[WARNING] {GS_ROWS_OUTPUT_PATH.relative_to(BASE)} not found — skipping rows validation.")

    # Load semantic output
    try:
        semantic_output = json.loads(SEMANTIC_OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ERROR] Cannot parse {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}: {e}")
        sys.exit(1)

    gs_rows_output = None
    if GS_ROWS_OUTPUT_PATH.exists():
        try:
            gs_rows_output = json.loads(GS_ROWS_OUTPUT_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARNING] Cannot parse GS rows: {e}")

    print(f"Source:        {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}")
    print(f"Model:         {semantic_output.get('model', '—')}")
    print(f"Prompt ver:    {semantic_output.get('prompt_version', '—')}")
    print(f"Posts:         {semantic_output.get('total_posts', 0)}")
    print()

    # Run structural validation
    val_errors = validate_output(semantic_output)

    # Run per-post postprocessing check
    pp_issues: list[str] = []
    fixed_posts: list[dict] = []
    any_pp_changes = False

    for sem in semantic_output.get("posts") or []:
        gf  = sem.get("google_sheet_fields") or {}
        pos = sem.get("position")

        # Re-run _validate_and_fix on the fields as if they came from OpenAI
        analysis_fields = dict(gf)
        analysis_fields["confidence"] = sem.get("confidence") or {}
        analysis_fields["evidence"]   = sem.get("evidence") or {}
        analysis_fields["limitations"] = []

        fixed_fields, new_warns, new_notes = _validate_and_fix(analysis_fields, {})

        if new_notes:
            any_pp_changes = True
            pp_issues.append(f"Post {pos}: {len(new_notes)} postprocessing fix(es) needed")
            for note in new_notes:
                pp_issues.append(
                    f"  [{note['field']}] {note['reason']}"
                    f"  orig={note['original_value'][:60]!r} → final={note['final_value'][:60]!r}"
                )

        # Build fixed semantic post
        new_gf = {k: v for k, v in fixed_fields.items()
                  if k in CELL_LIMITS or k == "Хук / первый экран"}
        fixed_sem = dict(sem)
        fixed_sem["google_sheet_fields"]  = {
            "Тема поста":            fixed_fields.get("Тема поста", ""),
            "Почему закреплен":      fixed_fields.get("Почему закреплен", ""),
            "Хук / первый экран":    "",
            "Что в тексте поста":    fixed_fields.get("Что в тексте поста", ""),
            "Ключевые смыслы":       fixed_fields.get("Ключевые смыслы", ""),
            "Какой CTA":             fixed_fields.get("Какой CTA", ""),
            "Куда ведет CTA":        fixed_fields.get("Куда ведет CTA", ""),
            "Роль в воронке":        fixed_fields.get("Роль в воронке", ""),
        }
        fixed_sem["confidence"]           = fixed_fields.get("confidence", {})
        fixed_sem["validation_warnings"]  = (sem.get("validation_warnings") or []) + new_warns
        fixed_sem["postprocessing_notes"] = (sem.get("postprocessing_notes") or []) + new_notes
        fixed_posts.append(fixed_sem)

    # Rows consistency check
    rows_issues: list[str] = []
    if gs_rows_output:
        rows = gs_rows_output.get("rows") or []
        if len(rows) != len(semantic_output.get("posts") or []):
            rows_issues.append(
                f"Row count mismatch: semantic has {len(semantic_output.get('posts') or [])} posts, "
                f"rows has {len(rows)}"
            )
        for row in rows:
            if len(row) != len(GS_FIELD_ORDER):
                rows_issues.append(
                    f"Row has {len(row)} columns, expected {len(GS_FIELD_ORDER)}"
                )
        # Check Хук column
        hook_idx = GS_FIELD_ORDER.index("Хук / первый экран")
        for i, row in enumerate(rows):
            if len(row) > hook_idx and row[hook_idx] != "":
                rows_issues.append(f"Row {i+1}: 'Хук / первый экран' column is non-empty")

    # Print validation results
    all_clean = True

    if val_errors:
        all_clean = False
        print(f"Structural validation issues ({len(val_errors)}):")
        for e in val_errors:
            print(f"  - {e}")
        print()

    if pp_issues:
        all_clean = False
        print(f"Postprocessing issues ({len(pp_issues)} lines):")
        for line in pp_issues:
            print(f"  {line}")
        print()

    if rows_issues:
        all_clean = False
        print(f"Rows JSON issues ({len(rows_issues)}):")
        for e in rows_issues:
            print(f"  - {e}")
        print()

    if all_clean:
        print("[OK] Existing output passes all validation checks.")
    else:
        print("[ISSUES FOUND] See details above.")

    # Run regression checks
    print()
    r_passed, r_failed, r_errors = run_regression_checks()
    print(f"Regression checks: {r_passed}/{r_passed + r_failed} passed")
    if r_errors:
        for e in r_errors:
            print(f"  {e}")

    # Write fixed output if requested
    if write_fixed and any_pp_changes:
        _write_fixed_outputs(semantic_output, fixed_posts, overwrite)
    elif write_fixed and not any_pp_changes:
        print("\n[SKIP] No postprocessing fixes needed; --write-fixed skipped.")


def _write_fixed_outputs(original_output: dict, fixed_posts: list[dict], overwrite: bool):
    from datetime import datetime, timezone

    fixed_output = dict(original_output)
    fixed_output["posts"] = fixed_posts
    fixed_output["fixed_at"] = datetime.now(timezone.utc).isoformat()

    sem_target = SEMANTIC_OUTPUT_PATH if overwrite else SEMANTIC_FIXED_PATH
    gs_target  = GS_ROWS_OUTPUT_PATH  if overwrite else GS_ROWS_FIXED_PATH

    sem_target.parent.mkdir(parents=True, exist_ok=True)
    sem_target.write_text(
        json.dumps(fixed_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nFixed semantic:  {sem_target.relative_to(BASE)}")

    gs_rows = build_gs_rows_output(fixed_posts, original_output.get("posts") or [])
    gs_target.parent.mkdir(parents=True, exist_ok=True)
    gs_target.write_text(
        json.dumps(gs_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Fixed GS rows:   {gs_target.relative_to(BASE)}")

    if overwrite:
        print("[OVERWRITE] Original files replaced.")
    else:
        print("[SAFE] Originals preserved; fixed copies written.")


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
        gf   = sem.get("google_sheet_fields") or {}
        conf = sem.get("confidence") or {}
        notes = sem.get("postprocessing_notes") or []
        print(f"  Post {sem.get('position')} [{sem.get('openai_status')}]:")
        print(f"    Тема поста:      {(gf.get('Тема поста') or '')[:80] or '—'}")
        print(f"    Роль в воронке:  {gf.get('Роль в воронке') or '—'}")
        print(f"    Какой CTA:       {(gf.get('Какой CTA') or '')[:60] or '—'}")
        print(f"    Куда ведет CTA:  {gf.get('Куда ведет CTA') or '—'}")
        print(f"    Cache status:    {sem.get('cache_status')}")
        print(f"    Tokens used:     {sem.get('tokens_used') or 0}")
        if notes:
            print(f"    PP fixes:        {len(notes)}")
            for n in notes[:3]:
                print(f"      [{n['field']}] {n['reason']}")
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
    mode_group.add_argument(
        "--validate-existing-output", action="store_true",
        help="Validate existing semantic/rows output; no OpenAI calls",
    )
    mode_group.add_argument(
        "--regression-checks", action="store_true",
        help="Run deterministic regression checks; no external calls",
    )
    parser.add_argument(
        "--budget-max-usd", type=float, default=1.0,
        help="Maximum allowed spend for --analyze (default 1.00)",
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL,
        help=f"OpenAI model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass cache and re-run all OpenAI calls",
    )
    parser.add_argument(
        "--write-fixed", action="store_true",
        help="With --validate-existing-output: write corrected output to _fixed.json files",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="With --validate-existing-output --write-fixed: overwrite original files",
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
    elif args.validate_existing_output:
        run_validate_existing_output(
            write_fixed=args.write_fixed,
            overwrite=args.overwrite,
        )
    elif args.regression_checks:
        run_regression_checks_mode()
    else:
        run_dry_run(model=args.model)


if __name__ == "__main__":
    main()
