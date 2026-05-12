"""Stage 5D-3: Send validate or write request to Google Sheets Apps Script Web App.

Default behaviour is dry-run (prints plan, sends no request, writes no files).
Use --validate to send a validate-only request.
Use --write --confirm-write to send a write request.
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent.parent

PAYLOAD_PATH = BASE / "output" / "stage5d1" / "payload.json"
OUT_DIR      = BASE / "output" / "stage5d3_write"
REPORT_DIR   = BASE / "report"

EXPECTED_SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
REQUIRED_START_ROW      = 3

# Expected row counts enforced by default
EXPECTED_ROW_COUNTS = {
    "Описание профиля":  1,
    "Анализ хайлайтс":   32,
    "Закрепленные посты": 3,
    "Воронка":            1,
    "Лендинг":            1,
    "Бот  лид-магнит":   0,   # two spaces in sheet name
}

# Sheets where 0 rows is intentional and always allowed
_SHEETS_ALLOW_EMPTY_ROWS = {"Бот  лид-магнит"}

_SECRET_PATTERNS = [
    "sk-", "apify_api_", "sessionid=", "OPENAI_API_KEY=", "APIFY_TOKEN=",
    "INSTAGRAM_SESSION_COOKIE=", "GOOGLE_SHEETS_SYNC_SECRET=",
    "GOOGLE_SHEETS_WEBAPP_URL=", "Authorization:", "Bearer ",
]


# ---------------------------------------------------------------------------
# Secret scanner
# ---------------------------------------------------------------------------

def _scan_secrets(text: str) -> list[str]:
    return [p for p in _SECRET_PATTERNS if p in text]


# ---------------------------------------------------------------------------
# Payload loader and validator
# ---------------------------------------------------------------------------

def load_and_validate_payload(
    only_sheet: str | None = None,
    allow_row_count_drift: bool = False,
) -> tuple[dict, list[str]]:
    errors = []

    if not PAYLOAD_PATH.exists():
        errors.append(f"Payload file not found: {PAYLOAD_PATH}")
        return {}, errors

    try:
        payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse payload.json: {e}")
        return {}, errors

    sid = payload.get("spreadsheet_id")
    if sid != EXPECTED_SPREADSHEET_ID:
        errors.append(
            f"payload.json spreadsheet_id='{sid}' "
            f"!= expected '{EXPECTED_SPREADSHEET_ID}'"
        )

    sr = payload.get("start_row")
    if sr != REQUIRED_START_ROW:
        errors.append(f"payload.json start_row={sr} != required {REQUIRED_START_ROW}")

    sheets = payload.get("sheets")
    if not sheets or not isinstance(sheets, dict):
        errors.append("payload.json 'sheets' is missing or not a dict")
        return payload, errors

    # Validate only_sheet exists in payload
    if only_sheet and only_sheet not in sheets:
        errors.append(
            f"--only-sheet '{only_sheet}' not found in payload. "
            f"Available: {list(sheets.keys())}"
        )
        return payload, errors

    target_sheets = {only_sheet: sheets[only_sheet]} if only_sheet else sheets

    for sname, sdata in target_sheets.items():
        if not sname or not sname.strip():
            errors.append("payload.json has a sheet with an empty name")
        headers = sdata.get("headers") or []
        rows    = sdata.get("rows") or []

        if not headers:
            errors.append(f"Sheet '{sname}': no headers in payload")

        # Row length check
        for i, row in enumerate(rows):
            if len(row) != len(headers):
                errors.append(
                    f"Sheet '{sname}', row {i}: length {len(row)} "
                    f"!= headers length {len(headers)}"
                )

        # Row count enforcement
        if not allow_row_count_drift and sname in EXPECTED_ROW_COUNTS:
            expected = EXPECTED_ROW_COUNTS[sname]
            actual   = len(rows)
            if actual != expected:
                errors.append(
                    f"Sheet '{sname}': expected {expected} rows, got {actual}. "
                    f"Use --allow-row-count-drift to skip this check."
                )

    # Secret scan
    payload_str = json.dumps(payload, ensure_ascii=False)
    leaked = _scan_secrets(payload_str)
    if leaked:
        errors.append(f"Secret patterns found in payload.json: {leaked}")

    return payload, errors


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def build_request(
    payload: dict,
    secret: str,
    mode: str,
    only_sheet: str | None = None,
    allow_empty_clear: bool = False,
    write_id: str | None = None,
) -> dict:
    sheets_payload = payload.get("sheets", {})
    if only_sheet:
        sheets_payload = {only_sheet: sheets_payload[only_sheet]}

    req = {
        "secret":           secret,
        "spreadsheet_id":   payload.get("spreadsheet_id", EXPECTED_SPREADSHEET_ID),
        "mode":             mode,
        "start_row":        REQUIRED_START_ROW,
        "write_id":         write_id,
        "allow_empty_clear": allow_empty_clear,
        "only_sheet":       only_sheet,
        "sheets":           sheets_payload,
    }
    return req


# ---------------------------------------------------------------------------
# HTTP sender
# ---------------------------------------------------------------------------

def send_request(webapp_url: str, req_body: dict) -> dict:
    import urllib.request
    import urllib.error

    req_bytes = json.dumps(req_body, ensure_ascii=False).encode("utf-8")
    http_req  = urllib.request.Request(
        webapp_url,
        data=req_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(http_req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _safe_url_display(url: str) -> str:
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}/..."
    except Exception:
        return "<url>"


def write_response_report(response: dict, meta: dict, report_path: Path):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append(f"# Stage 5D-3 Google Sheets {meta.get('mode', '').title()} Report")
    lines.append("")
    lines.append(f"Sent at:        {meta.get('sent_at', '—')}")
    lines.append(f"Mode:           {response.get('mode', '—')}")
    lines.append(f"Write ID:       {response.get('write_id', '—')}")
    lines.append(f"Spreadsheet ID: {response.get('spreadsheet_id', '—')}")
    lines.append(f"Spreadsheet:    {response.get('spreadsheet_name', '—')}")
    lines.append(f"Start row:      {response.get('start_row', '—')}")
    lines.append(f"Validated:      {response.get('validated', '—')}")
    lines.append(f"Written:        {response.get('written', '—')}")
    lines.append(f"Overall OK:     **{response.get('ok', False)}**")
    lines.append("")

    top_errors   = response.get("errors") or []
    top_warnings = response.get("warnings") or []
    if top_errors:
        lines.append("## Top-level Errors")
        for e in top_errors:
            lines.append(f"- {e}")
        lines.append("")
    if top_warnings:
        lines.append("## Top-level Warnings")
        for w in top_warnings:
            lines.append(f"- {w}")
        lines.append("")

    sheets = response.get("sheets") or {}
    if sheets:
        lines.append("## Sheet Results")
        lines.append("")
        lines.append("| Sheet | OK | Exists | Cols | Payload rows | Cleared | Written | Skipped |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for sname, sd in sheets.items():
            lines.append(
                f"| {sname} | {sd.get('ok')} | {sd.get('exists')} "
                f"| {sd.get('payload_headers_count')} | {sd.get('payload_rows_count')} "
                f"| {sd.get('cleared_range', '—')} | {sd.get('written_range', '—')} "
                f"| {sd.get('skipped', False)} |"
            )
        lines.append("")

        for sname, sd in sheets.items():
            errs  = sd.get("errors") or []
            warns = sd.get("warnings") or []
            mm    = sd.get("mismatches") or []
            sim   = sd.get("similar_sheet_names") or []
            if errs or warns or mm:
                lines.append(f"### {sname}")
                if sim:
                    lines.append(f"**Similar sheet names**: {', '.join(sim)}")
                for e in errs:
                    lines.append(f"- ERROR: {e}")
                for m in mm:
                    lines.append(
                        f"  - col {m.get('col')}: expected `{m.get('expected')}`, "
                        f"got `{m.get('actual')}`"
                    )
                for w in warns:
                    lines.append(f"- WARNING: {w}")
                lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(
    payload: dict,
    errors: list[str],
    only_sheet: str | None,
    allow_row_count_drift: bool,
):
    print("[DRY-RUN] No request will be sent.\n")

    if errors:
        print(f"[ERROR] Local payload validation failed ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        print()

    sheets = payload.get("sheets") or {}

    print(f"Payload:          {PAYLOAD_PATH.relative_to(BASE)}")
    print(f"  spreadsheet_id: {payload.get('spreadsheet_id', '—')}")
    print(f"  start_row:      {payload.get('start_row', '—')} (forced to {REQUIRED_START_ROW})")
    print(f"  sheet count:    {len(sheets)}")
    print()

    if only_sheet:
        print(f"  --only-sheet target: '{only_sheet}'")
        print()

    target = {only_sheet: sheets[only_sheet]} if only_sheet and only_sheet in sheets else sheets

    total_rows = 0
    print("  Sheet summary:")
    for sname, sdata in sheets.items():
        h    = len(sdata.get("headers") or [])
        r    = len(sdata.get("rows") or [])
        mark = " ← TARGET" if sname in target else " (skipped, not in --only-sheet)"
        exp  = EXPECTED_ROW_COUNTS.get(sname)
        drift = f" [expected {exp}]" if exp is not None and r != exp else ""
        print(f"    {sname!r}: {h} cols, {r} rows{drift}{mark}")
        if sname in target:
            total_rows += r

    print(f"\n  Total rows to write: {total_rows}")
    print()

    no_write = [s for s in target if len(target[s].get("rows") or []) == 0]
    if no_write:
        print("  Sheets with 0 rows (will NOT be cleared unless allow_empty_clear=true):")
        for s in no_write:
            print(f"    - {s!r}")
        print()

    webapp_url  = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "")
    sync_secret = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "")
    print("Environment variables:")
    print(f"  GOOGLE_SHEETS_WEBAPP_URL  : {'SET' if webapp_url else 'NOT SET (required for --validate / --write)'}")
    print(f"  GOOGLE_SHEETS_SYNC_SECRET : {'SET' if sync_secret else 'NOT SET (required for --validate / --write)'}")
    print()

    print("[DRY-RUN] Complete. Next steps:")
    print("  python3 scripts/stage5d3_write_google_sheets.py --validate")
    print('  python3 scripts/stage5d3_write_google_sheets.py --write --confirm-write --only-sheet "Описание профиля"')
    print("  python3 scripts/stage5d3_write_google_sheets.py --write --confirm-write")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def run_validate(payload: dict, errors: list[str], only_sheet: str | None):
    if errors:
        print(f"[ERROR] Local payload validation failed; fix before sending:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    webapp_url  = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "").strip()
    sync_secret = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "").strip()
    if not webapp_url:
        print("[ERROR] GOOGLE_SHEETS_WEBAPP_URL is not set.")
        sys.exit(1)
    if not sync_secret:
        print("[ERROR] GOOGLE_SHEETS_SYNC_SECRET is not set.")
        sys.exit(1)

    req_body = build_request(payload, sync_secret, "validate", only_sheet=only_sheet)

    # Scan request body (excluding secret field) for leaked secrets
    req_check = {k: v for k, v in req_body.items() if k != "secret"}
    leaked = _scan_secrets(json.dumps(req_check, ensure_ascii=False))
    if leaked:
        print(f"[ERROR] Secret pattern in request body: {leaked}")
        sys.exit(1)

    print(f"Sending validate request to {_safe_url_display(webapp_url)} ...")
    sent_at = datetime.utcnow().isoformat() + "Z"

    try:
        response = send_request(webapp_url, req_body)
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resp_path = OUT_DIR / "validate_response.json"
    resp_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Response saved: {resp_path.relative_to(BASE)}")

    report_path = REPORT_DIR / "stage_5d3_google_sheets_validate_report.md"
    write_response_report(response, {"sent_at": sent_at, "mode": "validate"}, report_path)
    print(f"Report written: {report_path.relative_to(BASE)}")

    _print_summary(response)
    if not response.get("ok"):
        sys.exit(1)


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------

def run_write(
    payload: dict,
    errors: list[str],
    only_sheet: str | None,
    allow_empty_clear: bool,
):
    if errors:
        print(f"[ERROR] Local payload validation failed; fix before sending:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    webapp_url  = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "").strip()
    sync_secret = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "").strip()
    if not webapp_url:
        print("[ERROR] GOOGLE_SHEETS_WEBAPP_URL is not set.")
        sys.exit(1)
    if not sync_secret:
        print("[ERROR] GOOGLE_SHEETS_SYNC_SECRET is not set.")
        sys.exit(1)

    write_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    req_body  = build_request(
        payload, sync_secret, "write",
        only_sheet=only_sheet,
        allow_empty_clear=allow_empty_clear,
        write_id=write_id,
    )

    req_check = {k: v for k, v in req_body.items() if k != "secret"}
    leaked = _scan_secrets(json.dumps(req_check, ensure_ascii=False))
    if leaked:
        print(f"[ERROR] Secret pattern in request body: {leaked}")
        sys.exit(1)

    print(f"Write ID:  {write_id}")
    print(f"Sending write request to {_safe_url_display(webapp_url)} ...")
    sent_at = datetime.utcnow().isoformat() + "Z"

    try:
        response = send_request(webapp_url, req_body)
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    resp_path = OUT_DIR / "write_response.json"
    resp_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Response saved: {resp_path.relative_to(BASE)}")

    report_path = REPORT_DIR / "stage_5d3_google_sheets_write_report.md"
    write_response_report(response, {"sent_at": sent_at, "mode": "write"}, report_path)
    print(f"Report written: {report_path.relative_to(BASE)}")

    _print_summary(response)
    if not response.get("ok"):
        sys.exit(1)


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(response: dict):
    overall_ok = response.get("ok", False)
    print(f"\nOverall result: {'OK' if overall_ok else 'FAILED'}")

    top_errors = response.get("errors") or []
    if top_errors:
        print(f"Top-level errors ({len(top_errors)}):")
        for e in top_errors:
            print(f"  - {e}")

    sheets = response.get("sheets") or {}
    for sname, sd in sheets.items():
        ok    = sd.get("ok", False)
        errs  = sd.get("errors") or []
        warns = sd.get("warnings") or []
        skip  = sd.get("skipped", False)
        wr    = sd.get("written_range", "—")
        status = "SKIPPED" if skip else ("OK" if ok else "FAILED")
        print(f"  Sheet '{sname}': {status}", end="")
        if wr and not skip:
            print(f"  written={wr}", end="")
        if errs:
            print(f"  — {len(errs)} error(s)", end="")
        if warns:
            print(f"  — {len(warns)} warning(s)", end="")
        print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5D-3: validate or write Google Sheets via Apps Script"
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Print plan; send no request (default)",
    )
    mode_group.add_argument(
        "--validate", action="store_true",
        help="Send validate request to Apps Script (read-only)",
    )
    mode_group.add_argument(
        "--write", action="store_true",
        help="Send write request to Apps Script (requires --confirm-write)",
    )

    parser.add_argument(
        "--confirm-write", action="store_true",
        help="Required safety flag when using --write",
    )
    parser.add_argument(
        "--only-sheet", metavar="SHEET_NAME",
        help="Validate/write only this sheet",
    )
    parser.add_argument(
        "--allow-row-count-drift", action="store_true",
        help="Skip expected-row-count enforcement",
    )
    parser.add_argument(
        "--allow-empty-clear", action="store_true",
        help="Clear row 3+ even for sheets with 0 rows (passed to Apps Script)",
    )

    args = parser.parse_args()

    if args.write and not args.confirm_write:
        print("[ERROR] --write requires --confirm-write as an explicit safety acknowledgement.")
        print("  python3 scripts/stage5d3_write_google_sheets.py --write --confirm-write")
        sys.exit(1)

    payload, errors = load_and_validate_payload(
        only_sheet=args.only_sheet,
        allow_row_count_drift=args.allow_row_count_drift,
    )

    if args.validate:
        run_validate(payload, errors, only_sheet=args.only_sheet)
    elif args.write:
        run_write(
            payload, errors,
            only_sheet=args.only_sheet,
            allow_empty_clear=args.allow_empty_clear,
        )
    else:
        run_dry_run(
            payload, errors,
            only_sheet=args.only_sheet,
            allow_row_count_drift=args.allow_row_count_drift,
        )


if __name__ == "__main__":
    main()
