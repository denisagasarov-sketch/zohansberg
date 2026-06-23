# Stage 5A-1 — Profile + Pinned Index Collector

## Что делает

Собирает структурированные JSON для листов "Описание профиля" и "Закрепленные посты":

- **profile_summary.json** — все профильные поля (username, full_name, bio_text, external_url, counts)
- **bio_analysis.json** — rule-based анализ bio (cta_text, social_proof, niche и др.)
- **pinned_posts_index.json** — список закреплённых постов из первых 30 публикаций
- **stage5a_summary.json** — coverage summary по листам XLSX

## Что НЕ делает

- не анализирует highlights
- не анализирует landing
- не заполняет XLSX
- не запускает OpenAI
- не скачивает media
- не использует resultsType=profiles

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# Safety preview — Apify НЕ вызывается
python scripts/stage5a1_run_local.py --dry-run

# Реальный запуск — 2 actor calls
python scripts/stage5a1_run_local.py

# Просмотр результатов
cat report/stage_5a1_profile_pinned_report.md
cat data/normalized/profile_summary.json
cat data/normalized/bio_analysis.json
cat data/normalized/pinned_posts_index.json
cat data/normalized/stage5a_summary.json
```

## Actor calls

| # | Actor | resultsType | Цель |
|---|---|---|---|
| 1 | apify/instagram-scraper | details | profile fields (bio, url, counts) |
| 2 | apify/instagram-scraper | posts | isPinned detection (limit 30) |

`resultsType=profiles` не используется — подтверждено Stage 5A-0, что не поддерживается.

## Выходные файлы

```
data/raw/stage5a1_profile_details_raw.json      ← в .gitignore, не коммитить
data/raw/stage5a1_posts_for_pinned_raw.json     ← в .gitignore, не коммитить
data/normalized/profile_summary.json            ← коммитить
data/normalized/bio_analysis.json               ← коммитить
data/normalized/pinned_posts_index.json         ← коммитить
data/normalized/stage5a_summary.json            ← коммитить
report/stage_5a1_profile_pinned_report.md       ← коммитить
```

## Как интерпретировать результат

**data_status:**
- `ok` — поле напрямую из actor output, уверенно
- `partial` — rule-based inference, требует проверки
- `missing` — actor не вернул, неизвестно как получить
- `manual_needed` — actor не вернул, можно ввести вручную

**bio_analysis.json** — это rule-based, не OpenAI. Все интерпретационные поля (`niche`, `target_audience`, `result_promise`, `positioning`) будут `partial` или `manual_needed`. Это нормально.

**pinned_posts_index.json:**
- `detection_method: actor_field` — actor вернул `isPinned`, используется автоматически
- `detection_method: not_detected` — `isPinned` не найден, нужен `data/input/pinned_posts_manual.json`
- `pinned_count = 0, manual_needed = true` — `isPinned` есть, но ни один пост не закреплён в первых 30

**stage5a_summary.json:**
- `can_fill_profile_sheet: ok|partial|missing`
- `can_fill_pinned_posts_sheet: ok|partial|manual_needed|missing`
- `can_run_stage5b: false` — пока не собран highlights index
- `can_run_stage5d: false` — пока не собран landing/funnel

## Следующий шаг

После Stage 5A-1:
1. Проверить `bio_analysis.json` — при необходимости заполнить `manual_needed` поля вручную
2. Если `pinned_posts_status: manual_needed` → заполнить `data/input/pinned_posts_manual.json`
3. Если `pinned_posts_status: manual_needed` → заполнить `data/input/highlights_manual.json`
4. → Stage 5B: highlights analysis
