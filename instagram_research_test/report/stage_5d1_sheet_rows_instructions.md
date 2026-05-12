# Stage 5D-1: Google Sheets-Ready Row Preview — Local Run Instructions

## What this stage does

Builds Google Sheets-ready row data from existing normalized pipeline outputs and writes:
- **CSV files** per sheet (utf-8-sig encoding, Google Sheets compatible)
- **payload.json** — structured JSON matching the target spreadsheet format
- **stage5d1_summary.json** — row counts, warnings, source presence
- **Preview report** — markdown with row counts, source status, per-sheet previews

All outputs are local only. Nothing is sent to Google Sheets.

---

## Spreadsheet target

- **Spreadsheet ID**: `1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ`
- **Data starts at row**: 3 (row 1 = column headers, row 2 = comments/hints — DO NOT TOUCH)
- **Total columns**: 79 across 6 sheets

---

## Prerequisites

- Python 3.10+
- Normalized outputs in `data/normalized/`:
  - `profile_summary.json` ← Stage 5A
  - `bio_analysis.json` ← Stage 5A
  - `pinned_posts_index.json` ← Stage 5A
  - `highlights_index.json` ← Stage 5B-1
  - `stage5b_auto_stories_index.json` ← Stage 5B-auto
  - `stage5c_highlights_summary.json` ← Stage 5C (optional; enriches highlights rows)
  - `stage5c_stories_analysis.json` ← Stage 5C (optional)
  - `stage5d_coverage_map.json` ← Stage 5D (optional; used for reference only)
- Optional: `input/competitor_analysis_template.xlsx` (openpyxl reads headers from row 1).
  If absent, hardcoded fallback headers are used.

---

## Running locally

### 1. Dry-run first (recommended)

```bash
cd instagram_research_test
python scripts/stage5d1_run_local.py --dry-run
```

Validates sources and row building without writing any files. Prints row counts and warnings.

### 2. Full run (writes output files)

```bash
cd instagram_research_test
python scripts/stage5d1_run_local.py
```

Writes to `output/stage5d1/` (gitignored) and `report/stage_5d1_sheet_rows_preview_report.md` (gitignored).

---

## Output files

All outputs are gitignored and must NOT be committed.

| File | Description |
|---|---|
| `output/stage5d1/csv/<sheet>.csv` | One CSV per sheet, utf-8-sig, row 1 = headers |
| `output/stage5d1/payload.json` | JSON payload (preview_only mode) |
| `output/stage5d1/stage5d1_summary.json` | Row counts, warnings, source presence |
| `report/stage_5d1_sheet_rows_preview_report.md` | Human-readable preview report |

---

## Expected row counts (current data)

| Sheet | Expected rows |
|---|---|
| Описание профиля | 1 |
| Анализ хайлайтс | 32 (from highlights_index) |
| Закрепленные посты | 3 (from pinned_posts_index) |
| Воронка | 0–1 (provisional, bio URL only) |
| Лендинг | 0–1 (provisional, bio URL only) |
| Бот  лид-магнит | 0 (no bot source yet) |

---

## What fields are filled vs empty

### Описание профиля
- **Filled**: Конкурент, Ниша/продукт, Что вынесено в имя профиля, Описание профиля (bio), Главный CTA в bio, Куда ведет CTA
- **Filled if status=ok**: Для кого, Социальные доказательства
- **Always empty** (rule-based analysis too weak): Обещание результата, Позиционирование, Аргументы доверия

### Анализ хайлайтс
- **Filled for all 32**: Конкурент, Название highlight, Порядок (позиция)
- **Filled for Stage 5C analyzed highlights only (~3)**: Тема highlight, Задача highlight, Что внутри (кратко), Куда ведет CTA (если есть)
- **Always empty** (requires synthesis): Какая механика подачи хайлайтс

### Закрепленные посты
- **Filled**: Конкурент, Ссылка на пост, Позиция закрепа, Что в тексте поста (caption preview)
- **Empty** (no semantic analyzer built yet): all other semantic fields

### Воронка / Лендинг
- **Provisional only**: Конкурент, Точка входа, Первый шаг, Куда ведет / Ссылка на сайт
- **Warning attached**: destination type not classified; do not treat as final

### Бот  лид-магнит
- Headers only; no rows

---

## Security rules

- Do NOT call Google Sheets API
- Do NOT send payload.json to any external service
- Do NOT modify the Excel template
- Instagram CDN URLs are automatically redacted to `<instagram_cdn_redacted>`
- Long URLs are truncated to `scheme://host/...`

---

## Next step after reviewing outputs

Before writing to Google Sheets:
1. Review `output/stage5d1/csv/` — confirm rows look correct
2. Run Apps Script validate-only step to confirm header alignment (row 1 match)
3. Only then run write mode (separate task, requires explicit permission)

Before filling Воронка/Лендинг/Бот fully: run link destination classifier to determine where the bio URL actually leads.
