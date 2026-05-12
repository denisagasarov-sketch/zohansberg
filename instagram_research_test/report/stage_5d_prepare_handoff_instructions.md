# Stage 5D Prepare Handoff — Local Run Instructions

## Что делает

Собирает sanitized handoff bundle для планирования Stage 5D.
Читает Excel-шаблон, ТЗ и pipeline outputs локально.
Не вызывает OpenAI, Apify, Telegram или любые внешние сервисы.
Не трогает `.env`. Не коммитит ничего.

## Требования

- Python 3.11+
- `pip install openpyxl python-dotenv`
- Рабочий каталог: `instagram_research_test/`
- (Опционально) Excel-шаблон `Competitor_Analysis_Template.xlsx`
- (Опционально) ТЗ `.md` файл в корне или поддиректориях

## Команды

```bash
cd /путь/к/zohansberg-instagram-test/instagram_research_test

# dry-run — показать что будет создано, ничего не писать
python scripts/stage5d_prepare_handoff.py --dry-run

# реальный запуск с автопоиском Excel и ТЗ
python scripts/stage5d_prepare_handoff.py

# явно указать Excel и ТЗ (если автопоиск не нашёл)
python scripts/stage5d_prepare_handoff.py \
  --excel-file ../Competitor_Analysis_Template.xlsx \
  --tz-file ../ТЗ_competitor_analysis.md

# посмотреть результат
cat handoff/stage5d_handoff/BUNDLE_README.md
cat handoff/stage5d_handoff/stage_proof_summary.md
cat handoff/stage5d_handoff/competitor_analysis_template_schema.md
```

## Что создаётся

```
handoff/stage5d_handoff/
  BUNDLE_README.md                          ← индекс bundle
  git_state.md                              ← ветка, статус, коммиты
  file_inventory.md                         ← дерево файлов проекта
  competitor_analysis_template_schema.json  ← структура Excel (все листы/столбцы)
  competitor_analysis_template_schema.md    ← читаемая версия
  competitor_analysis_tz.md                 ← sanitized ТЗ
  pipeline_output_summaries.json           ← краткие выводы из normalized данных
  pipeline_output_summaries.md             ← читаемая версия
  stage_proof_summary.md                   ← что доказано/проверено
```

## Что НЕ создаётся / НЕ копируется

- `.env` и любые API ключи
- `data/raw/`, `data/normalized/`, `analysis/`, `output/`
- медиа-файлы, base64 дампы
- полные raw JSON outputs (только truncated previews)
- Instagram CDN URLs (редактируются до `<url:domain/...redacted>`)

## Secret scanner

Перед записью каждого файла скрипт сканирует содержимое на паттерны:
- `sk-[A-Za-z0-9_-]{20,}` (OpenAI ключ)
- `apify_api_[A-Za-z0-9_-]{20,}` (Apify токен)
- `sessionid=...` (Instagram cookie)
- JWT токены `eyJ...`
- строки `VAR=<длинный_токен>` из `.env`

При обнаружении: **скрипт выходит с кодом 1**, файл не записывается.

## Папка handoff/ в .gitignore

`handoff/` добавлена в `.gitignore` — bundle никогда не попадёт в коммит случайно.

## Следующий шаг

После получения bundle:
1. Открыть `BUNDLE_README.md` — убедиться что всё нашлось.
2. Если `competitor_analysis_template_schema.md` показывает **"Excel file not provided"**:
   - запустить с `--excel-file путь/к/файлу.xlsx`.
3. Если `competitor_analysis_tz.md` показывает **"ТЗ file not provided"**:
   - запустить с `--tz-file путь/к/файлу.md`.
4. Передать bundle в Claude Code для создания Stage 5D Coverage Mapper.
