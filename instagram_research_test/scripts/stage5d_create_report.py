"""Generates the Stage 5D coverage report markdown from coverage map data."""

import json
import sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).parent.parent

STATUS_READY   = "ready"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"


def _pct(n, total):
    if total == 0:
        return "0%"
    return f"{round(100 * n / total)}%"


def _status_table(records, key, total):
    r = sum(1 for x in records if x[key] == STATUS_READY)
    p = sum(1 for x in records if x[key] == STATUS_PARTIAL)
    m = sum(1 for x in records if x[key] == STATUS_MISSING)
    rp = r + p
    lines = [
        "| Status | Count | % |",
        "|---|---|---|",
        f"| ready | {r} | {_pct(r, total)} |",
        f"| partial | {p} | {_pct(p, total)} |",
        f"| missing | {m} | {_pct(m, total)} |",
        f"| **ready + partial** | **{rp}** | **{_pct(rp, total)}** |",
    ]
    return "\n".join(lines)


def create_report(coverage_map, sheet_summaries, meta, out_path):
    """Write the coverage report markdown to out_path."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(coverage_map)
    timestamp = meta.get("run_timestamp", "unknown")
    account = meta.get("account", "unknown")

    lines = []

    lines.append("# Stage 5D Coverage Report")
    lines.append("")
    lines.append(f"Generated: {timestamp}")
    lines.append(f"Account: {account}")
    lines.append("")

    # Section 1: Total coverage summary
    lines.append("## 1. Total Coverage Summary")
    lines.append("")
    lines.append(f"**Excel columns: {total}** across 6 sheets.")
    lines.append("")

    lines.append("### Current data coverage (what can be filled RIGHT NOW from existing local outputs):")
    lines.append(_status_table(coverage_map, "status_current_data", total))
    lines.append("")

    lines.append("### Pipeline capability coverage (what the built pipeline CAN fill after full run):")
    lines.append(_status_table(coverage_map, "status_pipeline_capability", total))
    lines.append("")

    # Section 2: Coverage by sheet
    lines.append("## 2. Coverage by Sheet")
    lines.append("")
    lines.append("| Sheet | Grain | Fields | Ready now | Partial now | Missing now | Rows now | Rows pipeline |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for ss in sheet_summaries:
        cd = ss["current_data"]
        lines.append(
            f"| {ss['sheet_name']} | {ss['row_grain']} | {ss['total_fields']} "
            f"| {cd['ready']} | {cd['partial']} | {cd['missing']} "
            f"| {ss['expected_rows_now']} | {ss['expected_rows_pipeline']} |"
        )
    lines.append("")

    # Section 3: Sheet row-grain summary
    lines.append("## 3. Sheet Row-Grain Summary")
    lines.append("")
    for ss in sheet_summaries:
        lines.append(f"### {ss['sheet_name']}")
        lines.append(f"- **Grain**: {ss['row_grain']}")
        lines.append(f"- **Can create rows now**: {ss['can_create_rows_now']}")
        lines.append(f"- **Expected rows now**: {ss['expected_rows_now']}")
        lines.append(f"- **Expected rows after full pipeline**: {ss['expected_rows_pipeline']}")
        lines.append(f"- **Notes**: {ss['notes']}")
        lines.append("")

    # Section 4: Fields ready now
    ready_fields = [r for r in coverage_map if r["status_current_data"] == STATUS_READY]
    lines.append("## 4. Fields Ready Now")
    lines.append("")
    if ready_fields:
        lines.append("| Sheet | Column | Source files | Confidence | Preview |")
        lines.append("|---|---|---|---|---|")
        for r in ready_fields:
            src = ", ".join(r.get("source_files") or []) or "—"
            conf = r.get("confidence") or "—"
            prev = str(r.get("preview") or "").replace("|", "\\|")[:80]
            lines.append(f"| {r['sheet_name']} | {r['column_name']} | {src} | {conf} | {prev} |")
    else:
        lines.append("_No fields are ready with current data._")
    lines.append("")

    # Section 5: Fields partial now
    partial_fields = [r for r in coverage_map if r["status_current_data"] == STATUS_PARTIAL]
    lines.append("## 5. Fields Partial Now (with reasons)")
    lines.append("")
    if partial_fields:
        lines.append("| Sheet | Column | Source files | Confidence | Reason |")
        lines.append("|---|---|---|---|---|")
        for r in partial_fields:
            src = ", ".join(r.get("source_files") or []) or "—"
            conf = r.get("confidence") or "—"
            logic = str(r.get("source_logic") or r.get("blocker") or "").replace("|", "\\|")[:100]
            lines.append(f"| {r['sheet_name']} | {r['column_name']} | {src} | {conf} | {logic} |")
    else:
        lines.append("_No partial fields._")
    lines.append("")

    # Section 6: Missing fields grouped by next stage
    missing_fields = [r for r in coverage_map if r["status_current_data"] == STATUS_MISSING]
    lines.append("## 6. Fields Missing — Required Next Stage")
    lines.append("")

    by_stage = defaultdict(list)
    for r in missing_fields:
        ns = r.get("next_stage_needed") or "No stage defined / manual"
        by_stage[ns].append(r)

    for stage_name, fields in sorted(by_stage.items(), key=lambda x: -len(x[1])):
        lines.append(f"### {stage_name}")
        for r in fields:
            lines.append(f"- {r['sheet_name']} / {r['column_name']}")
        lines.append("")

    # Section 7: Top next steps by coverage impact
    lines.append("## 7. Top Next Steps by Coverage Impact")
    lines.append("")
    lines.append("Ordered by number of fields they unlock:")
    lines.append("")

    stage_counts = defaultdict(list)
    for r in coverage_map:
        if r["status_current_data"] in (STATUS_MISSING, STATUS_PARTIAL):
            ns = r.get("next_stage_needed")
            if ns:
                stage_counts[ns].append(r)

    sorted_stages = sorted(stage_counts.items(), key=lambda x: -len(x[1]))

    for i, (stage_name, fields) in enumerate(sorted_stages, 1):
        sheet_groups = defaultdict(list)
        for r in fields:
            sheet_groups[r["sheet_name"]].append(r["column_name"])
        sheet_notes = []
        for sn, cols in sheet_groups.items():
            sheet_notes.append(f"  - Sheet: {sn} ({len(cols)} columns)")
        sheet_str = "\n".join(sheet_notes)
        lines.append(f"{i}. **{stage_name}** — unlocks {len(fields)} fields")
        lines.append(sheet_str)
        lines.append("")

    # Section 8: Recommended next build step
    lines.append("## 8. Recommended Next Build Step")
    lines.append("")
    if sorted_stages:
        top_stage, top_fields = sorted_stages[0]
        sheet_groups = defaultdict(list)
        for r in top_fields:
            sheet_groups[r["sheet_name"]].append(r)
        sheet_list = ", ".join(sheet_groups.keys())
        lines.append(
            f"**Build: {top_stage}** — this stage unlocks the most fields ({len(top_fields)} fields "
            f"across: {sheet_list}). "
            f"After completing this stage, re-run `stage5d_run_local.py` to see updated coverage."
        )
        if len(sorted_stages) > 1:
            second_stage, second_fields = sorted_stages[1]
            lines.append(
                f" The second-highest impact stage is **{second_stage}** ({len(second_fields)} fields)."
            )
    else:
        lines.append("All fields have resolvers assigned. Review partial fields to determine manual fill priority.")
    lines.append("")

    # Section 9: Source file status
    lines.append("## 9. Source File Status")
    lines.append("")
    lines.append("| File | Status | Notes |")
    lines.append("|---|---|---|")
    source_presence = meta.get("source_presence", {})
    source_notes = {
        "profile_summary": "Instagram profile structural data",
        "bio_analysis": "AI-analyzed bio fields",
        "pinned_posts_index": "3 pinned posts structural index",
        "highlights_index": "32 highlights structural index",
        "stage5b_summary": "Stage 5B auto stories summary",
        "stage5b_index": "Stage 5B auto stories per-item index",
        "stage5c_highlights": "Stage 5C highlights analysis (3 of 32)",
        "stage5c_stories": "Stage 5C stories analysis",
    }
    for key, exists in source_presence.items():
        status = "EXISTS" if exists else "missing"
        note = source_notes.get(key, "")
        lines.append(f"| {key} | {status} | {note} |")
    lines.append("")

    report_text = "\n".join(lines)
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


def main():
    coverage_map_path = BASE / "data/normalized/stage5d_coverage_map.json"
    summary_path = BASE / "data/normalized/stage5d_coverage_summary.json"
    out_path = BASE / "report/stage_5d_coverage_report.md"

    if not coverage_map_path.exists():
        print(f"ERROR: {coverage_map_path} not found. Run stage5d_run_local.py first.")
        sys.exit(1)
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found. Run stage5d_run_local.py first.")
        sys.exit(1)

    with open(coverage_map_path, "r", encoding="utf-8") as f:
        coverage_map = json.load(f)
    with open(summary_path, "r", encoding="utf-8") as f:
        summary_data = json.load(f)

    sheet_summaries = summary_data.get("sheet_summaries", [])
    meta = summary_data.get("meta", {})

    result = create_report(coverage_map, sheet_summaries, meta, out_path)
    print(f"Report written to: {result}")


if __name__ == "__main__":
    main()
