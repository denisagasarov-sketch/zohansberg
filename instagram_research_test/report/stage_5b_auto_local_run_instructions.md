# Stage 5B-auto — Highlight Stories Collector (automation-lab)

## Что делает

Вызывает `automation-lab/instagram-stories-scraper` **одним Apify вызовом**
(не по одному на каждый highlight, в отличие от deprecated igview-owner).

Возвращает:
- **active stories** — stories из ленты профиля (последние 24 ч)
- **highlight stories** — archived stories, сгруппированные по `highlightId`

Canonical title/position/cover присоединяется из
`data/normalized/highlights_index.json` (Stage 5B-1, singhera07).
`highlightTitle` от automation-lab сохраняется как вторичное/raw поле.

Создаёт:
- `data/raw/stage5b_auto_stories_raw.json` — raw actor output
- `data/normalized/stage5b_auto_stories_summary.json` — run summary
- `data/normalized/stage5b_auto_stories_index.json` — grouped index
- `report/stage_5b_auto_stories_report.md` — human-readable отчёт

## Что НЕ делает

- не использует `igview-owner` (deprecated)
- не анализирует содержимое stories
- не скачивает media
- не запускает OpenAI
- не заполняет XLSX
- не меняет `actors_registry.json`

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- `.env` с обоими значениями:
  ```
  APIFY_TOKEN=apify_api_...
  INSTAGRAM_SESSION_COOKIE=<значение сессионной куки>
  ```
- `data/normalized/highlights_index.json` — должен существовать (Stage 5B-1 завершён)

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# dry-run — Apify не вызывается, показывает planned highlights + cost estimate
python scripts/stage5b_auto_run_local.py --dry-run --max-highlights 3

# реальный запуск — первые 3 highlights
python scripts/stage5b_auto_run_local.py --max-highlights 3

# реальный запуск — все 32 highlights
python scripts/stage5b_auto_run_local.py --max-highlights 32

# просмотр результатов
cat report/stage_5b_auto_stories_report.md
cat data/normalized/stage5b_auto_stories_index.json
cat data/normalized/stage5b_auto_stories_summary.json
```

## Actor call

| Поле | Значение |
|---|---|
| Actor | automation-lab/instagram-stories-scraper |
| Payload | `{"username": "vlada_kliuiko", "maxHighlights": N, "sessionCookie": "<from .env>"}` |
| Calls per run | **1** (один вызов на весь запуск) |

## ВАЖНО: cost warning

**Актор automation-lab тарифицируется per story item.**

| maxHighlights | Грубая оценка items |
|---|---|
| 3 | ~180–200 |
| 10 | ~500–700 |
| 32 | ~1500–2000+ |

Всегда указывай `--max-highlights`. Запуск без флага запрещён скриптом.
Начинай с `--max-highlights 3`, затем увеличивай.

## Нормализация highlightId

- automation-lab возвращает `highlightId` в формате `highlight:17874797856565339`
- скрипт стрипает `highlight:` префикс → `17874797856565339`
- join с canonical index по bare ID (без префикса)

## highlightTitle — вторичное поле

`highlightTitle` от automation-lab **не надёжен** (подтверждено тестом):
- тест с 3 highlights вернул только 2 уникальных названия на 3 highlight_id
- используется только как `automation_lab_title` (справочно)
- canonical title/position/cover берётся из singhera07 highlights_index

## Архитектура (финальная)

| Actor | Роль |
|---|---|
| `apify/instagram-scraper` | profile, bio, pinned posts |
| `singhera07/instagram-scraper` | canonical highlights index |
| `automation-lab/instagram-stories-scraper` | highlight stories content |
| `igview-owner/instagram-highlights-stories-viewer` | deprecated fallback — не использовать |

## Выходные файлы (runtime — не коммитить)

```
data/raw/stage5b_auto_stories_raw.json              ← raw actor output
data/normalized/stage5b_auto_stories_summary.json   ← run summary
data/normalized/stage5b_auto_stories_index.json     ← grouped index с canonical metadata
report/stage_5b_auto_stories_report.md              ← human-readable report
```

## Следующий шаг

После Stage 5B-auto:
- если `can_analyze_highlights: true` → Stage 5C: OpenAI Vision анализ highlights
- использовать `data/normalized/stage5b_auto_stories_index.json`
  (поле `highlights[].stories` содержит imageUrl/videoUrl для каждой story)
