"""CLI runner for Stage 5D coverage mapper."""

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))
from stage5d_coverage_mapper import (
    EXPECTED_TOTAL_COLUMNS, ACCOUNT,
    FIELD_DEFINITIONS, SOURCE_FILE_MAP,
    STATUS_READY, STATUS_PARTIAL, STATUS_MISSING,
    load_sources, source_presence, run_coverage_map,
)

SHEET_DISPLAY = [
    ("Описание профиля",   "profile_description",   11, "competitor"),
    ("Анализ хайлайтс",    "highlights_analysis",    8, "highlight"),
    ("Закрепленные посты", "pinned_posts",           11, "pinned_post"),
    ("Воронка",            "funnel",                 19, "funnel"),
    ("Лендинг",            "landing",                13, "landing"),
    ("Бот  лид-магнит",    "bot_lead_magnet",        17, "bot_or_lead_magnet"),
]

OUT_COVERAGE_MAP     = BASE / "data/normalized/stage5d_coverage_map.json"
OUT_COVERAGE_SUMMARY = BASE / "data/normalized/stage5d_coverage_summary.json"
OUT_REPORT           = BASE / "report/stage_5d_coverage_report.md"


def _count_statuses(records, key):
    r = sum(1 for x in records if x[key] == STATUS_READY)
    p = sum(1 for x in records if x[key] == STATUS_PARTIAL)
    m = sum(1 for x in records if x[key] == STATUS_MISSING)
    return r, p, m


def dry_run():
    print("=== Stage 5D Coverage Mapper ===")
    print("Mode: DRY RUN")
    print(f"Total Excel columns: {EXPECTED_TOTAL_COLUMNS}")
    print()
    print("Sheets:")
    total = 0
    for name, sid, ncols, grain in SHEET_DISPLAY:
        print(f"  {name:<28} {ncols:>2} columns  row_grain={grain}")
        total += ncols
    print(f"  {'─' * 41}")
    print(f"  {'Total':<28} {total:>2} columns")
    print()

    presence = source_presence()
    print("Source file presence:")
    for key, path in SOURCE_FILE_MAP.items():
        status = "EXISTS" if path.exists() else "missing"
        print(f"  [{status:6}]  {path.name}")
    print()

    print("Planned outputs (not written in dry-run):")
    print(f"  data/normalized/stage5d_coverage_map.json")
    print(f"  data/normalized/stage5d_coverage_summary.json")
    print(f"  report/stage_5d_coverage_report.md")
    print()

    print("No external API calls. No Excel modification.")
    sys.exit(0)


def real_run():
    sources = load_sources()
    coverage_map, sheet_summaries, meta = run_coverage_map(sources)

    OUT_COVERAGE_MAP.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUT_COVERAGE_MAP, "w", encoding="utf-8") as f:
        json.dump(coverage_map, f, ensure_ascii=False, indent=2)

    summary_data = {
        "meta": meta,
        "sheet_summaries": sheet_summaries,
    }
    with open(OUT_COVERAGE_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, ensure_ascii=False, indent=2)

    from stage5d_create_report import create_report
    create_report(coverage_map, sheet_summaries, meta, OUT_REPORT)

    r_cur, p_cur, m_cur = _count_statuses(coverage_map, "status_current_data")
    r_pip, p_pip, m_pip = _count_statuses(coverage_map, "status_pipeline_capability")

    print(f"Coverage map: {len(coverage_map)} fields")
    print(f"Current data:   ready={r_cur}  partial={p_cur}  missing={m_cur}")
    print(f"Pipeline cap:   ready={r_pip}  partial={p_pip}  missing={m_pip}")
    print(f"Output: data/normalized/stage5d_coverage_map.json")
    print(f"Output: data/normalized/stage5d_coverage_summary.json")
    print(f"Output: report/stage_5d_coverage_report.md")
    print(f"NOTE: These are runtime outputs. Do NOT commit them.")


def main():
    if "--dry-run" in sys.argv:
        dry_run()
    else:
        real_run()


if __name__ == "__main__":
    main()
