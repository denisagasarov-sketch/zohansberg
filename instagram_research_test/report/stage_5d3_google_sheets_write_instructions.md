# Stage 5D-3: Google Sheets Write — Local Run Instructions

## What this stage does

**This stage writes prepared row data to Google Sheets.** Writing happens only
when you run `--write --confirm-write` explicitly.

Rows 1 and 2 are **protected** — they are never touched under any circumstances.
Data is written starting at row 3. Old content from row 3 downward is cleared
with `clearContent()` (formatting, notes, and validations are preserved) before
new rows are written.

**Sheets with 0 rows are not cleared** unless `--allow-empty-clear` is passed.

Current payload (prepared by Stage 5D-1):
- Описание профиля — 1 row
- Анализ хайлайтс — 32 rows
- Закрепленные посты — 3 rows
- Воронка — 1 provisional row (bio URL only; destination type not classified)
- Лендинг — 1 provisional row (bio URL only)
- Бот  лид-магнит — 0 rows (no bot source yet)

**Total: 38 rows.** Not all analytical fields are filled. Some rows are
provisional because landing/funnel/bot analysis is not yet built.

---

## Prerequisites

1. **Stage 5D-1 outputs** must exist:
   - `output/stage5d1/payload.json`

2. **Stage 5D-2 validate** must have passed (`ok: true`) — confirms sheets exist
   and headers match.

3. **Apps Script Web App deployed** (see Step 2 below — this is a NEW deployment
   replacing the Stage 5D-2 script).

4. **`.env` file** with:
   ```
   GOOGLE_SHEETS_WEBAPP_URL=<your-new-web-app-url>
   GOOGLE_SHEETS_SYNC_SECRET=<same-long-random-secret>
   ```

---

## Step 1: Prepare environment

```bash
cd instagram_research_test
set -a
source .env
set +a
```

---

## Step 2: Update Apps Script with Stage 5D-3 code

**Important:** This replaces the Stage 5D-2 script. The new script supports
both `mode=validate` and `mode=write`. It is still read-only in validate mode.

1. Open the spreadsheet:
   `https://docs.google.com/spreadsheets/d/1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ/edit`
2. **Extensions → Apps Script**
3. Replace all existing code with the contents of:
   `apps_script/stage5d3_write_google_sheets_webapp.gs`
4. Click **Save**

**Script Properties:** Keep existing `SYNC_SECRET` value — no change needed.

### Deploy as new version

1. **Deploy → Manage deployments**
2. Click the pencil (edit) icon on the existing Web App deployment
3. Under **Version**, select **New version**
4. Confirm settings:
   - **Execute as**: Me
   - **Who has access**: Anyone with the link (or closest available)
5. Click **Deploy**
6. If the Web App URL changed, update `GOOGLE_SHEETS_WEBAPP_URL` in `.env`

---

## Step 3: Dry-run (always first)

```bash
python3 scripts/stage5d3_write_google_sheets.py --dry-run
```

Prints plan: spreadsheet_id, start_row, sheet names, column counts, row counts,
which sheets would be written, env var presence. No request sent, no files written.

---

## Step 4: Validate (read-only check on live spreadsheet)

```bash
python3 scripts/stage5d3_write_google_sheets.py --validate
```

Sends `mode=validate` to Apps Script. Apps Script checks sheet existence and
header alignment but writes nothing. Outputs:
- `output/stage5d3_write/validate_response.json` (gitignored)
- `report/stage_5d3_google_sheets_validate_report.md` (gitignored)

Fix any errors before proceeding.

---

## Step 5: Write one sheet first (recommended)

Test with a single sheet to verify formatting and data before the full write:

```bash
python3 scripts/stage5d3_write_google_sheets.py \
  --write --confirm-write \
  --only-sheet "Описание профиля"
```

**After this command:**
1. Open Google Sheets and visually inspect row 3 of "Описание профиля"
2. Verify data is in the correct columns
3. Verify rows 1–2 are untouched
4. If anything looks wrong, do NOT run the full write yet

---

## Step 6: Full write (only after one-sheet check passes)

```bash
python3 scripts/stage5d3_write_google_sheets.py --write --confirm-write
```

Writes all sheets with rows > 0. Sheets with 0 rows are skipped.

Outputs:
- `output/stage5d3_write/write_response.json` (gitignored)
- `report/stage_5d3_google_sheets_write_report.md` (gitignored)

---

## CLI reference

| Command | Effect |
|---|---|
| `--dry-run` (default) | Print plan; no request |
| `--validate` | Send validate-only request |
| `--write --confirm-write` | Send write request |
| `--only-sheet "Sheet name"` | Target one sheet only |
| `--allow-row-count-drift` | Skip expected-row-count check |
| `--allow-empty-clear` | Clear rows 3+ even for empty-row sheets |

---

## What the write response tells you

| Field | Meaning |
|---|---|
| `ok: true` | All target sheets written successfully |
| `validated: true` | Pre-write validation passed |
| `written: true` | Data rows written |
| `sheets.<name>.cleared_range` | Range cleared before write (e.g. `A3:K10`) |
| `sheets.<name>.written_range` | Range written (e.g. `A3:K3`) |
| `sheets.<name>.written_rows` | Number of data rows written |
| `sheets.<name>.skipped` | True if sheet had 0 rows and was not cleared |
| `sheets.<name>.skipped_reason` | `"empty_rows_no_clear"` when skipped |

---

## What is NOT written by this stage

- **Бот  лид-магнит** — no bot/lead-magnet source yet (0 rows, always skipped)
- Semantic fields that require AI analysis not yet built:
  - Тема поста, Почему закреплен, Хук, Роль в воронке (pinned posts)
  - Какая механика подачи хайлайтс (highlights)
  - Full funnel/landing/bot columns (need link destination classifier first)

---

## Security rules

- Do NOT print `GOOGLE_SHEETS_SYNC_SECRET`
- Do NOT commit `.env`
- Do NOT commit `output/`, runtime reports, or `payload.json`
- Secret read from environment variable only — never hardcoded
- Web App URL read from environment variable only — never hardcoded
- Apps Script reads secret from Script Properties only — never hardcoded
