# Stage 5B-2 — Highlight Stories Collector

## Что делает

Читает highlight IDs из `data/normalized/highlights_index.json` (созданного Stage 5B-1),
вызывает `igview-owner/instagram-highlights-stories-viewer` для каждого валидного ID
и сохраняет stories raw + normalized summary.

Создаёт:
- `data/raw/stage5b2_stories_{id}_raw.json` — raw stories на каждый highlight
- `data/normalized/stage5b2_highlights_stories_summary.json` — полный run summary
- `data/normalized/stage5b2_stories_index.json` — лёгкий индекс (position, id, title, status, count)
- `report/stage_5b2_highlights_stories_report.md` — human-readable отчёт

## Что НЕ делает

- не анализирует содержимое stories
- не скачивает media
- не запускает OpenAI
- не заполняет XLSX
- не меняет `actors_registry.json`

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`
- `data/normalized/highlights_index.json` — должен существовать (Stage 5B-1 завершён)

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# safety preview — показывает planned IDs и call count, Apify НЕ вызывается
python scripts/stage5b2_run_local.py --dry-run

# dry-run с лимитом (первые 5 highlights)
python scripts/stage5b2_run_local.py --dry-run --limit 5

# реальный запуск — все 32 highlights (32 actor calls)
python scripts/stage5b2_run_local.py

# реальный запуск — только первые 3 (для проверки)
python scripts/stage5b2_run_local.py --limit 3

# просмотр результатов
cat report/stage_5b2_highlights_stories_report.md
cat data/normalized/stage5b2_stories_index.json
cat data/normalized/stage5b2_highlights_stories_summary.json
```

## Actor call

| Поле | Значение |
|---|---|
| Actor | igview-owner/instagram-highlights-stories-viewer |
| Payload | `{"highlightId": "<numeric_id>"}` |
| Calls per run | = количество валидных highlights (до 32) |

ID normalization:
- убирает пробелы
- убирает `highlight:` префикс если есть
- проверяет, что ID числовой

## Выходные файлы

Все runtime — не коммитить:

```
data/raw/stage5b2_stories_{id}_raw.json                ← raw per highlight
data/normalized/stage5b2_highlights_stories_summary.json ← полный summary
data/normalized/stage5b2_stories_index.json              ← лёгкий индекс
report/stage_5b2_highlights_stories_report.md            ← human-readable report
```

## Статусы per highlight

| Status | Смысл |
|---|---|
| `OK` | Actor вернул >0 stories |
| `EMPTY_OR_INACCESSIBLE` | 0 stories — highlight пустой, удалён или недоступен |
| `FAIL` | Actor вернул ошибку |
| `INVALID_ID` | ID не числовой после нормализации |

## Важно: количество Apify calls

При запуске без `--limit` — до **32 actor calls** (по одному на каждый highlight).
Рекомендуется сначала проверить с `--limit 3`, затем запускать полный прогон.

## Следующий шаг

После Stage 5B-2:
- если `can_analyze_highlights: true` → Stage 5C: OpenAI Vision анализ highlights
- использовать `data/normalized/stage5b2_stories_index.json` для списка highlights
- raw stories в `data/raw/stage5b2_stories_{id}_raw.json`
