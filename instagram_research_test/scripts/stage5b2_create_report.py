#!/usr/bin/env python3
"""
Stage 5B-2: Create Markdown report from normalized JSON outputs.

Читает:
  data/normalized/stage5b2_highlights_stories_summary.json
  data/normalized/stage5b2_stories_index.json

Пишет:
  report/stage_5b2_highlights_stories_report.md

ВАЖНО: report — runtime output. Не коммитить без явного запроса пользователя.
"""

import argparse
import json
import sys
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

BASE       = Path(__file__).parent.parent
REPORT_DIR = BASE / "report"

_ap = argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT = _args.account

NORM_DIR         = BASE / "data" / ACCOUNT / "normalized"
SUMMARY_PATH     = NORM_DIR / "stage5b2_highlights_stories_summary.json"
STORIES_IDX_PATH = NORM_DIR / "stage5b2_stories_index.json"
REPORT_PATH      = REPORT_DIR / "stage_5b2_highlights_stories_report.md"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] {path.relative_to(BASE)} not found", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(sm: dict, si: dict) -> str:
    lines = []
    a = lines.append

    a("# Stage 5B-2 — Highlight Stories Report")
    a("")
    a("## Scope")
    a("")
    a("Что сделал:")
    a("- прочитал highlight IDs из `data/normalized/highlights_index.json`")
    a(f"- вызвал `{sm.get('actor', ACTOR_ID := 'igview-owner/instagram-highlights-stories-viewer')}` для каждого валидного ID")
    a("- собрал stories по каждому highlight")
    a("- создал normalized summary и stories index")
    a("")
    a("Что НЕ сделал:")
    a("- не анализировал содержимое stories")
    a("- не скачивал media")
    a("- не запускал OpenAI")
    a("- не заполнял XLSX")
    a("")
    a("## Run metadata")
    a("")
    a(f"- account: `{sm.get('account', '—')}`")
    a(f"- actor: `{sm.get('actor', '—')}`")
    a(f"- run_timestamp: `{sm.get('run_timestamp', '—')}`")
    a(f"- planned_apify_calls: {sm.get('planned_apify_calls', '—')}")
    a(f"- actual_apify_calls: {sm.get('actual_apify_calls', '—')}")
    run_ids = sm.get("apify_run_ids", [])
    a(f"- apify_run_ids: {run_ids if run_ids else '[]'}")
    a("")
    a("## Collection stats")
    a("")
    a(f"- highlights_total: {sm.get('highlights_total', '—')}")
    a(f"- highlights_processed: {sm.get('highlights_processed', '—')}")
    a(f"- highlights_ok: {sm.get('highlights_ok', '—')}")
    a(f"- highlights_empty: {sm.get('highlights_empty', '—')}")
    a(f"- highlights_fail: {sm.get('highlights_fail', '—')}")
    a(f"- highlights_invalid: {sm.get('highlights_invalid', '—')}")
    a(f"- highlights_skipped: {sm.get('highlights_skipped', '—')}")
    a(f"- total_stories_count: {sm.get('total_stories_count', '—')}")
    a(f"- highlights_with_media: {sm.get('highlights_with_media', '—')}")
    a(f"- can_analyze_highlights: **{sm.get('can_analyze_highlights', False)}**")
    a("")

    # Per-highlight table
    a("## Per-highlight results")
    a("")
    highlights = si.get("highlights", [])
    if highlights:
        a("| # | highlight_id | title | status | stories | imageUrl | videoUrl |")
        a("|---|---|---|---|---|---|---|")
        for h in highlights:
            pos   = h.get("position", "?")
            hid   = h.get("highlight_id") or "—"
            title = str(h.get("title") or "—")[:50]
            status = h.get("status", "—")
            count = h.get("stories_count", 0)
            img   = "yes" if h.get("has_imageUrl") else "no"
            vid   = "yes" if h.get("has_videoUrl") else "no"
            a(f"| {pos} | {hid} | {title} | {status} | {count} | {img} | {vid} |")
    else:
        a("No highlights processed.")
    a("")

    # Warnings and blockers
    warnings = sm.get("warnings", [])
    blockers = sm.get("blockers", [])
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

    # Output files
    a("## Output files")
    a("")
    a("```")
    a("data/raw/stage5b2_stories_{id}_raw.json       ← raw per highlight (not committed)")
    a("data/normalized/stage5b2_highlights_stories_summary.json ← run summary (not committed)")
    a("data/normalized/stage5b2_stories_index.json              ← lightweight index (not committed)")
    a("report/stage_5b2_highlights_stories_report.md            ← this report (not committed)")
    a("```")
    a("")

    # Final verdict
    a("## Final verdict")
    a("")
    ok     = sm.get("highlights_ok", 0)
    total  = sm.get("highlights_processed", 0)
    can    = sm.get("can_analyze_highlights", False)

    if can and ok == total:
        verdict = f"**OK** — все {ok} highlights вернули stories."
    elif can:
        verdict = f"**PARTIAL** — {ok} из {total} highlights вернули stories."
    else:
        verdict = "**FAIL** — нет highlights со stories. Stage 5C заблокирован."

    a(verdict)
    a(f"- can_analyze_highlights: {can}")
    a("")

    a("## Recommendation")
    a("")
    if can:
        a("→ Stage 5C (анализ highlights через OpenAI Vision) можно запускать.")
        a(f"  Использовать `data/normalized/stage5b2_stories_index.json` для списка highlights.")
        a(f"  Raw stories в `data/raw/stage5b2_stories_{{id}}_raw.json`.")
    else:
        a("→ Stage 5C заблокирован — исправить ошибки выше перед продолжением.")
    a("")

    return "\n".join(lines)


def main():
    sm = load(SUMMARY_PATH)
    si = load(STORIES_IDX_PATH)

    if not sm:
        print("[ERROR] stage5b2_highlights_stories_summary.json not found — run collect first.",
              file=sys.stderr)
        sys.exit(1)

    report_text = build_report(sm, si)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {REPORT_PATH.relative_to(BASE)}")
    print("NOTE: report is a runtime output — do not commit without explicit user request.")


if __name__ == "__main__":
    main()
