import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent

PLAN_CHECK_PATH    = BASE / "data/normalized/stage4b_plan_check.json"
POSTS_SUMMARY_PATH = BASE / "data/normalized/stage4b_posts_summary.json"
BATCHES_SUMMARY_PATH = BASE / "data/normalized/stage4b_highlight_batches_summary.json"
POSTS_OUT_DIR      = BASE / "analysis/stage4b/posts"
BATCHES_OUT_DIR    = BASE / "analysis/stage4b/highlight_batches"
REPORT_PATH        = BASE / "report/stage_4b_openai_analysis_report.md"


def load_json(path, label):
    if not path.exists():
        return None, f"{label} not found"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{label} parse error: {e}"


plan_check,      pc_err  = load_json(PLAN_CHECK_PATH,    "stage4b_plan_check.json")
posts_summary,   ps_err  = load_json(POSTS_SUMMARY_PATH, "stage4b_posts_summary.json")
batches_summary, bs_err  = load_json(BATCHES_SUMMARY_PATH, "stage4b_highlight_batches_summary.json")

lines = []
lines.append("# Stage 4B — OpenAI Analysis Report")
lines.append(f"\n_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n")

# ── Scope ──────────────────────────────────────────────────────────────────────
lines.append("## Scope\n")
lines.append("Stage 4B did:")
lines.append("- OpenAI analysis of 5 posts")
lines.append("- OpenAI analysis of 8 highlight batches")
lines.append("- Structured JSON outputs per post and per batch\n")
lines.append("Stage 4B did NOT do:")
lines.append("- Highlight synthesis")
lines.append("- Final account report")
lines.append("- Bio analysis")
lines.append("- Pinned posts analysis")
lines.append("- New scraping or media downloading\n")

# ── Plan check ────────────────────────────────────────────────────────────────
lines.append("## Plan Check\n")
if pc_err:
    lines.append(f"> ERROR: {pc_err}\n")
else:
    lines.append(f"- stage4b_can_continue: `{plan_check.get('stage4b_can_continue')}`")
    lines.append(f"- posts requests: `{plan_check.get('posts_requests')}`")
    lines.append(f"- highlight batch requests: `{plan_check.get('highlight_batch_requests')}`")
    lines.append(f"- all prepared files found: `{plan_check.get('all_prepared_files_found')}`")
    lines.append(f"- limits ok: `{plan_check.get('limits_ok')}`")
    lines.append(f"- planned calls: `{plan_check.get('planned_calls_to_make')}`")
    lines.append(f"- max calls allowed: `{plan_check.get('max_openai_calls_allowed')}`")
    errs = plan_check.get("errors", [])
    if errs:
        lines.append("\n**Errors:**")
        for e in errs:
            lines.append(f"- {e}")
lines.append("")

# ── Posts analysis ────────────────────────────────────────────────────────────
lines.append("## Posts Analysis\n")
if ps_err:
    lines.append(f"> ERROR: {ps_err}\n")
else:
    lines.append(f"- posts total: `{posts_summary.get('posts_total')}`")
    lines.append(f"- OK: `{posts_summary.get('posts_ok')}`")
    lines.append(f"- PARTIAL: `{posts_summary.get('posts_partial')}`")
    lines.append(f"- FAIL: `{posts_summary.get('posts_fail')}`")
    lines.append(f"- skipped existing OK: `{posts_summary.get('posts_skipped_existing_ok')}`")
    lines.append(f"- OpenAI calls made: `{posts_summary.get('openai_calls_made')}`")
    perrs = posts_summary.get("errors", [])
    if perrs:
        lines.append("\n**Errors:**")
        for e in perrs:
            lines.append(f"- {e}")
    lines.append("")

    # Per-post detail
    post_files = sorted(POSTS_OUT_DIR.glob("*.json")) if POSTS_OUT_DIR.exists() else []
    if post_files:
        lines.append("| request_id | status | topic | cta | offer | funnel_role | score | confidence | evidence |")
        lines.append("|------------|--------|-------|-----|-------|-------------|-------|------------|----------|")
        for pf in post_files:
            try:
                pd = json.loads(pf.read_text(encoding="utf-8"))
            except Exception:
                lines.append(f"| {pf.stem} | ERROR | — | — | — | — | — | — | — |")
                continue
            im = pd.get("inferred_meanings", {})
            lines.append(
                f"| {pf.stem} "
                f"| {pd.get('status','?')} "
                f"| {str(im.get('topic','?'))[:40]} "
                f"| {str(im.get('cta','?'))[:30]} "
                f"| {str(im.get('offer','?'))[:30]} "
                f"| {im.get('funnel_role','?')} "
                f"| {pd.get('score','?')} "
                f"| {pd.get('confidence','?')} "
                f"| {len(pd.get('evidence',[]))} |"
            )
        lines.append("")

# ── Highlight batches analysis ────────────────────────────────────────────────
lines.append("## Highlight Batches Analysis\n")
if bs_err:
    lines.append(f"> ERROR: {bs_err}\n")
else:
    lines.append(f"- batches total: `{batches_summary.get('batches_total')}`")
    lines.append(f"- OK: `{batches_summary.get('batches_ok')}`")
    lines.append(f"- PARTIAL: `{batches_summary.get('batches_partial')}`")
    lines.append(f"- FAIL: `{batches_summary.get('batches_fail')}`")
    lines.append(f"- skipped existing OK: `{batches_summary.get('batches_skipped_existing_ok')}`")
    lines.append(f"- OpenAI calls made: `{batches_summary.get('openai_calls_made')}`")
    berrs = batches_summary.get("errors", [])
    if berrs:
        lines.append("\n**Errors:**")
        for e in berrs:
            lines.append(f"- {e}")
    lines.append("")

    batch_files = sorted(BATCHES_OUT_DIR.glob("*.json")) if BATCHES_OUT_DIR.exists() else []
    if batch_files:
        lines.append(
            "| request_id | status | stories | inputs | main_roles | cta | offer | social_proof "
            "| dss | confidence | evidence |"
        )
        lines.append(
            "|------------|--------|---------|--------|------------|-----|-------|-------------|"
            "-----|------------|----------|"
        )
        for bf in batch_files:
            try:
                bd = json.loads(bf.read_text(encoding="utf-8"))
            except Exception:
                lines.append(f"| {bf.stem} | ERROR | — | — | — | — | — | — | — | — | — |")
                continue
            im    = bd.get("inferred_meanings", {})
            roles = ", ".join(im.get("main_roles", [])) or "?"
            lines.append(
                f"| {bf.stem} "
                f"| {bd.get('status','?')} "
                f"| {bd.get('stories_analyzed','?')} "
                f"| {bd.get('visual_inputs_count','?')} "
                f"| {str(roles)[:35]} "
                f"| {str(im.get('cta_found','?'))[:25]} "
                f"| {str(im.get('offer_found','?'))[:25]} "
                f"| {str(im.get('social_proof_found','?'))[:25]} "
                f"| {im.get('decision_support_score','?')} "
                f"| {bd.get('confidence','?')} "
                f"| {len(bd.get('evidence',[]))} |"
            )
        lines.append("")

# ── Output files ───────────────────────────────────────────────────────────────
lines.append("## Output Files\n")
lines.append("```")
lines.append("analysis/stage4b/posts/")
lines.append("analysis/stage4b/highlight_batches/")
lines.append("analysis/openai_responses/stage4b/posts/")
lines.append("analysis/openai_responses/stage4b/highlight_batches/")
lines.append("data/normalized/stage4b_posts_summary.json")
lines.append("data/normalized/stage4b_highlight_batches_summary.json")
lines.append("```\n")

# ── Final verdict ──────────────────────────────────────────────────────────────
lines.append("## Final Verdict\n")

p_ok   = (posts_summary   or {}).get("posts_ok",    0)
p_fail = (posts_summary   or {}).get("posts_fail",   0)
p_part = (posts_summary   or {}).get("posts_partial",0)
b_ok   = (batches_summary or {}).get("batches_ok",  0)
b_fail = (batches_summary or {}).get("batches_fail", 0)
b_part = (batches_summary or {}).get("batches_partial", 0)

if ps_err or bs_err:
    verdict = "FAIL"
elif p_fail == 0 and p_part == 0 and b_fail == 0 and b_part == 0:
    verdict = "OK"
elif (p_ok + p_part) > 0 or (b_ok + b_part) > 0:
    verdict = "PARTIAL"
else:
    verdict = "FAIL"

lines.append(f"**{verdict}**\n")

# ── Recommendation ─────────────────────────────────────────────────────────────
lines.append("## Recommendation\n")

if verdict == "OK":
    lines.append("All posts and batches analyzed successfully.")
    lines.append("Stage 4C (highlight synthesis + final account report) can proceed.\n")
    lines.append("**Remaining limitations before Stage 4C:**")
    lines.append("- Highlight synthesis not done — 8 batch outputs need synthesis pass")
    lines.append("- Bio and pinned posts not analyzed")
    lines.append("- Each batch analyzed independently; cross-batch patterns not resolved")
elif verdict == "PARTIAL":
    lines.append("Some outputs are PARTIAL or FAIL.")
    lines.append("**Before Stage 4C:**")
    if p_fail > 0 or p_part > 0:
        lines.append(f"- Re-run posts analysis: {p_fail} FAIL, {p_part} PARTIAL")
    if b_fail > 0 or b_part > 0:
        lines.append(f"- Re-run highlight batches: {b_fail} FAIL, {b_part} PARTIAL")
    lines.append("- Use `--force` to re-run specific failed requests")
    lines.append("- Fix FAIL outputs before running Stage 4C synthesis")
else:
    lines.append("Stage 4B failed. Do not proceed to Stage 4C.")
    lines.append("Fix errors listed above and re-run `stage4b_run_local.py`.")

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"verdict: {verdict}")
print(f"report saved: {REPORT_PATH.relative_to(BASE)}")
