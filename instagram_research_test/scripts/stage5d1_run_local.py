"""Stage 5D-1 local runner: builds Google Sheets-ready CSV preview and payload."""

import argparse
import csv
import io
import json
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

sys.path.insert(0, str(Path(__file__).parent))
from stage5d1_prepare_sheet_rows import (
    ACCOUNT,
    SPREADSHEET_ID,
    START_ROW,
    FALLBACK_HEADERS,
    load_sources,
    source_presence,
    read_excel_headers,
    build_all_rows,
    validate_sheet_data,
    build_payload,
    build_v2_pinned_rows,
    build_v2_highlights_rows,
    build_v2_landing_rows,
    build_v2_profile_rows,
    build_reels_rows,
    build_posts_rows,
    _redact_url,
)


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

def _write_csv(path: Path, headers: list, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(path: Path, sheet_data: dict, meta: dict, warnings_all: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    ts         = meta.get("generated_at", "unknown")
    account    = meta.get("account", "unknown")
    header_src = meta.get("headers_source", "unknown")

    lines = []
    lines.append("# Stage 5D-1 Sheet Rows Preview Report")
    lines.append("")
    lines.append(f"Generated: {ts}")
    lines.append(f"Account: {account}")
    lines.append(f"Headers source: {header_src}")
    lines.append("")

    lines.append("## Row Counts per Sheet")
    lines.append("")
    lines.append("| Sheet | Columns | Rows |")
    lines.append("|---|---|---|")
    for sname, data in sheet_data.items():
        lines.append(f"| {sname} | {len(data['headers'])} | {len(data['rows'])} |")
    lines.append("")

    lines.append("## Source File Status")
    lines.append("")
    lines.append("| File | Status |")
    lines.append("|---|---|")
    for key, exists in meta.get("source_presence", {}).items():
        status = "EXISTS" if exists else "missing"
        lines.append(f"| {key} | {status} |")
    lines.append("")

    lines.append("## Warnings")
    lines.append("")
    if warnings_all:
        for w in warnings_all:
            lines.append(f"- {w}")
    else:
        lines.append("_No warnings._")
    lines.append("")

    for sname, data in sheet_data.items():
        lines.append(f"## {sname} — Preview (first 3 rows)")
        lines.append("")
        if not data["rows"]:
            lines.append("_No rows created._")
        else:
            hdrs = data["headers"]
            preview_rows = data["rows"][:3]
            lines.append("| " + " | ".join(hdrs) + " |")
            lines.append("|" + "|".join("---" for _ in hdrs) + "|")
            for row in preview_rows:
                safe = [str(c).replace("|", "\\|")[:60] for c in row]
                lines.append("| " + " | ".join(safe) + " |")
        if data["warnings"]:
            lines.append("")
            lines.append("**Warnings:**")
            for w in data["warnings"]:
                lines.append(f"- {w}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(sheet_data: dict, meta: dict, warnings_all: list) -> dict:
    sheets = {}
    for sname, data in sheet_data.items():
        sheets[sname] = {
            "column_count": len(data["headers"]),
            "row_count":    len(data["rows"]),
            "warnings":     data["warnings"],
        }
    return {
        "meta":         meta,
        "sheets":       sheets,
        "all_warnings": warnings_all,
    }


# ---------------------------------------------------------------------------
# Pinned rows preview
# ---------------------------------------------------------------------------

def _print_pinned_preview(headers: list, rows: list):
    """Print a per-row preview of the pinned posts with key semantic fields."""
    _PREVIEW_FIELDS = [
        ("Позиция закрепа", "Position"),
        ("Ссылка на пост",  "URL"),
        ("Тема поста",      "Topic"),
        ("Какой CTA",       "CTA"),
        ("Куда ведет CTA",  "CTA destination"),
        ("Роль в воронке",  "Funnel role"),
    ]
    idx = {h: i for i, h in enumerate(headers)}
    print("\n=== Закрепленные посты — preview (semantic fields) ===")
    for row_num, row in enumerate(rows, start=1):
        print(f"  --- Post {row_num} ---")
        for field, label in _PREVIEW_FIELDS:
            col = idx.get(field)
            val = str(row[col] or "").strip() if col is not None and col < len(row) else ""
            display = val[:80] if val else "(empty)"
            print(f"    {label:<18}: {display}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5D-1: build Google Sheets-ready CSV preview + payload"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Load sources, build rows, validate, then print summary without writing any files",
    )
    parser.add_argument(
        "--account", default="vlada_kliuiko",
        help="Instagram account to process",
    )
    parser.add_argument(
        "--require-pinned-semantic", action="store_true",
        help=(
            "Exit with error if neither stage5a2c_fixed_rows nor stage5a2c_rows "
            "is available as the pinned posts source"
        ),
    )
    args = parser.parse_args()

    dry_run          = args.dry_run
    require_semantic = args.require_pinned_semantic
    if dry_run:
        print("[DRY-RUN] No files will be written.\n")

    # 1. Load sources
    print("Loading source files...")
    sources  = load_sources()
    presence = source_presence()

    # Guard: --require-pinned-semantic
    if require_semantic:
        has_fixed = sources.get("stage5a2c_fixed_rows") is not None
        has_rows  = sources.get("stage5a2c_rows") is not None
        if not has_fixed and not has_rows:
            print(
                "[ERROR] Pinned semantic rows required but not found.\n"
                "  stage5a2c_pinned_posts_google_sheet_rows_fixed.json — absent\n"
                "  stage5a2c_pinned_posts_google_sheet_rows.json       — absent\n"
                "  Run Stage 5A-2C locally to generate these files first."
            )
            sys.exit(1)

    # 2. Get headers
    headers, warn = read_excel_headers()
    if warn:
        print(f"[WARNING] {warn}")
    if headers is None:
        headers = FALLBACK_HEADERS
        headers_source = "hardcoded_fallback"
    else:
        headers_source = "excel_template"

    # 3. Build rows
    print("Building sheet rows...")
    sheet_data = build_all_rows(sources, headers)

    # 4. Validate
    print("Validating...")
    try:
        validate_sheet_data(sheet_data, sources, headers)
        print("[OK] Validation passed.")
    except AssertionError as e:
        print(f"[ERROR] Validation failed: {e}")
        sys.exit(1)

    # 5. Collect warnings
    warnings_all = []
    for sname, data in sheet_data.items():
        for w in data["warnings"]:
            warnings_all.append(f"[{sname}] {w}")

    # 6. Build payload
    print("Building payload...")
    try:
        payload = build_payload(sheet_data)
    except ValueError as e:
        print(f"[ERROR] Payload build failed: {e}")
        sys.exit(1)

    # Build v2 pinned rows and inject into payload (errors are non-fatal)
    try:
        v2_headers, v2_rows, v2_warnings = build_v2_pinned_rows(sources)
        if v2_rows:
            clean_v2 = [
                [_redact_url(cell, payload_mode=True) for cell in row]
                for row in v2_rows
            ]
            payload["sheets"]["Закрепленные посты v2"] = {
                "headers": v2_headers,
                "rows":    clean_v2,
            }
            print(f"  v2 pinned rows: {len(v2_rows)} row(s) added to payload")
        else:
            print(f"  v2 pinned rows: skipped — {v2_warnings[0] if v2_warnings else 'no data'}")
        if v2_warnings:
            warnings_all.extend(f"[Закрепленные посты v2] {w}" for w in v2_warnings)
    except Exception as _v2_err:
        print(f"  [WARN] build_v2_pinned_rows failed (non-fatal): {_v2_err}")
        warnings_all.append(f"[Закрепленные посты v2] build failed: {_v2_err}")

    # Build v2 highlights rows and inject into payload (errors are non-fatal)
    try:
        v2h_headers, v2h_rows, v2h_warnings = build_v2_highlights_rows(sources)
        if v2h_rows:
            payload["sheets"]["Анализ хайлайтс v2"] = {
                "headers": v2h_headers,
                "rows":    v2h_rows,
            }
            print(f"  v2 highlights rows: {len(v2h_rows)} row(s) added to payload")
        else:
            print(f"  v2 highlights rows: skipped — {v2h_warnings[0] if v2h_warnings else 'no data'}")
        if v2h_warnings:
            warnings_all.extend(f"[Анализ хайлайтс v2] {w}" for w in v2h_warnings)
    except Exception as _v2h_err:
        print(f"  [WARN] build_v2_highlights_rows failed (non-fatal): {_v2h_err}")
        warnings_all.append(f"[Анализ хайлайтс v2] build failed: {_v2h_err}")

    # Build v2 profile rows and inject into payload (errors are non-fatal)
    try:
        v2p_headers, v2p_rows, v2p_warnings = build_v2_profile_rows(sources)
        if v2p_rows:
            payload["sheets"]["Описание профиля v2"] = {
                "headers": v2p_headers,
                "rows":    v2p_rows,
            }
            print(f"  v2 profile rows: {len(v2p_rows)} row(s) added to payload")
        else:
            print(f"  v2 profile rows: skipped — {v2p_warnings[0] if v2p_warnings else 'no data'}")
        if v2p_warnings:
            warnings_all.extend(f"[Описание профиля v2] {w}" for w in v2p_warnings)
    except Exception as _v2p_err:
        print(f"  [WARN] build_v2_profile_rows failed (non-fatal): {_v2p_err}")
        warnings_all.append(f"[Описание профиля v2] build failed: {_v2p_err}")

    # Build v2 landing rows and inject into payload (errors are non-fatal)
    try:
        v2l_headers, v2l_rows, v2l_warnings = build_v2_landing_rows(sources)
        if v2l_rows:
            payload["sheets"]["Лендинг v2"] = {
                "headers": v2l_headers,
                "rows":    v2l_rows,
            }
            print(f"  v2 landing rows: {len(v2l_rows)} row(s) added to payload")
        else:
            print(f"  v2 landing rows: skipped — {v2l_warnings[0] if v2l_warnings else 'no data'}")
        if v2l_warnings:
            warnings_all.extend(f"[Лендинг v2] {w}" for w in v2l_warnings)
    except Exception as _v2l_err:
        print(f"  [WARN] build_v2_landing_rows failed (non-fatal): {_v2l_err}")
        warnings_all.append(f"[Лендинг v2] build failed: {_v2l_err}")

    # Build reels rows and inject into payload (errors are non-fatal)
    try:
        vr_headers, vr_rows, vr_warnings = build_reels_rows(sources)
        if vr_rows:
            clean_vr = [
                [_redact_url(cell, payload_mode=True) for cell in row]
                for row in vr_rows
            ]
            payload["sheets"]["Reels"] = {
                "headers": vr_headers,
                "rows":    clean_vr,
            }
            print(f"  reels rows: {len(vr_rows)} row(s) added to payload")
        else:
            print(f"  reels rows: skipped — {vr_warnings[0] if vr_warnings else 'no data'}")
        if vr_warnings:
            warnings_all.extend(f"[Reels] {w}" for w in vr_warnings)
    except Exception as _vr_err:
        print(f"  [WARN] build_reels_rows failed (non-fatal): {_vr_err}")
        warnings_all.append(f"[Reels] build failed: {_vr_err}")

    # Build posts rows and inject into payload (errors are non-fatal)
    try:
        vp_headers, vp_rows, vp_warnings = build_posts_rows(sources)
        if vp_rows:
            clean_vp = [
                [_redact_url(cell, payload_mode=True) for cell in row]
                for row in vp_rows
            ]
            payload["sheets"]["Посты"] = {
                "headers": vp_headers,
                "rows":    clean_vp,
            }
            print(f"  posts rows: {len(vp_rows)} row(s) added to payload")
        else:
            print(f"  posts rows: skipped — {vp_warnings[0] if vp_warnings else 'no data'}")
        if vp_warnings:
            warnings_all.extend(f"[Посты] {w}" for w in vp_warnings)
    except Exception as _vp_err:
        print(f"  [WARN] build_posts_rows failed (non-fatal): {_vp_err}")
        warnings_all.append(f"[Посты] build failed: {_vp_err}")

    # Extract pinned rows metadata
    pinned_data = sheet_data.get("Закрепленные посты", {})
    pinned_meta = pinned_data.get("pinned_meta") or {}

    ts  = datetime.utcnow().isoformat() + "Z"
    meta = {
        "generated_at":                  ts,
        "account":                       ACCOUNT,
        "spreadsheet_id":                SPREADSHEET_ID,
        "start_row":                     START_ROW,
        "headers_source":                headers_source,
        "source_presence":               presence,
        "dry_run":                       dry_run,
        "pinned_rows_source":            pinned_meta.get("source"),
        "pinned_rows_count":             pinned_meta.get("rows_count", 0),
        "pinned_semantic_fields_filled": pinned_meta.get("semantic_fields_filled", False),
        "pinned_hook_field_empty":       pinned_meta.get("hook_field_empty", True),
        "pinned_warnings_count":         pinned_meta.get("warnings_count", 0),
    }

    summary = _build_summary(sheet_data, meta, warnings_all)

    # 7. Print row counts
    print("\n=== Row Counts ===")
    total_rows = 0
    for sname, data in sheet_data.items():
        n = len(data["rows"])
        total_rows += n
        print(f"  {sname}: {n} rows, {len(data['headers'])} columns")
    print(f"  TOTAL: {total_rows} rows across {len(sheet_data)} sheets")

    # Pinned posts source summary
    pinned_source = pinned_meta.get("source") or "unknown"
    print("\n=== Закрепленные посты — source info ===")
    print(f"  Source used:             {pinned_source}")
    print(f"  Rows count:              {pinned_meta.get('rows_count', 0)}")
    print(f"  Semantic fields filled:  {'yes' if pinned_meta.get('semantic_fields_filled') else 'no'}")
    print(f"  Hook field empty:        {'yes' if pinned_meta.get('hook_field_empty', True) else 'NO (unexpected)'}")
    print(f"  Pinned warnings count:   {pinned_meta.get('warnings_count', 0)}")

    if pinned_source == "pinned_posts_index_fallback" and not require_semantic:
        print(
            "  [WARNING] Using fallback source. "
            "stage5a2c semantic rows not found. "
            "Run Stage 5A-2C locally to generate fixed rows."
        )

    # Pinned rows preview (mandatory — shows whether semantic rows or fallback are used)
    pinned_rows = pinned_data.get("rows") or []
    pinned_hdrs = pinned_data.get("headers") or []
    if pinned_rows and pinned_hdrs:
        _print_pinned_preview(pinned_hdrs, pinned_rows)

    if warnings_all:
        print(f"\n=== Warnings ({len(warnings_all)}) ===")
        for w in warnings_all:
            print(f"  {w}")

    if dry_run:
        print("\n[DRY-RUN] Complete. No files written.")
        print("Output paths that WOULD be written (not gitignored — all in output/):")
        out = BASE / "output" / ACCOUNT / "stage5d1"
        print(f"  {out}/csv/<sheet>.csv  (utf-8-sig)")
        print(f"  {out}/payload.json")
        print(f"  {out}/stage5d1_summary.json")
        print(f"  report/stage_5d1_sheet_rows_preview_report.md  (gitignored)")
        return

    # 8. Write outputs
    out_dir = BASE / "output" / ACCOUNT / "stage5d1"
    csv_dir = out_dir / "csv"

    print("\nWriting CSV files...")
    for sname, data in sheet_data.items():
        safe_name = sname.replace(" ", "_").replace("/", "-")
        csv_path  = csv_dir / f"{safe_name}.csv"
        _write_csv(csv_path, data["headers"], data["rows"])
        print(f"  -> {csv_path.relative_to(BASE)}")

    payload_path = out_dir / "payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {payload_path.relative_to(BASE)}")

    summary_path = out_dir / "stage5d1_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {summary_path.relative_to(BASE)}")

    report_path = BASE / "report" / "stage_5d1_sheet_rows_preview_report.md"
    _write_report(report_path, sheet_data, meta, warnings_all)
    print(f"  -> {report_path.relative_to(BASE)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
