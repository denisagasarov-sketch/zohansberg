import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent

INPUTS_CHECK_PATH = BASE / "data/normalized/stage4a_inputs_check.json"
MANIFEST_PATH     = BASE / "data/normalized/stage4a_media_manifest.json"
PLAN_PATH         = BASE / "data/normalized/stage4a_openai_plan.json"
REPORT_PATH       = BASE / "report/stage_4a_media_and_openai_plan.md"

def load_json(path, label):
    if not path.exists():
        return None, f"{label} not found"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{label} parse error: {e}"

inputs_check, ic_err = load_json(INPUTS_CHECK_PATH, "stage4a_inputs_check.json")
manifest,     mn_err = load_json(MANIFEST_PATH,     "stage4a_media_manifest.json")
plan,         pl_err = load_json(PLAN_PATH,         "stage4a_openai_plan.json")

lines = []
lines.append("# Stage 4A — Media Preparation & OpenAI Plan Report")
lines.append(f"\n_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n")

# ── 1. Inputs check ───────────────────────────────────────────────────────────
lines.append("## 1. Inputs Check\n")
if ic_err:
    lines.append(f"> ERROR: {ic_err}\n")
else:
    can = inputs_check.get("stage4a_can_continue", False)
    lines.append(f"**stage4a_can_continue:** `{can}`\n")
    for key, result in [
        ("posts_raw",             inputs_check.get("posts_raw", {})),
        ("highlight_stories_raw", inputs_check.get("highlight_stories_raw", {})),
        ("stage3a_manifest",      inputs_check.get("stage3a_manifest", {})),
        ("stage3b1_preview",      inputs_check.get("stage3b1_preview", {})),
    ]:
        status = result.get("status", "?")
        exists = result.get("exists", False)
        count  = result.get("items_count")
        detail = f"exists={exists}, status={status}" + (f", count={count}" if count is not None else "")
        lines.append(f"- **{key}**: {detail}")
    gs = inputs_check.get("gitignore_safe", False)
    lines.append(f"- **gitignore_safe**: {gs}")
    errs = inputs_check.get("errors", [])
    if errs:
        lines.append("\n**Errors:**")
        for e in errs:
            lines.append(f"- {e}")
lines.append("")

# ── 2. Media manifest summary ─────────────────────────────────────────────────
lines.append("## 2. Media Manifest Summary\n")
if mn_err:
    lines.append(f"> ERROR: {mn_err}\n")
else:
    summary = manifest.get("summary", {})
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    for k, v in summary.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    posts = manifest.get("posts", [])
    if posts:
        lines.append("### Posts\n")
        lines.append("| content_id | type | inputs | status | errors |")
        lines.append("|------------|------|--------|--------|--------|")
        for p in posts:
            inp_count = len(p.get("prepared_inputs", []))
            errs = "; ".join(p.get("errors", [])) or "—"
            lines.append(f"| {p.get('content_id','')} | {p.get('type','')} | {inp_count} | {p.get('status','')} | {errs} |")
        lines.append("")

    hl = manifest.get("highlight", {})
    hl_stories = hl.get("stories", [])
    if hl_stories:
        ok    = sum(1 for s in hl_stories if s.get("status") == "OK")
        fail  = sum(1 for s in hl_stories if s.get("status") == "FAIL")
        skip  = sum(1 for s in hl_stories if s.get("status") == "SKIP")
        total = len(hl_stories)
        lines.append(f"### Highlight Stories ({total} total)\n")
        lines.append(f"- OK: {ok} | FAIL: {fail} | SKIP: {skip}")
        lines.append("")
        fail_stories = [s for s in hl_stories if s.get("status") == "FAIL"]
        if fail_stories:
            lines.append("**Failed stories:**")
            for s in fail_stories:
                errs = "; ".join(s.get("errors", []))
                lines.append(f"- story #{s.get('story_number','')} ({s.get('story_id','')}): {errs}")
            lines.append("")

# ── 3. OpenAI plan summary ────────────────────────────────────────────────────
lines.append("## 3. OpenAI Plan Summary\n")
if pl_err:
    lines.append(f"> ERROR: {pl_err}\n")
else:
    summary = plan.get("summary", {})
    plan_status     = summary.get("plan_status", "?")
    can_run         = summary.get("can_run_stage4b", False)
    total_requests  = summary.get("estimated_openai_requests", "?")
    total_images    = summary.get("total_images_planned", "?")
    max_img_req     = summary.get("max_images_in_one_request", "?")
    max_payload     = summary.get("max_payload_size_mb", "?")
    plan_errors     = summary.get("errors", [])

    lines.append(f"**plan_status:** `{plan_status}`  ")
    lines.append(f"**can_run_stage4b:** `{can_run}`\n")
    lines.append(f"| Metric | Value | Limit |")
    lines.append(f"|--------|-------|-------|")
    lines.append(f"| posts requests | {summary.get('posts_requests','?')} | — |")
    lines.append(f"| highlight batch requests | {summary.get('highlight_batch_requests','?')} | — |")
    lines.append(f"| synthesis requests | {summary.get('synthesis_requests','?')} | — |")
    lines.append(f"| estimated total requests | {total_requests} | 15 |")
    lines.append(f"| total images planned | {total_images} | 120 |")
    lines.append(f"| max images in one request | {max_img_req} | 10 |")
    lines.append(f"| max payload size (MB) | {max_payload} | 20 |")
    lines.append("")

    if plan_errors:
        lines.append("**Plan errors:**")
        for e in plan_errors:
            lines.append(f"- {e}")
        lines.append("")

    posts_plan = plan.get("posts_plan", [])
    if posts_plan:
        lines.append("### Posts Requests\n")
        lines.append("| request_id | type | images | payload (bytes) | status |")
        lines.append("|------------|------|--------|-----------------|--------|")
        for p in posts_plan:
            lines.append(
                f"| {p.get('request_id','')} | {p.get('type','')} | "
                f"{p.get('images_count',0)} | {p.get('estimated_payload_size_bytes',0)} | "
                f"{p.get('status','')} |"
            )
        lines.append("")

    batches_plan = plan.get("highlight_batches_plan", [])
    if batches_plan:
        lines.append("### Highlight Batch Requests\n")
        lines.append("| request_id | stories | images | payload (bytes) | status |")
        lines.append("|------------|---------|--------|-----------------|--------|")
        for b in batches_plan:
            lines.append(
                f"| {b.get('request_id','')} | {len(b.get('story_ids',[]))} | "
                f"{b.get('images_count',0)} | {b.get('estimated_payload_size_bytes',0)} | "
                f"{b.get('status','')} |"
            )
        lines.append("")

    synth = plan.get("synthesis_plan", {})
    lines.append(f"### Synthesis Request\n")
    lines.append(f"- request_id: `{synth.get('request_id','')}`")
    lines.append(f"- uses_images: `{synth.get('uses_images','')}`")
    lines.append(f"- uses_batch_outputs_only: `{synth.get('uses_batch_outputs_only','')}`")
    lines.append(f"- status: `{synth.get('status','')}`")
    lines.append("")

# ── 4. Next steps ─────────────────────────────────────────────────────────────
lines.append("## 4. Next Steps\n")
if plan and plan.get("summary", {}).get("can_run_stage4b"):
    lines.append("Stage 4A is complete. Stage 4B (full OpenAI analysis) can proceed.")
    lines.append("")
    lines.append("Before running Stage 4B:")
    lines.append("- Confirm `openai_call_allowed` is set to `true` in the plan or Stage 4B script")
    lines.append("- Ensure `.env` contains a valid `OPENAI_API_KEY`")
    lines.append("- Run: `python scripts/stage4b_run_local.py`")
else:
    lines.append("Stage 4A has errors. Fix the issues listed above before proceeding to Stage 4B.")

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"report saved: {REPORT_PATH.relative_to(BASE)}")
if plan:
    summary = plan.get("summary", {})
    print(f"plan_status:     {summary.get('plan_status','?')}")
    print(f"can_run_stage4b: {summary.get('can_run_stage4b','?')}")
