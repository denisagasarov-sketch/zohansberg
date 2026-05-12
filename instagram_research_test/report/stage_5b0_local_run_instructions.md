# Stage 5B-0 — Highlight ID Compatibility Check

## Что делает

Проверяет, совместимы ли highlight IDs из `singhera07/instagram-scraper`
с actor `igview-owner/instagram-highlights-stories-viewer`.

Тестирует 2 ID:
- `17874797856565339` — control (ранее вернул 57 stories)
- `18110898391654002` — candidate из highlights index scraper

Для каждого ID:
- нормализует ID (убирает пробелы, убирает `highlight:` префикс если есть)
- проверяет, что ID числовой
- вызывает actor один раз
- считает stories_count
- проверяет наличие ключевых полей (`imageUrl`, `videoUrl` и др.)
- сохраняет raw output и normalized summary

## Что НЕ делает

- не анализирует все highlights
- не скачивает media
- не вызывает OpenAI
- не заполняет XLSX

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# safety preview, без Apify calls
python scripts/stage5b0_check_highlight_id_compatibility.py --dry-run

# real compatibility check — 2 actor calls
python scripts/stage5b0_check_highlight_id_compatibility.py

cat data/normalized/stage5b0_highlight_id_compatibility_summary.json
```

## Выходные файлы

```
data/raw/stage5b0_highlight_17874797856565339_raw.json   ← не коммитить
data/raw/stage5b0_highlight_18110898391654002_raw.json   ← не коммитить
data/normalized/stage5b0_highlight_id_compatibility_summary.json  ← коммитить
```

## Как интерпретировать результат

**`compatibility_verdict`:**

| Verdict | Значение |
|---|---|
| `compatible` | Оба ID вернули stories с media URLs — actor pair совместим |
| `partially_compatible` | Control работает, candidate нет — проблема в конкретном highlight, не в actor |
| `not_compatible` | Control тоже не работает — сначала проверить actor/token/network |
| `dry_run` | Запуск с `--dry-run` — Apify не вызывался |

**`can_build_stage5b`:**
- `true` — можно строить Stage 5B на этом actor pair
- `"conditional"` — viewer работает, но нужно проверить больше candidate IDs
- `false` — не строить пока не починить control ID

**Статусы по каждому ID:**

| Status | Значение |
|---|---|
| `OK` | Actor вернул >0 stories |
| `EMPTY_OR_INACCESSIBLE` | Actor завершился без ошибки, но 0 stories — highlight пустой/удалён/недоступен |
| `FAIL` | Actor вернул ошибку |
| `INVALID_ID` | ID не числовой — actor не вызывался |
| `DRY_RUN` | Запуск с `--dry-run` |

**Если control ID не работает:**
Не делать вывод о candidate ID. Control ранее возвращал 57 stories —
если сейчас падает, проблема в текущем запуске (actor/token/network).
Сначала починить control, потом проверять candidate.

**Если control работает, candidate не работает:**
Viewer actor рабочий. Проблема в конкретном highlight (пустой/удалён/недоступен)
или формате ID. Рекомендуется проверить 2–3 дополнительных candidate IDs.

## Следующий шаг

После Stage 5B-0:
- `compatible` → строить Stage 5B (highlights analysis)
- `partially_compatible` → протестировать ещё 2–3 candidate IDs
- `not_compatible` → проверить actor/token, повторить control test
