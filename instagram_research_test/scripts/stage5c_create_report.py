#!/usr/bin/env python3
"""
Stage 5C: Create competitor analysis report from normalized outputs.

Reads:
  data/normalized/stage5c_stories_analysis.json
  data/normalized/stage5c_highlights_summary.json

Writes:
  report/stage_5c_analysis_report.md

IMPORTANT: report is runtime output — do not commit without explicit user request.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

BASE       = Path(__file__).parent.parent
NORM_DIR   = BASE / "data/normalized"
REPORT_DIR = BASE / "report"

ANALYSIS_PATH  = NORM_DIR / "stage5c_stories_analysis.json"
HL_SUMMARY_PATH = NORM_DIR / "stage5c_highlights_summary.json"
REPORT_PATH    = REPORT_DIR / "stage_5c_analysis_report.md"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] {path.relative_to(BASE)} not found", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(num: int, denom: int) -> str:
    if not denom:
        return "—"
    return f"{num/denom*100:.0f}%"


def build_report(analysis: dict, hl_data: dict) -> str:
    lines = []
    a = lines.append

    results    = analysis.get("results", [])
    highlights = hl_data.get("highlights", [])

    analyzed_results = [r for r in results if r.get("status") == "analyzed"]
    skipped_results  = [r for r in results if r.get("status") == "skipped"]
    error_results    = [r for r in results if r.get("status") == "error"]
    cached_results   = [r for r in results if r.get("from_cache")]

    a("# Stage 5C — Competitor Content Analysis Report")
    a("")
    a("## Run metadata")
    a("")

    if analyzed_results:
        r0 = analyzed_results[0]
        a(f"- model: `{r0.get('model', '—')}`")
        a(f"- detail: `{r0.get('detail', '—')}`")
        a(f"- prompt_version: `{r0.get('prompt_version', '—')}`")
    a(f"- stories total in output: {len(results)}")
    a(f"- stories analyzed: {len(analyzed_results)}")
    a(f"- stories from cache: {len(cached_results)}")
    a(f"- stories skipped (url unavailable): {len(skipped_results)}")
    a(f"- stories errored: {len(error_results)}")
    a("")

    a("## Что НЕ сделал")
    a("")
    a("- не запускал Apify")
    a("- не скачивал media файлы")
    a("- не менял actors_registry.json")
    a("- не заполнял XLSX")
    a("")

    # -----------------------------------------------------------------------
    # Per-highlight summary table
    # -----------------------------------------------------------------------
    a("## По highlights")
    a("")
    if highlights:
        a("| pos | highlight_id | canonical_title | analyzed | dominant content | dominant role | CTA rate | text rate |")
        a("|---|---|---|---|---|---|---|---|")
        for h in sorted(highlights, key=lambda x: (x.get("position") is None, x.get("position") or 9999)):
            pos   = h.get("position") or "—"
            hid   = h.get("highlight_id") or "—"
            title = str(h.get("canonical_title") or "—")[:35]
            n_a   = h.get("stories_analyzed", 0)
            n_t   = h.get("stories_total", 0)
            dctype = h.get("dominant_content_type") or "—"
            drole  = h.get("dominant_commercial_role") or "—"
            cta_r  = f"{h.get('cta_rate', 0)*100:.0f}%"
            txt_r  = f"{h.get('has_visible_text_rate', 0)*100:.0f}%"
            a(f"| {pos} | {hid} | {title} | {n_a}/{n_t} | {dctype} | {drole} | {cta_r} | {txt_r} |")
    else:
        a("No highlights processed.")
    a("")

    # -----------------------------------------------------------------------
    # Content type distribution (cross-highlight)
    # -----------------------------------------------------------------------
    a("## Распределение content_type (все highlights)")
    a("")
    ctype_counter: Counter = Counter()
    for r in analyzed_results:
        ct = (r.get("analysis") or {}).get("content_type")
        if ct:
            ctype_counter[ct] += 1

    if ctype_counter:
        total_a = len(analyzed_results)
        a("| content_type | count | % |")
        a("|---|---|---|")
        for ct, cnt in ctype_counter.most_common():
            a(f"| {ct} | {cnt} | {_pct(cnt, total_a)} |")
    else:
        a("No data.")
    a("")

    # -----------------------------------------------------------------------
    # Commercial role distribution
    # -----------------------------------------------------------------------
    a("## Распределение commercial_role (все highlights)")
    a("")
    crole_counter: Counter = Counter()
    for r in analyzed_results:
        cr = (r.get("analysis") or {}).get("commercial_role")
        if cr:
            crole_counter[cr] += 1

    if crole_counter:
        total_a = len(analyzed_results)
        a("| commercial_role | count | % |")
        a("|---|---|---|")
        for cr, cnt in crole_counter.most_common():
            a(f"| {cr} | {cnt} | {_pct(cnt, total_a)} |")
    else:
        a("No data.")
    a("")

    # -----------------------------------------------------------------------
    # Per-highlight detail: content type breakdown
    # -----------------------------------------------------------------------
    a("## Детально по highlights")
    a("")
    for h in sorted(highlights, key=lambda x: (x.get("position") is None, x.get("position") or 9999)):
        hid   = h.get("highlight_id") or "?"
        title = h.get("canonical_title") or hid
        a(f"### [{h.get('position', '?')}] {title}  `{hid}`")
        a("")
        a(f"- stories_total: {h.get('stories_total', '—')}")
        a(f"- stories_analyzed: {h.get('stories_analyzed', '—')}")
        a(f"- stories_skipped: {h.get('stories_skipped', '—')}")
        a(f"- dominant_content_type: **{h.get('dominant_content_type', '—')}**")
        a(f"- dominant_commercial_role: **{h.get('dominant_commercial_role', '—')}**")
        a(f"- cta_rate: {h.get('cta_rate', 0)*100:.0f}%")
        a(f"- has_visible_text_rate: {h.get('has_visible_text_rate', 0)*100:.0f}%")

        ctype_d = h.get("content_type_distribution") or {}
        if ctype_d:
            a("")
            a("  **Content types:**")
            for k, v in sorted(ctype_d.items(), key=lambda x: -x[1]):
                a(f"  - {k}: {v}")

        crole_d = h.get("commercial_role_distribution") or {}
        if crole_d:
            a("")
            a("  **Commercial roles:**")
            for k, v in sorted(crole_d.items(), key=lambda x: -x[1]):
                a(f"  - {k}: {v}")

        tags = h.get("common_tags") or []
        if tags:
            a("")
            a(f"  **Common tags:** {', '.join(tags)}")

        ctas = h.get("extracted_ctas") or []
        if ctas:
            a("")
            a("  **Detected CTAs:**")
            for cta in ctas:
                a(f"  - {cta}")

        a("")

    # -----------------------------------------------------------------------
    # CTA inventory
    # -----------------------------------------------------------------------
    all_ctas = [
        (r.get("analysis") or {}).get("cta_text")
        for r in analyzed_results
        if (r.get("analysis") or {}).get("has_cta")
    ]
    all_ctas = [c for c in all_ctas if c]
    if all_ctas:
        a("## Все обнаруженные CTA")
        a("")
        cta_counts: Counter = Counter(all_ctas)
        for cta, cnt in cta_counts.most_common():
            a(f"- {cta}  ×{cnt}" if cnt > 1 else f"- {cta}")
        a("")

    # -----------------------------------------------------------------------
    # Skipped stories
    # -----------------------------------------------------------------------
    if skipped_results:
        a("## Пропущенные stories (недоступные URL)")
        a("")
        skip_reasons: Counter = Counter(
            r.get("skip_reason", "unknown") for r in skipped_results
        )
        for reason, cnt in skip_reasons.most_common():
            a(f"- {reason}: {cnt} stories")
        a("")
        a("Возможная причина: Instagram CDN URL истёк (TTL ~24–48ч).")
        a("Решение: повторить Stage 5B-auto, затем Stage 5C.")
        a("")

    # -----------------------------------------------------------------------
    # Skipped highlight_ids by highlight
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Output files
    # -----------------------------------------------------------------------
    a("## Output files")
    a("")
    a("```")
    a("data/raw/stage5c_cache/                          ← per-story cache (not committed)")
    a("data/normalized/stage5c_stories_analysis.json    ← all story results (not committed)")
    a("data/normalized/stage5c_highlights_summary.json  ← per-highlight aggregate (not committed)")
    a("report/stage_5c_analysis_report.md               ← this report (not committed)")
    a("```")
    a("")

    # -----------------------------------------------------------------------
    # Recommendation
    # -----------------------------------------------------------------------
    a("## Recommendation")
    a("")
    if not highlights:
        a("→ No data. Run Stage 5C first.")
    else:
        total_stories = sum(h.get("stories_total", 0) for h in highlights)
        total_analyzed_hl = sum(h.get("stories_analyzed", 0) for h in highlights)
        if total_analyzed_hl < total_stories:
            a(f"→ Analyzed {total_analyzed_hl} of {total_stories} total stories.")
            a("  Increase --max-stories-per-highlight or run for remaining highlights.")
        else:
            a(f"→ All {total_stories} stories analyzed.")
        a("→ Stage 5D (XLSX): use stage5c_highlights_summary.json for competitive table.")
    a("")

    return "\n".join(lines)


def main() -> None:
    analysis = load(ANALYSIS_PATH)
    hl_data  = load(HL_SUMMARY_PATH)

    if not analysis and not hl_data:
        print(
            "[ERROR] No Stage 5C outputs found — run stage5c_run_local.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    report_text = build_report(analysis, hl_data)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {REPORT_PATH.relative_to(BASE)}")
    print("NOTE: report is a runtime output — do not commit without explicit user request.")


if __name__ == "__main__":
    main()
