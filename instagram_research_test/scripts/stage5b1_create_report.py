#!/usr/bin/env python3
"""
Stage 5B-1: Create Markdown report from normalized JSON outputs.

Читает:
  data/normalized/highlights_index.json
  data/normalized/stage5b1_highlights_index_summary.json

Пишет:
  report/stage_5b1_highlights_index_report.md

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

NORM_DIR     = BASE / "data" / ACCOUNT / "normalized"
INDEX_PATH   = NORM_DIR / "highlights_index.json"
SUMMARY_PATH = NORM_DIR / "stage5b1_highlights_index_summary.json"
REPORT_PATH  = REPORT_DIR / "stage_5b1_highlights_index_report.md"


def load(path: Path) -> dict:
    if not path.exists():
        print(f"[WARN] {path.relative_to(BASE)} not found", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def val(field) -> str:
    if not isinstance(field, dict):
        return str(field) if field is not None else "—"
    v = field.get("value")
    if v is None:
        return f"—  [{field.get('data_status', '')}]"
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v)


def build_report(idx: dict, sm: dict) -> str:
    lines = []
    a = lines.append

    a("# Stage 5B-1 — Highlights Index Report")
    a("")
    a("## Scope")
    a("")
    a("Что сделал:")
    a(f"- прочитал actor registry (`config/actors_registry.json`)")
    a(f"- запустил `{sm.get('actor', 'singhera07/instagram-scraper')}` highlights index actor")
    a(f"- собрал список highlights")
    a(f"- создал `data/normalized/highlights_index.json`")
    a("")
    a("Что НЕ сделал:")
    a("- не собирал stories по highlights")
    a("- не скачивал media")
    a("- не запускал OpenAI")
    a("- не анализировал содержание highlights")
    a("- не заполнял XLSX")
    a("")
    a("## Run metadata")
    a("")
    a(f"- account: `{sm.get('account', '—')}`")
    a(f"- actor: `{sm.get('actor', '—')}`")
    a(f"- run_timestamp: `{sm.get('run_timestamp', '—')}`")
    a(f"- planned_apify_calls: {sm.get('planned_apify_calls', '—')}")
    a(f"- actual_apify_calls: {sm.get('actual_apify_calls', '—')}")
    run_ids = sm.get('apify_run_ids', [])
    a(f"- apify_run_ids: {run_ids if run_ids else '[]'}")
    a(f"- requested_limit: {sm.get('requested_limit', '—')}")
    a(f"- returned_highlights_count: {sm.get('returned_highlights_count', '—')}")
    a(f"- unique_highlights_count: {sm.get('unique_highlights_count', '—')}")
    a(f"- duplicates_count: {sm.get('duplicates_count', '—')}")
    a(f"- raw_shape: `{sm.get('raw_shape', '—')}`")
    a(f"- extraction_path: `{sm.get('extraction_path', '—')}`")
    a(f"- limit_behavior: **{sm.get('limit_behavior', '—')}**")
    a("")

    # Highlights table
    a("## Highlights index")
    a("")
    highlights = idx.get("highlights", [])
    if highlights:
        a("| # | highlight_id | title | owner_username | cover |")
        a("|---|---|---|---|---|")
        for h in highlights:
            pos   = h.get("position", "?")
            hid   = val(h.get("highlight_id"))
            title = val(h.get("title"))
            owner = val(h.get("owner_username"))
            cover = "yes" if h.get("cover_image_url", {}).get("data_status") == "ok" else "no"
            # truncate long values
            title = title[:60] + "…" if len(title) > 60 else title
            a(f"| {pos} | {hid} | {title} | {owner} | {cover} |")
    else:
        a("No highlights collected.")
    a("")

    # Limit behavior section
    a("## Limit behavior")
    a("")
    req_limit   = sm.get("requested_limit", "?")
    ret_count   = sm.get("returned_highlights_count", "?")
    prev_count  = sm.get("user_reported_previous_count", {})
    prev_val    = prev_count.get("value", 32) if isinstance(prev_count, dict) else 32
    prev_src    = prev_count.get("source", "") if isinstance(prev_count, dict) else ""
    limit_beh   = sm.get("limit_behavior", "unclear")

    a(f"- requested_limit = {req_limit}")
    a(f"- returned_highlights_count = {ret_count}")
    a(f"- user_reported_previous_count = {prev_val}  *(source: {prev_src})*")
    a("")
    if limit_beh == "likely_limited":
        a(f"**Вывод: likely_limited** — actor вернул ровно {ret_count} highlights "
          f"при limit={req_limit}, тогда как ранее сообщалось о {prev_val}. "
          f"Возможно, параметр `limit` ограничивает вывод. "
          f"Рекомендуется протестировать больший limit после явного подтверждения пользователя.")
    elif limit_beh == "likely_not_limited":
        a(f"**Вывод: likely_not_limited** — actor вернул {ret_count} highlights "
          f"при limit={req_limit}, что больше запрошенного лимита. "
          f"Параметр `limit` не ограничивает вывод. Текущий payload подходит для production.")
    else:
        a(f"**Вывод: unclear** — невозможно однозначно определить поведение limit. "
          f"Проверить вручную или сравнить с no-limit запуском.")
    a("")

    # Quality checks
    a("## Quality checks")
    a("")
    a(f"- highlights_with_id: {sm.get('highlights_with_id', '—')}")
    a(f"- highlights_with_title: {sm.get('highlights_with_title', '—')}")
    a(f"- highlights_with_cover: {sm.get('highlights_with_cover', '—')}")
    a(f"- highlights_with_owner_username: {sm.get('highlights_with_owner_username', '—')}")
    a(f"- duplicates_count: {sm.get('duplicates_count', '—')}")
    a("")
    warnings = sm.get("warnings", [])
    if warnings:
        a("**Warnings:**")
        for w in warnings:
            a(f"- {w}")
    else:
        a("No warnings.")
    extr_errors = sm.get("extraction_errors", [])
    if extr_errors:
        a("")
        a("**Extraction errors:**")
        for e in extr_errors:
            a(f"- {e}")
    a("")

    # Output files
    a("## Output files")
    a("")
    a("```")
    a("data/raw/stage5b1_highlights_index_raw.json          ← raw actor output (not committed)")
    a("data/normalized/highlights_index.json                 ← normalized highlights list (not committed)")
    a("data/normalized/stage5b1_highlights_index_summary.json ← run summary (not committed)")
    a("report/stage_5b1_highlights_index_report.md           ← this report (not committed)")
    a("```")
    a("")

    # Final verdict
    a("## Final verdict")
    a("")
    status         = sm.get("status", "FAIL")
    can_stage5b2   = sm.get("can_run_stage5b2", False)
    blockers       = sm.get("blockers", [])

    if status == "OK":
        verdict = "**OK** — все highlights собраны с id и title."
    elif status == "PARTIAL":
        verdict = "**PARTIAL** — highlights собраны, некоторые поля отсутствуют (не блокирует Stage 5B-2)."
    else:
        verdict = "**FAIL** — actor не вернул highlights или ошибка извлечения."

    a(verdict)
    a(f"- status: {status}")
    a(f"- can_run_stage5b2: {can_stage5b2}")

    if blockers:
        a("")
        a("Blockers:")
        for b in blockers:
            a(f"- {b}")
    a("")

    # Recommendation
    a("## Recommendation")
    a("")
    rec = sm.get("next_recommendation", "")
    if rec:
        a(rec)
    a("")
    if can_stage5b2:
        a("→ Stage 5B-2 можно запускать: использовать `highlight_id` из `highlights_index.json`.")
    else:
        a("→ Stage 5B-2 заблокирован — исправить ошибки выше перед продолжением.")
    if limit_beh == "likely_limited":
        a("→ Перед production: подтвердить у пользователя тест с большим limit.")
    a("")

    return "\n".join(lines)


def main():
    idx = load(INDEX_PATH)
    sm  = load(SUMMARY_PATH)

    if not sm:
        print("[ERROR] stage5b1_highlights_index_summary.json not found — run collect script first.",
              file=sys.stderr)
        sys.exit(1)

    report_text = build_report(idx, sm)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {REPORT_PATH.relative_to(BASE)}")
    print("NOTE: report is a runtime output — do not commit without explicit user request.")


if __name__ == "__main__":
    main()
