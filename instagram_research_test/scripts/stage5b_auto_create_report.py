#!/usr/bin/env python3
"""
Stage 5B-auto: Create Markdown report from normalized outputs.

Reads:
  data/normalized/stage5b_auto_stories_summary.json
  data/normalized/stage5b_auto_stories_index.json

Writes:
  report/stage_5b_auto_stories_report.md

IMPORTANT: report is runtime output — do not commit without explicit user request.
"""

import json
import sys
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

BASE       = Path(__file__).parent.parent
NORM_DIR   = BASE / "data/normalized"
REPORT_DIR = BASE / "report"

SUMMARY_PATH      = NORM_DIR / "stage5b_auto_stories_summary.json"
STORIES_IDX_PATH  = NORM_DIR / "stage5b_auto_stories_index.json"
REPORT_PATH       = REPORT_DIR / "stage_5b_auto_stories_report.md"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] {path.relative_to(BASE)} not found", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(sm: dict, si: dict) -> str:
    lines = []
    a = lines.append

    a("# Stage 5B-auto — Highlight Stories Report")
    a("")
    a("## Scope")
    a("")
    a("Что сделал:")
    a(f"- вызвал `{sm.get('actor', 'automation-lab/instagram-stories-scraper')}` (1 call)")
    a("- разделил active stories и highlight stories")
    a("- сгруппировал highlight stories по `highlightId`")
    a("- присоединил canonical title/position/cover из `data/normalized/highlights_index.json`")
    a("")
    a("Что НЕ сделал:")
    a("- не использовал `igview-owner` (deprecated fallback)")
    a("- не анализировал содержимое stories")
    a("- не скачивал media")
    a("- не запускал OpenAI")
    a("- не заполнял XLSX")
    a("")

    a("## Run metadata")
    a("")
    a(f"- account: `{sm.get('account', '—')}`")
    a(f"- actor: `{sm.get('actor', '—')}`")
    a(f"- mode: `{sm.get('mode', 'collect')}`")
    a(f"- run_timestamp: `{sm.get('run_timestamp', '—')}`")
    a(f"- apify_run_id: `{sm.get('apify_run_id', '—')}`")
    a(f"- max_highlights_requested: {sm.get('max_highlights_requested', '—')}")
    a(f"- apify_calls: {'1  (single call)' if sm.get('mode') != 'normalize_only' else '0  (normalize-only, raw reused)'}")
    a("")

    a("## Collection stats")
    a("")
    a(f"- total_items_returned: {sm.get('total_items_returned', '—')}")
    a(f"- active_stories_count: {sm.get('active_stories_count', '—')}")
    a(f"- highlight_stories_count: {sm.get('highlight_stories_count', '—')}")
    a(f"- highlights_returned: {sm.get('highlights_returned', '—')}")
    a(f"- highlights_in_index: {sm.get('highlights_in_index', '—')}")
    a(f"- can_analyze_highlights: **{sm.get('can_analyze_highlights', False)}**")
    a("")

    ns = sm.get("normalization_stats", {})
    if ns:
        a("## Normalization stats")
        a("")
        a(f"- image_stories:    {ns.get('image_stories', '—')}")
        a(f"- video_stories:    {ns.get('video_stories', '—')}")
        a(f"- null_id_count:    {ns.get('null_id_count', '—')}")
        a(f"- null_media_count: {ns.get('null_media_count', '—')}")
        a("")

    a("## Active stories (profile, last 24h)")
    a("")
    active = si.get("active_stories", [])
    a(f"Count: {len(active)}")
    if active:
        a("")
        a("| # | id | mediaType | timestamp | imageUrl | videoUrl |")
        a("|---|---|---|---|---|---|")
        for i, s in enumerate(active, start=1):
            sid   = s.get("id") or "—"
            stype = s.get("mediaType") or "—"
            ts    = s.get("timestamp") or "—"
            img   = "yes" if s.get("imageUrl") else "no"
            vid   = "yes" if s.get("videoUrl") else "no"
            a(f"| {i} | {sid} | {stype} | {ts} | {img} | {vid} |")
    a("")

    a("## Highlight stories")
    a("")
    highlights = si.get("highlights", [])
    if highlights:
        a("| pos | highlight_id | canonical_title | auto_lab_title | stories | imageUrl | videoUrl |")
        a("|---|---|---|---|---|---|---|")
        for h in highlights:
            pos        = h.get("position") or "—"
            hid        = h.get("highlight_id") or "—"
            can_title  = str(h.get("canonical_title") or "—")[:40]
            auto_title = str(h.get("automation_lab_title") or "—")[:40]
            count      = h.get("stories_count", 0)
            stories    = h.get("stories", [])
            has_img    = "yes" if any(s.get("imageUrl") for s in stories) else "no"
            has_vid    = "yes" if any(s.get("videoUrl") for s in stories) else "no"
            a(f"| {pos} | {hid} | {can_title} | {auto_title} | {count} | {has_img} | {has_vid} |")
    else:
        a("No highlight stories returned.")
    a("")

    # Warnings
    warnings = sm.get("warnings", [])
    blockers  = sm.get("blockers", [])
    if warnings:
        a("## Warnings")
        a("")
        for w in warnings:
            a(f"- {w}")
        a("")
    if blockers:
        a("## Blockers")
        a("")
        for b in blockers:
            a(f"- {b}")
        a("")

    a("## Architecture note")
    a("")
    a("| Actor | Role |")
    a("|---|---|")
    a("| `singhera07/instagram-scraper` | canonical highlights index (id, title, position, cover) |")
    a("| `automation-lab/instagram-stories-scraper` | highlight stories content |")
    a("| `igview-owner/instagram-highlights-stories-viewer` | deprecated fallback — not used |")
    a("")
    a("highlightTitle from automation-lab is stored as `automation_lab_title` (raw).")
    a("Source of truth for title/order/cover is `highlights_index.json` from singhera07.")
    a("")

    a("## Output files")
    a("")
    a("```")
    a("data/raw/stage5b_auto_stories_raw.json              ← raw actor output (not committed)")
    a("data/normalized/stage5b_auto_stories_summary.json   ← run summary (not committed)")
    a("data/normalized/stage5b_auto_stories_index.json     ← grouped index (not committed)")
    a("report/stage_5b_auto_stories_report.md              ← this report (not committed)")
    a("```")
    a("")

    a("## Final verdict")
    a("")
    ok     = sm.get("highlights_returned", 0)
    can    = sm.get("can_analyze_highlights", False)
    total  = sm.get("highlights_in_index", 0)
    mxh    = sm.get("max_highlights_requested", "?")

    if can and ok >= min(int(mxh) if str(mxh).isdigit() else 0, total):
        verdict = f"**OK** — {ok} highlights вернули stories (maxHighlights={mxh})."
    elif can:
        verdict = f"**PARTIAL** — {ok} из {min(int(mxh) if str(mxh).isdigit() else total, total)} ожидаемых highlights вернули stories."
    else:
        verdict = "**FAIL** — нет highlights со stories. Stage 5C заблокирован."

    a(verdict)
    a(f"- can_analyze_highlights: {can}")
    a("")

    a("## Recommendation")
    a("")
    if can:
        a("→ Stage 5C (анализ highlights через OpenAI Vision) можно запускать.")
        a("  Использовать `data/normalized/stage5b_auto_stories_index.json`.")
        a("  Если нужны все highlights — повторить с `--max-highlights 32`.")
    else:
        a("→ Stage 5C заблокирован — исправить ошибки выше перед продолжением.")
    a("")

    return "\n".join(lines)


def main() -> None:
    sm = load(SUMMARY_PATH)
    si = load(STORIES_IDX_PATH)

    if not sm:
        print(
            "[ERROR] stage5b_auto_stories_summary.json not found — run collector first.",
            file=sys.stderr,
        )
        sys.exit(1)

    report_text = build_report(sm, si)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {REPORT_PATH.relative_to(BASE)}")
    print("NOTE: report is a runtime output — do not commit without explicit user request.")


if __name__ == "__main__":
    main()
