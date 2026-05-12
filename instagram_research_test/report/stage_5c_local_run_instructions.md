# Stage 5C — Story Content Analyzer (OpenAI Vision)

## Что делает

Читает `data/normalized/stage5b_auto_stories_index.json` (Stage 5B-auto).
Отправляет story images в OpenAI Vision для контентной классификации.
Один OpenAI вызов на story (не на highlight).

Создаёт:
- `data/raw/stage5c_cache/` — per-story кеш (не коммитить)
- `data/normalized/stage5c_stories_analysis.json` — все результаты (не коммитить)
- `data/normalized/stage5c_highlights_summary.json` — aggregate по highlights (не коммитить)
- `report/stage_5c_analysis_report.md` — competitor analysis отчёт (не коммитить)

## Что НЕ делает

- не запускает Apify
- не скачивает media файлы
- не делает XLSX (Stage 5D)
- не меняет `actors_registry.json`
- для video использует `thumbnailUrl`, не скачивает видео

## Требования

- Python 3.11+
- `pip install openai python-dotenv requests`
- `.env` с:
  ```
  OPENAI_API_KEY=sk-...
  ```
- `data/normalized/stage5b_auto_stories_index.json` — Stage 5B-auto завершён
- `data/normalized/highlights_index.json` — Stage 5B-1 завершён (canonical titles)

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# dry-run — OpenAI не вызывается, показывает план и cost estimate
python scripts/stage5c_run_local.py \
  --dry-run \
  --max-stories-per-highlight 5 \
  --budget-max-usd 1.00

# реальный запуск — 5 stories per highlight, spread selection
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

## Обязательные флаги

| Флаг | Тип | Описание |
|---|---|---|
| `--max-stories-per-highlight N` | int ≥ 1 | сколько stories брать из каждого highlight |
| `--budget-max-usd X` | float > 0 | жёсткий лимит бюджета в USD |

Запуск без этих флагов падает с ошибкой.

## Опциональные флаги

| Флаг | По умолчанию | Варианты |
|---|---|---|
| `--selection-mode` | `spread` | `first` / `last` / `spread` |
| `--model` | `gpt-4o-mini` | `gpt-4o` (дороже, точнее) |
| `--detail` | `low` | `high` (лучше OCR) |
| `--highlight-ids` | все | `id1,id2,...` через запятую |
| `--force` | false | пересчитать даже если в кеше |
| `--dry-run` | false | показать план без вызовов |

## Оценка стоимости

| Model | Detail | Цена / story (est.) |
|---|---|---|
| gpt-4o-mini | low | ~$0.0015 |
| gpt-4o-mini | high | ~$0.006 |
| gpt-4o | low | ~$0.018 |
| gpt-4o | high | ~$0.055 |

Рекомендация: начать с `gpt-4o-mini --detail low --max-stories-per-highlight 5`.
Для 3 highlights × 5 stories = 15 calls ≈ $0.02.

## Budget guard

- `--budget-max-usd` проверяется перед каждым вызовом OpenAI
- при достижении лимита: run останавливается мягко (не ошибка)
- уже проанализированные stories сохраняются в кеш
- повторный запуск продолжит с незакешированных stories

## Кеш

Cache key = `story_id + model + detail + prompt_version`.

```
data/raw/stage5c_cache/{story_id}__{model}__{detail}__pv{PROMPT_VERSION}.json
```

- Кеш используется автоматически — повторный запуск не тратит бюджет на уже обработанные stories.
- `--force` инвалидирует кеш (пересчитывает).
- При смене `--model`, `--detail` или при обновлении `PROMPT_VERSION` — новый кеш.

## URL check

Перед каждым OpenAI вызовом скрипт проверяет доступность URL через HTTP HEAD.
Instagram CDN URLs истекают через ~24–48 часов.

| Причина skip | Значение |
|---|---|
| `no_url` | поле imageUrl/thumbnailUrl пустое |
| `http_403` | URL истёк или заблокирован |
| `http_404` | URL не существует |
| `error_ConnectionError` | сетевая ошибка |

Если много skips → повторить Stage 5B-auto для получения свежих URLs, затем Stage 5C.

## Selection modes

| Mode | Смысл |
|---|---|
| `spread` | равномерно распределённые индексы по всему highlight |
| `first` | первые N stories |
| `last` | последние N stories |

`spread` рекомендуется — даёт репрезентативную выборку arc (начало → середина → конец).

## Grouping

Группировка **только по `highlight_id`**, не по `highlightTitle`.
`highlightTitle` от automation-lab ненадёжен (несколько highlights могут иметь одно название).
Canonical title берётся из `highlights_index.json` (singhera07).

## Video stories

Для `mediaType == "Video"` используется `thumbnailUrl`.
Видео не скачивается. Если `thumbnailUrl` недоступен — story пропускается с причиной.

## Taxonomy: content_type

| Значение | Смысл |
|---|---|
| `student_review` | отзыв студента/клиента |
| `case_result` | конкретный результат (цифры, before/after) |
| `sales_offer` | коммерческое предложение, цена |
| `webinar_event` | анонс вебинара или мероприятия |
| `lead_magnet` | бесплатный продукт, гайд, чек-лист |
| `objection_handling` | снятие возражений |
| `authority_proof` | экспертность, СМИ, регалии |
| `process_demo` | демонстрация процесса работы |
| `educational` | обучающий контент |
| `personal_positioning` | личный бренд, история, ценности |
| `community_social_proof` | сообщество, количество учеников |
| `lifestyle` | образ жизни, не продающий |
| `cta_only` | только призыв к действию |
| `other` | не подходит ни под одну категорию |

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
| `none` | некоммерческое содержание |

## Выходные файлы (runtime — не коммитить)

```
data/raw/stage5c_cache/                          ← per-story cache
data/normalized/stage5c_stories_analysis.json    ← все результаты
data/normalized/stage5c_highlights_summary.json  ← aggregate по highlights
report/stage_5c_analysis_report.md               ← competitor report
```

## Следующий шаг

После Stage 5C:
- Stage 5D: XLSX — использовать `stage5c_highlights_summary.json` для competitive table
- Ключевые поля для таблицы: `dominant_content_type`, `commercial_role_distribution`,
  `cta_rate`, `common_tags`, `extracted_ctas`
