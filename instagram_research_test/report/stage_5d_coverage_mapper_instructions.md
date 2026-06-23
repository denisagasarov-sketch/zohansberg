# Stage 5D Coverage Mapper — Local Run Instructions

## Что делает

Читает реальные normalized outputs пайплайна и строит покрытие 79 Excel-колонок:
- какие поля можно заполнить сейчас
- какие частично
- какие missing
- какой следующий stage нужен

Не вызывает Apify, OpenAI. Не пишет в Excel. Не читает .env.

## Требования

- Python 3.11+
- Рабочий каталог: instagram_research_test/
- Опционально: normalized outputs в data/normalized/ (без них все поля будут missing)

## Команды

```bash
cd /путь/к/zohansberg-instagram-test/instagram_research_test

# dry-run — показать план без записи файлов
python scripts/stage5d_run_local.py --dry-run

# реальный запуск — создать coverage map + report
python scripts/stage5d_run_local.py

# пересоздать только отчёт (если coverage_map.json уже есть)
python scripts/stage5d_create_report.py
```

## Входные файлы (все опциональны — при отсутствии поля помечаются missing)

- data/normalized/profile_summary.json
- data/normalized/bio_analysis.json
- data/normalized/pinned_posts_index.json
- data/normalized/highlights_index.json
- data/normalized/stage5b_auto_stories_summary.json
- data/normalized/stage5b_auto_stories_index.json
- data/normalized/stage5c_highlights_summary.json
- data/normalized/stage5c_stories_analysis.json

## Выходные файлы (runtime — НЕ коммитить)

- data/normalized/stage5d_coverage_map.json     ← 79 coverage records
- data/normalized/stage5d_coverage_summary.json  ← sheet summaries + meta
- report/stage_5d_coverage_report.md             ← human-readable отчёт

## Валидация

Скрипт падает если:
- total Excel columns != 79
- любое поле имеет недопустимый status
- любой лист имеет 0 mapped fields
- любое поле не имеет обоих статусов (current_data + pipeline_capability)

## Следующий шаг

После просмотра отчёта:
1. Определить top next stage по impact на coverage.
2. Построить нужный stage (5E landing / 5F bot / pinned post analyzer).
3. Повторить stage5d_run_local.py после нового run — coverage увеличится.
