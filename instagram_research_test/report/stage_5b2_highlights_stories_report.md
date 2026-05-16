# Stage 5B-2 — Highlight Stories Report

## Scope

Что сделал:
- прочитал highlight IDs из `data/normalized/highlights_index.json`
- вызвал `automation-lab/instagram-stories-scraper` для каждого валидного ID
- собрал stories по каждому highlight
- создал normalized summary и stories index

Что НЕ сделал:
- не анализировал содержимое stories
- не скачивал media
- не запускал OpenAI
- не заполнял XLSX

## Run metadata

- account: `vlada_kliuiko`
- actor: `automation-lab/instagram-stories-scraper`
- run_timestamp: `2026-05-16T03:47:06.350674+00:00`
- planned_apify_calls: 1
- actual_apify_calls: 1
- apify_run_ids: ['et6LgwJBWbBIFvYf8']

## Collection stats

- highlights_total: 32
- highlights_processed: 2
- highlights_ok: 2
- highlights_empty: 0
- highlights_fail: 0
- highlights_invalid: 0
- highlights_skipped: 30
- total_stories_count: 77
- highlights_with_media: 0
- can_analyze_highlights: **True**

## Per-highlight results

| # | highlight_id | title | status | stories | imageUrl | videoUrl |
|---|---|---|---|---|---|---|
| 1 | 17874797856565339 | отзывы курс | OK | 60 | no | no |
| 2 | 18110898391654002 | GEO | OK | 17 | no | no |

## Warnings

- 30 highlights not processed (limit applied)

## Output files

```
data/raw/stage5b2_stories_{id}_raw.json       ← raw per highlight (not committed)
data/normalized/stage5b2_highlights_stories_summary.json ← run summary (not committed)
data/normalized/stage5b2_stories_index.json              ← lightweight index (not committed)
report/stage_5b2_highlights_stories_report.md            ← this report (not committed)
```

## Final verdict

**OK** — все 2 highlights вернули stories.
- can_analyze_highlights: True

## Recommendation

→ Stage 5C (анализ highlights через OpenAI Vision) можно запускать.
  Использовать `data/normalized/stage5b2_stories_index.json` для списка highlights.
  Raw stories в `data/raw/stage5b2_stories_{id}_raw.json`.
