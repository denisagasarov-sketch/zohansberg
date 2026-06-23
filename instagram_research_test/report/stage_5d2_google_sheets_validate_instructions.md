# Stage 5D-2: Google Sheets Validate-Only — Local Run Instructions

## What this stage does

**Validate only.** This stage reads the Google Sheets structure and compares it to the local payload headers. It does **not** write rows, does **not** clear cells, does **not** modify rows 1 or 2, and does **not** modify any formatting.

Writing data to Google Sheets is a **separate future stage** (Stage 5D-3 or later).

---

## What is validated

For each sheet in the payload:
- Sheet exists in the spreadsheet
- Row 1 header names match payload headers exactly (name and order)
- No extra non-empty headers in row 1 beyond payload width
- Row 2 (comment/hint row) is present (warning only if missing — not an error)
- `start_row = 3` (data must start at row 3)
- `spreadsheet_id` matches expected ID

---

## Prerequisites

1. **Stage 5D-1 outputs** must exist:
   - `output/stage5d1/payload.json`

2. **Python 3.10+** (no additional packages — uses only stdlib `urllib`)

3. **Apps Script Web App deployed** (see setup below)

4. **`.env` file** with:
   ```
   GOOGLE_SHEETS_WEBAPP_URL=<your-web-app-url>
   GOOGLE_SHEETS_SYNC_SECRET=<your-long-random-secret>
   ```

---

## Step 1: Open Google Sheet

Open the spreadsheet:
**Spreadsheet ID**: `1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ`

---

## Step 2: Open Apps Script editor

In the spreadsheet: **Extensions → Apps Script**

---

## Step 3: Paste the Apps Script

Copy the full contents of:
```
apps_script/stage5d2_validate_google_sheets_webapp.gs
```

Paste into the Apps Script editor (replace any existing code).

Click **Save** (floppy disk icon or Ctrl+S).

---

## Step 4: Set Script Properties (secret)

In Apps Script:
1. Click **Project Settings** (gear icon in left sidebar)
2. Scroll to **Script Properties**
3. Click **Add script property**
4. Name: `SYNC_SECRET`
5. Value: generate a long random secret (e.g. 40+ random characters — use a password manager or `openssl rand -hex 32`)
6. Click **Save script properties**

**Never commit this secret to git.**

---

## Step 5: Deploy as Web App

In Apps Script:
1. Click **Deploy** → **New deployment**
2. Click the gear icon next to **Select type** → choose **Web app**
3. Settings:
   - **Execute as**: Me
   - **Who has access**: Anyone with the link *(closest available option if "Anyone" is not shown)*
4. Click **Deploy**
5. Copy the **Web App URL** (looks like `https://script.google.com/macros/s/.../exec`)

---

## Step 6: Add to local `.env`

Open (or create) `instagram_research_test/.env` and add:

```env
GOOGLE_SHEETS_WEBAPP_URL=https://script.google.com/macros/s/.../exec
GOOGLE_SHEETS_SYNC_SECRET=your-long-random-secret-here
```

**Never commit `.env` to git.**

---

## Step 7: Run dry-run (always first)

```bash
cd instagram_research_test
source .env  # or: export $(cat .env | xargs)
python scripts/stage5d2_validate_google_sheets.py --dry-run
```

Dry-run output:
- Prints spreadsheet_id, start_row, sheet names, column/row counts
- Checks env var presence (never prints values)
- Does **not** send any request
- Writes **no files**

---

## Step 8: Run validate (only after reviewing dry-run)

```bash
python scripts/stage5d2_validate_google_sheets.py --send
```

This sends a POST request to the Apps Script Web App with:
- `mode = "validate"` (forced — no write possible)
- `start_row = 3` (forced)
- All sheet headers from `payload.json`

Outputs (gitignored — not committed):
- `output/stage5d2_validate/validate_response.json`
- `report/stage_5d2_google_sheets_validate_report.md`

---

## Output files

All runtime outputs are gitignored.

| File | Description |
|---|---|
| `output/stage5d2_validate/validate_response.json` | Raw JSON response from Apps Script |
| `report/stage_5d2_google_sheets_validate_report.md` | Human-readable validation report |

---

## What the validate response tells you

| Field | Meaning |
|---|---|
| `ok: true` | All sheets validated, all headers match |
| `ok: false` | At least one sheet or header failed |
| `sheets.<name>.ok` | Per-sheet validation result |
| `sheets.<name>.exists` | Whether the sheet was found |
| `sheets.<name>.mismatches` | Header mismatches (col number, expected, actual) |
| `sheets.<name>.similar_sheet_names` | Suggestions if sheet not found (typos, spacing) |
| `sheets.<name>.row2_present` | Whether row 2 has any content |
| `warnings` | Non-blocking issues (extra sheets, empty row 2) |
| `errors` | Blocking failures (missing sheet, header mismatch) |

---

## Security rules

- Do NOT call Google Sheets API directly
- Do NOT print `GOOGLE_SHEETS_SYNC_SECRET` anywhere
- Do NOT commit `.env`
- Do NOT commit `payload.json`, `validate_response.json`, or runtime reports
- Apps Script reads secret from Script Properties only — never hardcoded
- Python client reads secret from environment variable only — never hardcoded

---

## Next step after successful validation

If `ok: true` — all sheets exist and headers match. You are ready to proceed to **Stage 5D-3** (write rows), which is a separate future stage requiring explicit permission.

If `ok: false` — fix the sheet structure in Google Sheets (add missing sheets, correct header names in row 1) and re-run `--send`.
