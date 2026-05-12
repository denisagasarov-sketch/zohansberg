"""Stage 5D-2: Send validate-only request to Google Sheets Apps Script Web App.

Default behavior is dry-run (prints what would be sent, does not send).
Use --send to actually send the validate request.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

PAYLOAD_PATH        = BASE / "output" / "stage5d1" / "payload.json"
RESPONSE_DIR        = BASE / "output" / "stage5d2_validate"
RESPONSE_PATH       = RESPONSE_DIR / "validate_response.json"
REPORT_PATH         = BASE / "report" / "stage_5d2_google_sheets_validate_report.md"

EXPECTED_SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
REQUIRED_START_ROW      = 3
FORCED_MODE             = "validate"

_SECRET_PATTERNS = [
    "sk-", "apify_api_", "sessionid=", "OPENAI_API_KEY=", "APIFY_TOKEN=",
    "INSTAGRAM_SESSION_COOKIE=", "GOOGLE_SHEETS_SYNC_SECRET=", "GOOGLE_SHEETS_WEBAPP_URL=",
    "Authorization:", "Bearer ",
]

# Sheets where 0 rows is acceptable (no source data for this account yet)
_SHEETS_ALLOW_EMPTY_ROWS = {"Бот  лид-магнит"}


# ---------------------------------------------------------------------------
# Secret scanner
# ---------------------------------------------------------------------------

def _scan_secrets(text: str) -> list[str]:
    return [p for p in _SECRET_PATTERNS if p in text]


# ---------------------------------------------------------------------------
# Payload loader and validator
# ---------------------------------------------------------------------------

def load_and_validate_payload() -> tuple[dict, list[str]]:
    """Load payload.json and run local validation. Returns (payload, errors)."""
    errors = []

    if not PAYLOAD_PATH.exists():
        errors.append(f"Payload file not found: {PAYLOAD_PATH}")
        return {}, errors

    try:
        payload = json.loads(PAYLOAD_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse payload.json: {e}")
        return {}, errors

    # Check spreadsheet_id
    sid = payload.get("spreadsheet_id")
    if sid != EXPECTED_SPREADSHEET_ID:
        errors.append(
            f"payload.json spreadsheet_id='{sid}' "
            f"!= expected '{EXPECTED_SPREADSHEET_ID}'"
        )

    # Check start_row
    sr = payload.get("start_row")
    if sr != REQUIRED_START_ROW:
        errors.append(f"payload.json start_row={sr} != required {REQUIRED_START_ROW}")

    # Check sheets
    sheets = payload.get("sheets")
    if not sheets or not isinstance(sheets, dict):
        errors.append("payload.json 'sheets' is missing or not a dict")
        return payload, errors

    for sname, sdata in sheets.items():
        if not sname or not sname.strip():
            errors.append("payload.json has a sheet with empty name")
        headers = sdata.get("headers") or []
        rows    = sdata.get("rows")    or []
        if not headers:
            errors.append(f"Sheet '{sname}': no headers in payload")
        if not rows and sname not in _SHEETS_ALLOW_EMPTY_ROWS:
            pass  # Rows may be empty on first run; warn but not error

    # Secret scan
    payload_str = json.dumps(payload, ensure_ascii=False)
    secrets = _scan_secrets(payload_str)
    if secrets:
        errors.append(f"Secret patterns found in payload.json: {secrets}")

    return payload, errors


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------

def build_request(payload: dict, secret: str) -> dict:
    """Build the validate request body from payload, overriding mode and start_row."""
    req = {
        "secret":         secret,
        "spreadsheet_id": payload.get("spreadsheet_id", EXPECTED_SPREADSHEET_ID),
        "mode":           FORCED_MODE,
        "start_row":      REQUIRED_START_ROW,
        "sheets":         payload.get("sheets", {}),
    }
    return req


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(response: dict, meta: dict):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = meta.get("sent_at", "unknown")
    lines = []
    lines.append("# Stage 5D-2 Google Sheets Validate Report")
    lines.append("")
    lines.append(f"Sent at: {ts}")
    lines.append(f"Spreadsheet ID: {response.get('spreadsheet_id', '—')}")
    lines.append(f"Mode: {response.get('mode', '—')}")
    lines.append(f"Start row: {response.get('start_row', '—')}")
    lines.append(f"Overall OK: **{response.get('ok', False)}**")
    lines.append("")

    top_errors = response.get("errors") or []
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
        lines.append("| Sheet | OK | Exists | Payload cols | Sheet cols | Payload rows | Row2 |")
        lines.append("|---|---|---|---|---|---|---|")
        for sname, sdata in sheets.items():
            ok     = sdata.get("ok", False)
            exists = sdata.get("exists", False)
            pc     = sdata.get("payload_headers_count", 0)
            sc     = sdata.get("sheet_headers_count", 0)
            pr     = sdata.get("payload_rows_count", 0)
            r2     = sdata.get("row2_present", False)
            lines.append(f"| {sname} | {ok} | {exists} | {pc} | {sc} | {pr} | {r2} |")
        lines.append("")

        for sname, sdata in sheets.items():
            sheet_errors   = sdata.get("errors") or []
            sheet_warnings = sdata.get("warnings") or []
            mismatches     = sdata.get("mismatches") or []
            similar        = sdata.get("similar_sheet_names") or []
            if sheet_errors or sheet_warnings or mismatches:
                lines.append(f"### {sname}")
                if similar:
                    lines.append(f"**Similar sheet names**: {', '.join(similar)}")
                if sheet_errors:
                    for e in sheet_errors:
                        lines.append(f"- ERROR: {e}")
                if mismatches:
                    for m in mismatches:
                        lines.append(
                            f"  - col {m.get('col')}: expected `{m.get('expected')}`, "
                            f"got `{m.get('actual')}`"
                        )
                if sheet_warnings:
                    for w in sheet_warnings:
                        lines.append(f"- WARNING: {w}")
                lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(payload: dict, errors: list[str]):
    print("[DRY-RUN] No request will be sent.\n")

    if errors:
        print(f"[ERROR] Local payload validation failed ({len(errors)} error(s)):")
        for e in errors:
            print(f"  - {e}")
        print("")

    sheets = payload.get("sheets") or {}
    print(f"Payload: {PAYLOAD_PATH.relative_to(BASE)}")
    print(f"  spreadsheet_id : {payload.get('spreadsheet_id', '—')}")
    print(f"  start_row      : {payload.get('start_row', '—')} (will be forced to {REQUIRED_START_ROW})")
    print(f"  mode           : will be forced to '{FORCED_MODE}'")
    print(f"  sheet count    : {len(sheets)}")
    print("")
    print("  Sheet summary:")
    for sname, sdata in sheets.items():
        h = len(sdata.get("headers") or [])
        r = len(sdata.get("rows") or [])
        print(f"    {sname!r}: {h} cols, {r} rows")
    print("")

    # Check env vars — presence only, never print values
    webapp_url = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "")
    sync_secret = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "")
    print("Environment variables:")
    print(f"  GOOGLE_SHEETS_WEBAPP_URL    : {'SET' if webapp_url else 'NOT SET (required for --send)'}")
    print(f"  GOOGLE_SHEETS_SYNC_SECRET   : {'SET' if sync_secret else 'NOT SET (required for --send)'}")
    print("")

    print("[DRY-RUN] Complete. To send the validate request, run:")
    print("  python scripts/stage5d2_validate_google_sheets.py --send")


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------

def run_send(payload: dict, errors: list[str]):
    if errors:
        print(f"[ERROR] Local payload validation failed; fix before sending:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    webapp_url  = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "").strip()
    sync_secret = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "").strip()

    if not webapp_url:
        print("[ERROR] GOOGLE_SHEETS_WEBAPP_URL is not set in environment.")
        sys.exit(1)
    if not sync_secret:
        print("[ERROR] GOOGLE_SHEETS_SYNC_SECRET is not set in environment.")
        sys.exit(1)

    req_body = build_request(payload, sync_secret)

    # Scan request body for secrets (excluding the intentional secret field)
    req_without_secret = {k: v for k, v in req_body.items() if k != "secret"}
    req_str = json.dumps(req_without_secret, ensure_ascii=False)
    leaked = _scan_secrets(req_str)
    if leaked:
        print(f"[ERROR] Secret pattern found in request body (non-secret fields): {leaked}")
        sys.exit(1)

    try:
        import urllib.request
        import urllib.error
    except ImportError:
        print("[ERROR] urllib not available.")
        sys.exit(1)

    req_bytes = json.dumps(req_body, ensure_ascii=False).encode("utf-8")
    # Print URL scheme+host only, never query params or full URL to avoid leaking tokens
    from urllib.parse import urlparse
    parsed = urlparse(webapp_url)
    safe_url_display = f"{parsed.scheme}://{parsed.netloc}/..."

    print(f"Sending validate request to {safe_url_display} ...")
    sent_at = datetime.utcnow().isoformat() + "Z"

    try:
        http_req = urllib.request.Request(
            webapp_url,
            data=req_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(http_req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] HTTP {e.code}: {e.reason}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] Request failed: {e.reason}")
        sys.exit(1)

    try:
        response = json.loads(raw)
    except Exception as e:
        print(f"[ERROR] Response is not valid JSON: {e}")
        print(f"Raw response (first 500 chars): {raw[:500]}")
        sys.exit(1)

    # Save response
    RESPONSE_DIR.mkdir(parents=True, exist_ok=True)
    RESPONSE_PATH.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Response saved: {RESPONSE_PATH.relative_to(BASE)}")

    # Write report
    write_report(response, {"sent_at": sent_at})
    print(f"Report written: {REPORT_PATH.relative_to(BASE)}")

    # Print summary
    overall_ok = response.get("ok", False)
    print(f"\nOverall validate result: {'OK' if overall_ok else 'FAILED'}")

    top_errors = response.get("errors") or []
    if top_errors:
        print(f"Top-level errors ({len(top_errors)}):")
        for e in top_errors:
            print(f"  - {e}")

    sheets = response.get("sheets") or {}
    for sname, sdata in sheets.items():
        ok = sdata.get("ok", False)
        sheet_errors = sdata.get("errors") or []
        sheet_warnings = sdata.get("warnings") or []
        status = "OK" if ok else "FAILED"
        print(f"  Sheet '{sname}': {status}", end="")
        if sheet_errors:
            print(f" — {len(sheet_errors)} error(s)", end="")
        if sheet_warnings:
            print(f" — {len(sheet_warnings)} warning(s)", end="")
        print()

    if not overall_ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5D-2: Validate Google Sheets structure against payload"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Print what would be sent; do not send (default)",
    )
    group.add_argument(
        "--send", action="store_true",
        help="Send validate request to Apps Script Web App",
    )
    args = parser.parse_args()

    payload, errors = load_and_validate_payload()

    if args.send:
        run_send(payload, errors)
    else:
        run_dry_run(payload, errors)


if __name__ == "__main__":
    main()
