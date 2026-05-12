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

# normalize-only — перестроить outputs из существующего raw, Apify НЕ вызывается
# требует: data/raw/stage5b_auto_stories_raw.json (предыдущий реальный запуск)
python scripts/stage5b_auto_run_local.py --normalize-only

# просмотр результатов
cat report/stage_5b_auto_stories_report.md
cat data/normalized/stage5b_auto_stories_index.json
cat data/normalized/stage5b_auto_stories_summary.json
```

## Actor call

| Поле | Значение |
|---|---|
| Actor | automation-lab/instagram-stories-scraper |
| Calls per run | **1** (один вызов на весь запуск) |

Payload (точные ключи — не менять регистр):
```json
{
  "usernames":          ["vlada_kliuiko"],
  "sessionCookie":      "<from INSTAGRAM_SESSION_COOKIE env var>",
  "includeHighlights":  true,
  "maxHighlights":      3,
  "includeProfile":     false,
  "proxyConfiguration": {"useApifyProxy": true}
}
```

**Неправильные ключи, которые молча ломают запуск:**

| Неправильно | Правильно |
|---|---|
| `username` | `usernames` (массив) |
| `max_highlights` | `maxHighlights` |
| `include_highlights` | `includeHighlights` |
| `session_cookie` | `sessionCookie` |

## Dry-run ожидаемый вывод

```
=== Stage 5B-auto: DRY RUN ===
Actor:               automation-lab/instagram-stories-scraper
...
Payload shape (sanitized — no secrets printed):
  usernames:          list[str], length=1  ["vlada_kliuiko"]
  sessionCookie:      present / redacted
  includeHighlights:  true
  maxHighlights:      3
  includeProfile:     false
  proxyConfiguration: {useApifyProxy: true}
...
[DRY RUN] No Apify call made. No files written.
```

## Dataset validation (реальный запуск)

Скрипт упадёт с non-zero exit если:
- Apify статус SUCCEEDED, но dataset содержит 0 items
- `includeHighlights=true`, но 0 highlight story items в результате

## Normalization validation (реальный запуск и --normalize-only)

Скрипт упадёт с non-zero exit если:
- highlight stories count > 0 и **все** highlight mediaUrl = null
- более 10% normalized stories имеют null `id` (expected: `storyId`)
- более 10% normalized stories имеют null `mediaUrl`

## Mapping: automation-lab поля → normalized schema

| Raw поле (automation-lab) | Normalized поле | Примечание |
|---|---|---|
| `storyId` | `id` | |
| `mediaUrl` | `mediaUrl` | всегда сохраняется |
| `mediaType` | `mediaType` | `"Image"` или `"Video"` |
| `thumbnailUrl` | `thumbnailUrl` | |
| `mediaUrl` (если Image) | `imageUrl` | |
| `mediaUrl` (если Video) | `videoUrl` | |
| `null` (если Image) | `videoUrl` | |
| `null` (если Video) | `imageUrl` | |
| `timestamp` | `timestamp` | |
| `expiresAt` | `expiresAt` | |
| `durationSecs` | `durationSecs` | |
| `caption` | `caption` | |
| `isHighlight` | `isHighlight` | |
| `highlightId` | `highlightId` | сохраняется raw |
| `highlightTitle` | `highlightTitle` | secondary/raw |
| `hasLink` | `hasLink` | |
| `linkUrl` | `linkUrl` | |
| `stickerTypes` | `stickerTypes` | |
| `scrapedAt` | `scrapedAt` | |

**НЕ используй**: `id`, `imageUrl`, `videoUrl`, `displayUrl`, `type` — это старые/неправильные поля.

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
