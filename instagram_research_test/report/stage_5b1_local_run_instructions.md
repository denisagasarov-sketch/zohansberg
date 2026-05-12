# Stage 5B-1 — Highlights Index Collector

## Что делает

Собирает список highlights профиля `vlada_kliuiko` через `singhera07/instagram-scraper`.

Payload берётся из `config/actors_registry.json` — не хардкодится отдельно.

Главный вопрос: ведёт ли `limit=12` к ограничению вывода,
если ранее actor возвращал 32 highlights?

Создаёт:
- `data/normalized/highlights_index.json` — список highlights для Stage 5B-2
- `data/normalized/stage5b1_highlights_index_summary.json` — run summary с limit_behavior
- `report/stage_5b1_highlights_index_report.md` — человекочитаемый отчёт

## Что НЕ делает

- не собирает stories по highlights
- не скачивает media
- не запускает OpenAI
- не анализирует содержание highlights
- не заполняет XLSX
- не меняет `actors_registry.json`

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`
- `config/actors_registry.json` с записью для `singhera07/instagram-scraper`

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# safety preview — Apify НЕ вызывается
python scripts/stage5b1_run_local.py --dry-run

# реальный запуск — 1 actor call
python scripts/stage5b1_run_local.py

cat report/stage_5b1_highlights_index_report.md
cat data/normalized/highlights_index.json
cat data/normalized/stage5b1_highlights_index_summary.json
```

## Actor call

| Поле | Значение |
|---|---|
| Actor | singhera07/instagram-scraper |
| Payload source | config/actors_registry.json → confirmed_actions.highlights.safe_input_payload_example |
| planned_apify_calls | 1 |

Payload из registry:
```json
{
  "action": "highlights",
  "limit": 12,
  "username": "vlada_kliuiko"
}
```

## Выходные файлы

Все runtime — не коммитить:

```
data/raw/stage5b1_highlights_index_raw.json           ← raw actor output
data/normalized/highlights_index.json                  ← normalized highlights list
data/normalized/stage5b1_highlights_index_summary.json ← run summary
report/stage_5b1_highlights_index_report.md            ← human-readable report
```

## Как интерпретировать limit_behavior

| Значение | Смысл |
|---|---|
| `likely_limited` | Вернулось ровно 12 при user-reported 32 — limit, вероятно, ограничивает |
| `likely_not_limited` | Вернулось больше 12 — limit не ограничивает |
| `unclear` | Actor упал или 0 items — невозможно определить |

Если `likely_limited`:
- не запускать второй call с большим limit без явного подтверждения пользователя
- зафиксировать наблюдение в report и дождаться решения

## Как интерпретировать can_run_stage5b2

| Значение | Смысл |
|---|---|
| `true` | highlights_with_id > 0, статус OK или PARTIAL — Stage 5B-2 можно запускать |
| `false` | нет highlights с id, или actor FAIL — Stage 5B-2 заблокирован |

## Следующий шаг

После Stage 5B-1:
- если `can_run_stage5b2: true` → Stage 5B-2: собрать stories по каждому highlight_id
- если `limit_behavior: likely_limited` → согласовать с пользователем тест с большим limit
- если `can_run_stage5b2: false` → исправить ошибки, проверить actor/token
