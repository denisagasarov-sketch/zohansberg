# Stage 5A-2C: Pinned Posts Caption Analyzer — Local Run Instructions

## What this stage does

Sends the full caption of each pinned post to OpenAI (text-only, no images).
Produces per-post semantic analysis for Google Sheets fields:
- Тема поста
- Почему закреплен *(always starts with "Вероятно" — inference, not fact)*
- Что в тексте поста
- Ключевые смыслы
- Какой CTA
- Куда ведет CTA
- Роль в воронке

**Does NOT:**
- Analyze images, covers, or carousel slides
- Do OCR
- Call Apify
- Write to Google Sheets
- Fill "Хук / первый экран" (left empty — requires Stage 5A-2D)
- Invent data not present in caption text

---

## Why this stage is needed

Stage 5A-2B collected full captions and confirmed `caption_semantic_possible`.
This stage extracts structured semantic meaning from caption text only.

Output feeds:
- **Stage 5D-1.1**: Update the Stage 5D-1 exporter to include semantic fields
- **Stage 5D-3 re-run**: Rewrite "Закрепленные посты" sheet with semantic data

---

## Prerequisites

| Requirement | File / env var |
|---|---|
| Stage 5A-2B output | `data/normalized/stage5a2b_pinned_posts_details.json` |
| OpenAI API key | `OPENAI_API_KEY` in `.env` |
| openai Python package | `pip install openai` |

---

## Running locally

### 1. Dry-run (always first)

```bash
cd instagram_research_test
python3 scripts/stage5a2c_run_local.py --dry-run
```

Prints:
- 3 posts to analyze (caption lengths, readiness flags)
- Cost estimate
- Field constraints (cell limits, allowed Роль/CTA values)
- Prompt preview (first post, first 15 lines)
- OPENAI_API_KEY presence (value never printed)
- Planned output paths

### 2. Run analysis

```bash
set -a; source .env; set +a
python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10
```

`--budget-max-usd` is a required safety parameter (default 1.00).
Analysis will abort if estimated cost exceeds this limit.

Results are cached per post by (post_id, caption hash, model, prompt version).
Repeated runs reuse cache at zero cost.

### 3. Force re-analysis (bypass cache)

```bash
python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 0.10 --force
```

### 4. Use a different model

```bash
python3 scripts/stage5a2c_run_local.py --analyze --budget-max-usd 1.00 --model gpt-4o
```

### 5. Generate report from existing output

```bash
python3 scripts/stage5a2c_run_local.py --create-report
```

### 6. Validate existing output (read-only)

```bash
python3 scripts/stage5a2c_run_local.py --validate-existing-output
```

Reads existing semantic and GS rows JSON, runs all validation checks and
deterministic postprocessing to detect any issues. No OpenAI calls. No files written.

### 7. Validate and write corrected copies

```bash
python3 scripts/stage5a2c_run_local.py --validate-existing-output --write-fixed
```

If postprocessing fixes are needed, writes corrected output to `_fixed.json` variants.
Original files are preserved.

```bash
python3 scripts/stage5a2c_run_local.py --validate-existing-output --write-fixed --overwrite
```

Overwrites original files with fixed versions.

### 8. Run regression checks only

```bash
python3 scripts/stage5a2c_run_local.py --regression-checks
```

Runs 44 deterministic tests on CTA validation, destination normalization, role
normalization, and postprocessing. No files. No external calls.

---

## Output files

All runtime outputs are gitignored.

| File | Description |
|---|---|
| `data/normalized/stage5a2c_pinned_posts_semantic.json` | Per-post semantic analysis with confidence, evidence, postprocessing_notes |
| `data/normalized/stage5a2c_pinned_posts_google_sheet_rows.json` | GS-ready rows for "Закрепленные посты" |
| `data/normalized/stage5a2c_pinned_posts_semantic_fixed.json` | Fixed copy (written by --write-fixed) |
| `data/normalized/stage5a2c_pinned_posts_google_sheet_rows_fixed.json` | Fixed GS rows copy |
| `analysis/stage5a2c_cache/<key>.json` | Cache keyed by (post_id, model, prompt_version, caption_sha256) |
| `report/stage_5a2c_pinned_posts_caption_analysis_report.md` | Human-readable analysis report |

---

## Field rules enforced by this stage

| Field | Rule |
|---|---|
| Тема поста | Max 160 chars |
| Почему закреплен | Must start with "Вероятно"; evidence-based; auto-prepended if missing |
| Хук / первый экран | **Always empty** — visual/OCR not done in this stage |
| Что в тексте поста | Max 350 chars |
| Ключевые смыслы | Max 500 chars |
| Какой CTA | Must contain explicit action verb (пишите/оставьте/переходите/etc.); cleared if invalid |
| Куда ведет CTA | Composite paths allowed: `директ / комментарии → анкета предзаписи → закрытый канал`; atoms validated |
| Роль в воронке | Composite allowed: `доверие / прогрев`; atoms validated against allowed list |

### CTA validity rules

A CTA is valid only if it contains a **strong imperative action verb**:
`пишите`, `напишите`, `оставьте`, `переходите`, `перейдите`, `заполните`,
`регистрируйтесь`, `отправьте`, `забронируйте`, `подпишитесь`, `нажмите`,
`запишитесь`, `приходите`, `получите доступ`

**Not valid CTA:** thesis, teaser, forecast, insight, spójler, или вопрос.

Invalid examples (auto-cleared by postprocessing):
- `Спойлер: в 2026 году...`
- `как прогнозировать результаты`
- `получите ссылку на анкету` *(weak verb only, no strong action)*

### CTA destination atoms

Allowed atoms: `директ` | `комментарии` | `био-ссылка` | `анкета` | `анкета предзаписи` |
`закрытый канал` | `консультация` | `курс` | `сайт` | `бот` | `unknown`

Composite path: `"директ / комментарии → анкета предзаписи → закрытый канал"`
- `/` = parallel channels
- `→` = sequential steps
- Mixed input (`|`, `->`) is auto-normalized

### Funnel role atoms

Allowed: `знакомство` | `доверие` | `прогрев` | `продажа` | `лидогенерация`

Composite: `"доверие / прогрев"`, `"доверие / лидогенерация"`, `"прогрев / лидогенерация"`

---

## Cache system

Cache key: `{post_id}__{model}__pv{prompt_version}__{caption_sha256[:16]}.json`

Only `"status": "analyzed"` results are cached. Failed/skipped results are not cached.

If caption changes (after a Stage 5A-2B re-run with new data), the cache miss is automatic.

---

## Model and cost

| Model | Est. cost per post | Notes |
|---|---|---|
| `gpt-4o-mini` *(default)* | ~$0.0004 | 3 posts ≈ $0.0012 |
| `gpt-4o` | ~$0.008 | Higher quality, 20× cost |

---

## What is NOT done in this stage

- No image analysis (Stage 5A-2D)
- No Apify calls
- No Google Sheets reads or writes
- No "Хук / первый экран" fill
- No invented data (fields left empty if not supported by caption)

---

## Recommended run order

1. `--dry-run` → verify posts detected, check readiness flags
2. `--analyze --budget-max-usd 0.10` → run analysis
3. `--create-report` → review semantic output
4. If satisfied → proceed to Stage 5D-1.1 (exporter update)
5. If "Хук / первый экран" needed → proceed to Stage 5A-2D

---

## Limitations

- Analysis quality depends on caption text completeness.
  If `caption_semantic_possible=False` (caption ≤300 chars), results may be partial.
- "Почему закреплен" is always inference — labeled with "Вероятно" prefix.
- "Хук / первый экран" will remain empty until Stage 5A-2D (visual/OCR).
- CTA destination is validated against a closed list; novel destinations will be set to `unknown`.
