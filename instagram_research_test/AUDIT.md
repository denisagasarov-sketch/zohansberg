# PIPELINE AUDIT
_Дата: 2026-06-22_

## КОНТРАКТЫ СТЕЙДЖЕЙ

---
### 01 · stage5a1_collect_profile_and_pinned
**Назначение:** 2 вызова Apify → профиль + индекс закрепов

**Вход:** accounts.json → username
**Выход:**
- normalized/profile_summary.json
- normalized/bio_analysis.json
- normalized/pinned_posts_index.json
- normalized/stage5a_summary.json

**Apify:** apify/instagram-scraper (2 вызова)
**OpenAI:** нет · **Playwright:** нет
**Стоимость:** $0 (только Apify)
**Оркестратор:** stage5a1_run_local.py ✓

---
### 02 · stage5a2b_collect_pinned_post_details
**Назначение:** детали 3 закреплённых постов

**Вход:** raw/stage5a1_posts_for_pinned_raw.json
**Выход:**
- normalized/stage5a2b_pinned_posts_details.json
- normalized/stage5a2b_pinned_posts_schema_summary.json

**Apify:** нет (читает уже собранный raw)
**OpenAI:** нет · **Playwright:** нет
**Стоимость:** $0
**Оркестратор:** stage5a2b_run_local.py ✓

---
### 03 · stage5a2c_analyze_pinned_posts_caption
**Назначение:** семантический анализ текста 3 закрепов

**Вход:** normalized/stage5a2b_pinned_posts_details.json
**Выход:**
- normalized/stage5a2c_pinned_posts_semantic.json
- normalized/stage5a2c_pinned_posts_google_sheet_rows.json
- normalized/stage5a2c_pinned_posts_google_sheet_rows_fixed.json (шаг 2)

**OpenAI:** gpt-4o (текст, без картинок)
**Стоимость:** $0.01–0.05
**Оркестратор:** stage5a2c_run_local.py × 2
  - вызов 1: --analyze --budget-max-usd 0.10
  - вызов 2: --validate-existing-output --write-fixed

---
### 04 · stage5a2d_pinned_hooks_visual
**Назначение:** хук первого экрана закрепов через Vision

**Вход:** normalized/stage5a2b_pinned_posts_details.json
**Выход:** normalized/stage5a2d_pinned_hooks.json

**OpenAI:** gpt-4o Vision
**Стоимость:** ~$0.05
**Оркестратор:** stage5a2d_pinned_hooks_visual.py ✓

---
### 05 · stage5a2e_bio_semantic_analyzer
**Назначение:** семантика био → 4 поля (аудитория, позиционирование, job, оффер)

**Вход:** normalized/profile_summary.json + raw/stage5a1_profile_details_raw.json
**Выход:** normalized/stage5a2e_bio_semantic.json

**OpenAI:** gpt-4o (текст)
**Стоимость:** ~$0.01
**Оркестратор:** stage5a2e_bio_semantic_analyzer.py ✓

---
### 06 · stage5a2f_link_destination_classifier
**Назначение:** куда ведёт ссылка из профиля

**Вход:** normalized/profile_summary.json → external_url.value
**Выход:** normalized/stage5a2f_link_destination.json

**OpenAI:** gpt-4o-mini (если эвристика не справилась)
**Стоимость:** ~$0.01
**Оркестратор:** stage5a2f_link_destination_classifier.py ✓

---
### 07 · stage5a2g_landing_analyzer
**Назначение:** анализ лендинга конкурента (6 проходов)

**Вход:** normalized/stage5a2f_link_destination.json → url
**Выход:** normalized/stage5a2g_landing_analysis.json

**Playwright:** да (скролл + скриншоты)
**OpenAI:** gpt-4o (Vision + Text, 6 проходов)
**Стоимость:** $0.10–0.30 (самый дорогой)
**Оркестратор:** stage5a2g_landing_analyzer.py ✓

---
### 08 · stage5b1_collect_highlights_index
**Назначение:** индекс хайлайтов профиля

**Вход:** accounts.json → username
**Выход:**
- normalized/highlights_index.json
- normalized/stage5b1_highlights_index_summary.json

**Apify:** singhera07/instagram-scraper (highlights)
**Стоимость:** $0
**Оркестратор:** stage5b1_run_local.py ✓

---
### 09 · stage5b2_collect_highlight_stories
**Назначение:** сторис внутри каждого хайлайта

**Вход:** normalized/highlights_index.json → highlight IDs
**Выход:**
- raw/stage5b2_stories_{id}_raw.json (по одному на хайлайт)
- normalized/stage5b2_stories_index.json
- normalized/stage5b2_highlights_stories_summary.json

**Apify:** N вызовов (по одному на хайлайт)
**Стоимость:** $0 × N
**Оркестратор:** stage5b2_run_local.py ✓

---
### 10 · stage5b2v_highlights_visual_analyzer
**Назначение:** визуальный анализ хайлайтов (до 5 imageUrl на хайлайт)

**Вход:**
- raw/stage5b1_highlights_index_raw.json
- raw/stage5b2_stories_{id}_raw.json

**Выход:** normalized/stage5b2v_highlights_visual.json

**OpenAI:** gpt-4o Vision
**Стоимость:** ~$0.05–0.15
**Оркестратор:** stage5b2v_highlights_visual_analyzer.py ✓

---
### 11 · stage5c1_reels_collector
**Назначение:** сбор Reels (isPinned первыми, потом топ по viewCount)

**Вход:** accounts.json → username
**Выход:**
- raw/stage5c1_reels_raw.json
- normalized/stage5c1_reels_index.json

**Apify:** apify/instagram-reel-scraper
**Стоимость:** $0
**Оркестратор:** stage5c1_reels_collector.py ✓

---
### 12 · stage5c2_reels_analyzer
**Назначение:** анализ Reels (2 прохода GPT на каждый)

**Вход:** normalized/stage5c1_reels_index.json
**Выход:** normalized/stage5c2_reels_analysis.json

**OpenAI:** gpt-4o
  - проход 1: Vision по обложке → hook, vizual_format
  - проход 2: текст caption → topic, mechanic, CTA, what_to_test
**Стоимость:** ~$0.05–0.10
**Оркестратор:** stage5c2_reels_analyzer.py ✓

---
### 13 · stage5e0_posts_index  ⚠ НЕ В ОРКЕСТРАТОРЕ
**Назначение:** лёгкий сборщик индекса постов (без GPT, без медиа)

**Вход:** accounts.json → username
**Выход:**
- raw/stage5e0_posts_raw.json
- normalized/stage5e0_posts_index.json

**Apify:** apify/instagram-scraper (resultsType=posts)
**Стоимость:** $0
**Оркестратор:** НЕ ПОДКЛЮЧЁН ⚠

---
### 14 · stage5e1_posts_analyzer  ⚠ НЕ В ОРКЕСТРАТОРЕ
**Назначение:** полный анализ постов (download + GPT Vision + строки)

**Вход:**
- normalized/stage5e0_posts_index.json (приоритет)
- raw/posts_test_raw.json (fallback)
- normalized/profile_summary.json → followers
- data/kate.jet/normalized/profile_summary.json → контекст Кейт
- data/kate.jet/raw/posts_test_raw.json → последние посты Кейт

**Выход:** normalized/stage5e1_posts_analysis.json

**OpenAI:** gpt-4o Vision
  - фото: 1 картинка high detail
  - карусель: до 10 слайдов high detail
  - видео: 5 кадров через ffmpeg high detail
**Стоимость:** $0.10–0.50 (зависит от лимита)
**Оркестратор:** НЕ ПОДКЛЮЧЁН ⚠

---
### 15 · stage5d1_prepare_sheet_rows
**Назначение:** сборка payload.json из ВСЕХ normalized-файлов

**Вход:** все normalized/*.json (17 источников)
**Выход:** payload.json (6 вкладок, 79 полей)

**OpenAI:** нет · **Apify:** нет
**Стоимость:** $0
**Оркестратор:** stage5d1_run_local.py ✓

---
### 16 · stage5d3_write_google_sheets
**Назначение:** запись payload в Google Sheets через Apps Script

**Вход:** payload.json
**Выход:** данные в Google Sheets

**Google Sheets:** да (Apps Script Web App)
**Стоимость:** $0
**Оркестратор:** stage5d3_write_google_sheets.py ✓

---
## УТИЛИТЫ (не в основном пайплайне)

| Файл | Назначение |
|------|-----------|
| stage5a0 | schema-check актора Apify |
| stage5a2a | аудит источника закрепов |
| stage5b0 | проверка совместимости highlight ID |
| stage5b_auto* | активные сторис за 24ч (другой актор) |
| stage5c_analyze_stories | анализ активных сторис (не Reels) |
| stage5d2 | валидация формата payload |
| stage5d_coverage_mapper | карта покрытия 79 полей |
| stage5d_prepare_handoff | сборка handoff-бандла |

---
## ИТОГО

**Скриптов основного пайплайна:** 16
**Не подключены в оркестратор:** stage5e0, stage5e1 (13, 14)

**Функции дублируются в 3+ скриптах:**
- загрузка accounts.json → читают 5e0, 5e1, 5c1 каждый по-своему
- инициализация OpenAI клиента → 5a2c, 5a2d, 5a2e, 5a2f, 5a2g, 5b2v, 5c2, 5e1
- определение BASE (корень репо) → все скрипты, каждый сам

**Пути встречаются в 3+ скриптах:**
- data/{account}/normalized/profile_summary.json → 5a2c, 5a2e, 5a2f, 5d1, 5e1
- data/{account}/normalized/highlights_index.json → 5b2, 5b_auto, 5d1
- data/{account}/normalized/stage5c*.json → 5d1, 5d_coverage_mapper

**Главный архитектурный долг:**
- 3 файла на стейдж (логика + run_local + create_report) → 42 скрипта вместо 16
- BASE, paths, OpenAI клиент — дублируются везде, нет core/
- 5e0/5e1 не в оркестраторе → вкладка «Посты» не заполняется через бота
