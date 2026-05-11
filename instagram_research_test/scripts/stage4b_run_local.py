import subprocess
import sys
from pathlib import Path

BASE    = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent

DRY_RUN = "--dry-run" in sys.argv
FORCE   = "--force"   in sys.argv

extra_args = []
if DRY_RUN:
    extra_args.append("--dry-run")
if FORCE:
    extra_args.append("--force")

print("=" * 60)
print("Stage 4B — OpenAI Analysis by Approved Stage 4A Plan")
if DRY_RUN:
    print("MODE: DRY-RUN (no OpenAI calls will be made)")
if FORCE:
    print("FLAG: --force (existing OK outputs will be re-analyzed)")
print("=" * 60)


def run(script_name, args=None):
    cmd = [sys.executable, str(SCRIPTS / script_name)] + (args or [])
    result = subprocess.run(cmd, cwd=str(BASE))
    return result.returncode


# ── 1. Check plan ─────────────────────────────────────────────────────────────
print("\n── stage4b_check_plan ──")
rc = run("stage4b_check_plan.py", extra_args)
if rc != 0:
    print("\nERROR: plan check failed. Stopping.")
    sys.exit(rc)

if DRY_RUN:
    # Show dry-run for both analysis scripts, then exit
    print("\n── stage4b_analyze_posts (dry-run) ──")
    run("stage4b_analyze_posts.py", extra_args)
    print("\n── stage4b_analyze_highlight_batches (dry-run) ──")
    run("stage4b_analyze_highlight_batches.py", extra_args)
    print("\n" + "=" * 60)
    print("Dry-run complete. No API calls were made.")
    print("=" * 60)
    sys.exit(0)

# ── 2. Analyze posts ──────────────────────────────────────────────────────────
print("\n── stage4b_analyze_posts ──")
posts_rc = run("stage4b_analyze_posts.py", extra_args)
if posts_rc != 0:
    print("  WARNING: posts analysis exited with errors — continuing to batches")

# ── 3. Analyze highlight batches ─────────────────────────────────────────────
print("\n── stage4b_analyze_highlight_batches ──")
batches_rc = run("stage4b_analyze_highlight_batches.py", extra_args)
if batches_rc != 0:
    print("  WARNING: highlight batches analysis exited with errors — continuing to report")

# ── 4. Create report ─────────────────────────────────────────────────────────
print("\n── stage4b_create_report ──")
run("stage4b_create_report.py")

print("\n" + "=" * 60)
print("Stage 4B complete.")
print("=" * 60)
print("\nOutput files:")
print("  analysis/stage4b/posts/")
print("  analysis/stage4b/highlight_batches/")
print("  analysis/openai_responses/stage4b/  (gitignored)")
print("  data/normalized/stage4b_posts_summary.json")
print("  data/normalized/stage4b_highlight_batches_summary.json")
print("  report/stage_4b_openai_analysis_report.md")
print("\nNext: review report/stage_4b_openai_analysis_report.md")
print("      then run Stage 4C when ready.")

if posts_rc != 0 or batches_rc != 0:
    sys.exit(1)
