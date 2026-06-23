# Stage 5C — Story Content Analyzer (OpenAI Vision)

## Что делает

Читает `data/normalized/stage5b_auto_stories_index.json` (Stage 5B-auto).
Анализирует story images через OpenAI Vision (gpt-4o-mini по умолчанию).

**Важно: медиа передаётся через base64, не через CDN URL.**
Instagram CDN URLs нельзя передавать напрямую в OpenAI — они возвращают
`invalid_image_url`. Скрипт скачивает bytes в память и конвертирует в
`data:image/jpeg;base64,...` перед отправкой в OpenAI.

Создаёт:
- `data/raw/stage5c_cache/` — per-story кеш (не коммитить)
- `data/normalized/stage5c_stories_analysis.json` — все результаты (не коммитить)
- `data/normalized/stage5c_highlights_summary.json` — aggregate (не коммитить)
- `report/stage_5c_analysis_report.md` — competitor analysis отчёт (не коммитить)

## Что НЕ делает

- не запускает Apify
- не сохраняет media файлы на диск
- не скачивает mp4/video — для Video использует thumbnailUrl
- не делает XLSX (Stage 5D)
- не меняет `actors_registry.json`

## Требования

- Python 3.11+
- `pip install openai python-dotenv requests`
- `.env` с:
  ```
  OPENAI_API_KEY=sk-...
  INSTAGRAM_SESSION_COOKIE=<сессионная кука — для retry на 401/403>
  ```
- `data/normalized/stage5b_auto_stories_index.json` — Stage 5B-auto завершён
- `data/normalized/highlights_index.json` — Stage 5B-1 завершён

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# test media fetch — проверить что URLs доступны, без OpenAI
python scripts/stage5c_run_local.py \
  --test-media-fetch \
  --max-stories-per-highlight 1

# dry-run — план вызовов, cost estimate, без OpenAI
python scripts/stage5c_run_local.py \
  --dry-run \
  --max-stories-per-highlight 5 \
  --budget-max-usd 1.00

# реальный запуск — 5 stories per highlight, spread
python scripts/stage5c_run_local.py \
  --max-stories-per-highlight 5 \
  --budget-max-usd 1.00

# только конкретные highlights
python scripts/stage5c_run_local.py \
  --max-stories-per-highlight 10 \
  --budget-max-usd 2.00 \
  --highlight-ids 17874797856565339,18110898391654002

# high detail (лучше OCR, ~3-4x дороже)
python scripts/stage5c_run_local.py \
  --max-stories-per-highlight 5 \
  --budget-max-usd 2.00 \
  --detail high

# force re-analyze (игнорировать кеш)
python scripts/stage5c_run_local.py \
  --max-stories-per-highlight 5 \
  --budget-max-usd 1.00 \
  --force

# просмотр результатов
cat report/stage_5c_analysis_report.md
cat data/normalized/stage5c_highlights_summary.json
```

## Media input: base64 (по умолчанию)

```
Instagram CDN URL
      ↓
fetch bytes in-memory (requests + browser headers)
      ↓  если 401/403 → retry с INSTAGRAM_SESSION_COOKIE
validate: HTTP 200, content-type = image/*, size ≤ 8 MB
      ↓
base64 encode
      ↓
data:image/jpeg;base64,... → OpenAI Vision
```

Медиа **не записывается на диск**. Только cache JSON (без image bytes).

## Почему не direct URL

Instagram CDN URLs подписаны и ограничены по IP/User-Agent.
OpenAI не может их скачать — возвращает `invalid_image_url`.
Флаг `--allow-direct-url-mode` существует только для тестирования —
**не использовать в production**.

## Обязательные флаги

| Флаг | Описание |
|---|---|
| `--max-stories-per-highlight N` | количество stories из каждого highlight |
| `--budget-max-usd X` | жёсткий лимит USD (кроме `--dry-run` и `--test-media-fetch`) |

## Опциональные флаги

| Флаг | По умолчанию | Варианты |
|---|---|---|
| `--selection-mode` | `spread` | `first` / `last` / `spread` |
| `--model` | `gpt-4o-mini` | `gpt-4o` |
| `--detail` | `low` | `high` |
| `--highlight-ids` | все | `id1,id2,...` |
| `--force` | false | пересчитать даже если в кеше |
| `--test-media-fetch` | false | тест fetch без OpenAI |
| `--dry-run` | false | план без вызовов |
| `--allow-direct-url-mode` | false | не использовать |

## --test-media-fetch

Без OpenAI, без записи файлов. Проверяет:
- одну Image story (через imageUrl)
- одну Video story (через thumbnailUrl)

Выводит: story_id, highlight_id, mediaType, bytes, content_type, data_url prefix.
Не выводит полный URL.

Запускать перед первым реальным запуском для проверки доступности URLs.

## Оценка стоимости

| Model | Detail | Цена / story (est.) |
|---|---|---|
| gpt-4o-mini | low | ~$0.0015 |
| gpt-4o-mini | high | ~$0.006 |
| gpt-4o | low | ~$0.018 |
| gpt-4o | high | ~$0.055 |

Рекомендация: начать с `gpt-4o-mini --detail low --max-stories-per-highlight 5`.
3 highlights × 5 = 15 calls ≈ $0.02.

## Budget guard

- `--budget-max-usd` проверяется перед каждым OpenAI вызовом
- при достижении лимита: run останавливается мягко, не ошибка
- уже обработанные stories сохранены в кеш
- повторный запуск продолжит с незакешированных

## Кеш

Cache key = `story_id + model + detail + image_input_mode + prompt_version`.

```
data/raw/stage5c_cache/{story_id}__{model}__{detail}__{mode}__pv{VERSION}.json
```

- Только `analyzed` результаты сохраняются и используются из кеша.
- `openai_error`, `skipped_*` — **не кешируются** (будут повторены при следующем запуске).
- `--force` игнорирует кеш полностью.
- Смена `--model`, `--detail` или `--allow-direct-url-mode` = другой ключ кеша.
- Старые ошибки с `direct_url` mode **не мешают** новым base64 запускам.

## Статусы stories

| Status | Смысл |
|---|---|
| `analyzed` | OpenAI вернул анализ — сохранён в кеш |
| `skipped_no_url` | поле imageUrl/thumbnailUrl пустое |
| `skipped_media_fetch_failed` | HTTP ошибка или сетевой timeout |
| `skipped_invalid_content_type` | ответ не image/* |
| `skipped_media_too_large` | > 8 MB |
| `openai_error` | OpenAI API вернул ошибку — не кешируется |

## Если много skipped_media_fetch_failed

Instagram CDN URLs истекают через ~24–48 часов.
1. Повторить Stage 5B-auto — получить свежие URLs.
2. Запустить Stage 5C с `--force` для stories со старыми URLs.

## Grouping

Группировка **только по `highlight_id`**, не по названию.
Canonical title/position берётся из `highlights_index.json` (singhera07).

## Video stories

`mediaType == "Video"` → используется `thumbnailUrl`.
Видео не скачивается. Если `thumbnailUrl` недоступен → `skipped_media_fetch_failed`.

## Taxonomy: content_type

| Значение | Смысл |
|---|---|
| `student_review` | отзыв студента/клиента |
| `case_result` | результат (цифры, before/after) |
| `sales_offer` | коммерческое предложение |
| `webinar_event` | анонс вебинара/события |
| `lead_magnet` | бесплатный продукт/гайд |
| `objection_handling` | снятие возражений |
| `authority_proof` | экспертность, СМИ, регалии |
| `process_demo` | демонстрация процесса |
| `educational` | обучающий контент |
| `personal_positioning` | личный бренд |
| `community_social_proof` | сообщество, количество учеников |
| `lifestyle` | образ жизни |
| `cta_only` | только призыв к действию |
| `other` | не классифицировано |

## Taxonomy: commercial_role

| Значение | Смысл |
|---|---|
| `proof` | доказательство результата |
| `offer` | прямое предложение купить |
| `trust` | построение доверия |
| `objection` | снятие возражений |
| `education` | обучение и ценность |
| `activation` | призыв к немедленному действию |
| `navigation` | направление по воронке |
| `identity` | формирование образа эксперта |
| `none` | некоммерческое |

## Выходные файлы (runtime — не коммитить)

```
data/raw/stage5c_cache/                          ← per-story кеш
data/normalized/stage5c_stories_analysis.json    ← все результаты
data/normalized/stage5c_highlights_summary.json  ← aggregate
report/stage_5c_analysis_report.md               ← competitor report
```

## Следующий шаг

Stage 5D (XLSX):
- использовать `stage5c_highlights_summary.json`
- ключевые поля: `dominant_content_type`, `commercial_role_distribution`,
  `cta_rate`, `common_tags`, `extracted_ctas`
