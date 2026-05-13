# Instagram Competitor Research Pipeline

## Обзор
Pipeline анализирует Instagram-аккаунт конкурента и заполняет общую Google Sheets таблицу (6 листов, до 79 полей).

Входные данные: Instagram username (например: vlada_kliuiko)
Выходные данные: новые строки в таблице + отчет в Telegram на русском языке

Spreadsheet ID: 1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ

---

## Режим предварительной оценки

Перед полным запуском можно получить оценку затрат и времени:

    python3 run_pipeline.py --account username --estimate

Пример вывода в терминале:
    Аккаунт: @новый_конкурент
    Хайлайтов: ~28
    Сторис (оценка): ~400

    Ожидаемые затраты:
      Apify (профиль + хайлайты):     $0.50 – $1.50
      OpenAI Vision (хайлайты):       $0.20 – $0.50
      OpenAI GPT-4o (лендинг):        $0.05 – $0.10
      OpenAI GPT-4o-mini (bio, url):  $0.01 – $0.02
      Итого:                           $0.76 – $2.12

    Ожидаемое время: 4 – 8 минут
    Продолжить? [y/n]

Пример сообщения в Telegram при --estimate:
    📋 Оценка для @новый_конкурент

    Хайлайтов: ~28
    Сторис (оценка): ~400

    Ожидаемые затраты: $0.76 – $2.12
    Ожидаемое время: 4 – 8 минут

    Запустить полный анализ?
    ✅ Да  ❌ Нет

---

## Порядок запуска stages

### Stage 5A-1: Сбор профиля и закрепов
Скрипт: scripts/stage5a1_collect_profile_and_pinned.py
Источник: Apify (apify/instagram-scraper)
Выход:
  data/{account}/normalized/profile_summary.json
  data/{account}/normalized/pinned_posts_index.json
  data/{account}/raw/stage5a1_*.json
Затраты: ~$0.07–0.30 (Apify, pay per event)

### Stage 5A-2B: Детали закрепов
Скрипт: scripts/stage5a2b_collect_pinned_post_details.py
Источник: raw данные из Stage 5A-1
Выход: data/{account}/normalized/stage5a2b_pinned_posts_details.json
Затраты: $0

### Stage 5A-2C: Семантика закрепов
Скрипты:
  scripts/stage5a2c_analyze_pinned_posts_caption.py
  scripts/stage5a2c_run_local.py --validate-existing-output --write-fixed
Источник: stage5a2b output
Выход:
  data/{account}/normalized/stage5a2c_pinned_posts_semantic.json
  data/{account}/normalized/stage5a2c_pinned_posts_google_sheet_rows.json
  data/{account}/normalized/stage5a2c_pinned_posts_google_sheet_rows_fixed.json
Затраты: ~$0.01–0.05 (OpenAI gpt-4o)
Примечание: postprocessing (--write-fixed) — часть этого stage, не отдельный шаг.

### Stage 5A-2D: Хуки закрепов (Vision)
Скрипт: scripts/stage5a2d_pinned_hooks_visual.py
Источник: stage5a2b output (display_url изображений)
Выход: data/{account}/normalized/stage5a2d_pinned_hooks.json
Затраты: ~$0.01 (OpenAI gpt-4o Vision, 3 изображения)

### Stage 5A-2E: Семантика bio
Скрипт: scripts/stage5a2e_bio_semantic_analyzer.py
Источник: profile_summary.json
Выход: data/{account}/normalized/stage5a2e_bio_semantic.json
Затраты: ~$0.001 (OpenAI gpt-4o-mini)

### Stage 5A-2F: Классификатор ссылки из bio
Скрипт: scripts/stage5a2f_link_destination_classifier.py
Источник: profile_summary.json
Выход: data/{account}/normalized/stage5a2f_link_destination.json
Затраты: ~$0.001 (OpenAI gpt-4o-mini)

### Stage 5A-2G: Анализ лендинга
Скрипт: scripts/stage5a2g_landing_analyzer.py
Источник: stage5a2f output (url_clean)
Выход: data/{account}/normalized/stage5a2g_landing_analysis.json
Затраты: ~$0.05–0.10 (OpenAI gpt-4o + Playwright)
Примечание: требует Playwright и Chromium на локальной машине.

### Stage 5B-1: Сбор хайлайтов
Скрипт: scripts/stage5b1_collect_highlights_index.py
Источник: Apify (apify/instagram-scraper highlights)
Выход: data/{account}/normalized/highlights_index.json
Затраты: ~$0.10–0.50 (Apify, зависит от числа хайлайтов)

### Stage 5C: Семантика хайлайтов
Скрипт: scripts/stage5c_*.py
Источник: raw данные сторис из stage5b0
Выход: data/{account}/normalized/stage5c_highlights_summary.json
Затраты: ~$0.10–0.50 (OpenAI gpt-4o)
Примечание: запускается только если есть stage5b0 файлы.
Если файлов нет — stage пропускается.

### Stage 5B-2V: Vision для хайлайтов
Скрипт: scripts/stage5b2v_highlights_visual_analyzer.py
Источник: data/{account}/raw/stage5b0_highlight_*_raw.json
Выход: data/{account}/normalized/stage5b2v_highlights_visual.json
Затраты: ~$0.05–0.50 (OpenAI gpt-4o Vision)
Примечание: запускается только если есть stage5b0 файлы.
Для аккаунтов без собранных сторис — пропускается.

### Stage 5D-1: Сборка payload
Скрипт: scripts/stage5d1_run_local.py --require-pinned-semantic
Источник: все normalized файлы текущего аккаунта
Выход:
  output/{account}/stage5d1/payload.json
  output/{account}/stage5d1/csv/*.csv
Затраты: $0

### Stage 5D-3: Запись в Google Sheets
Скрипт: scripts/stage5d3_write_google_sheets.py --write --confirm-write
Источник: payload.json
Выход: новые строки в Google Sheets для текущего конкурента
Затраты: $0
Примечание: пишет в первую пустую строку каждого листа.
Существующие данные не перезаписываются.

---

## Итоговые затраты на одного конкурента

Сценарий                          | Apify         | OpenAI        | Итого
Минимум (без сторис хайлайтов)    | $0.20–0.50    | $0.10–0.20    | $0.30–0.70
Полный прогон (с хайлайтами)      | $0.50–2.00    | $0.40–1.20    | $0.90–3.20

---

## Структура данных

instagram_research_test/
  data/
    {account}/
      raw/          — сырые данные от Apify (не коммитятся)
      normalized/   — обработанные данные (не коммитятся)
  output/
    {account}/
      stage5d1/     — payload и CSV файлы
      costs.json    — затраты по источникам для отчета в Telegram
  scripts/          — все скрипты pipeline
  run_pipeline.py   — entry-point (в разработке)

---

## Формат отчета в Telegram

Все сообщения бота — на русском языке.

Отчет после завершения:
    ✅ Анализ @username завершен

    📊 Заполнено полей: 45/79
    📋 Листов обновлено: 5/6

    💰 Затраты:
      Apify (профиль + хайлайты): $1.42
      OpenAI Vision (хайлайты):   $0.31
      OpenAI GPT-4o (лендинг):    $0.08
      OpenAI GPT-4o-mini (bio):   $0.02
      Итого:                       $1.83

    ⏱ Время: 4 мин 23 сек
    🔗 Таблица: https://docs.google.com/spreadsheets/d/1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ

---

## Статус параметризации

- [ ] Все скрипты принимают --account аргумент
- [ ] Данные изолированы в data/{account}/
- [ ] Stage 5D-3 пишет в первую пустую строку
- [ ] Entry-point: run_pipeline.py --account username --estimate
- [ ] Telegram-бот

---

## Протестировано на

- vlada_kliuiko (май 2026) — покрытие ~45/79 полей
