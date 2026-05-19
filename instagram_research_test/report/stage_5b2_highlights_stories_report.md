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

- account: `kate.jet`
- actor: `automation-lab/instagram-stories-scraper`
- run_timestamp: `2026-05-17T14:14:49.157743+00:00`
- planned_apify_calls: 1
- actual_apify_calls: 1
- apify_run_ids: ['yRDmrCwoqB9fR6HfN']

## Collection stats

- highlights_total: 5
- highlights_processed: 5
- highlights_ok: 0
- highlights_empty: 5
- highlights_fail: 0
- highlights_invalid: 0
- highlights_skipped: 0
- total_stories_count: 0
- highlights_with_media: 0
- can_analyze_highlights: **False**

## Per-highlight results

| # | highlight_id | title | status | stories | imageUrl | videoUrl |
|---|---|---|---|---|---|---|
| 1 | 18048529088454532 | Отзывы | EMPTY_OR_INACCESSIBLE | 0 | no | no |
| 2 | 18136644298466967 | Публикации | EMPTY_OR_INACCESSIBLE | 0 | no | no |
| 3 | 18145835785306063 | Мой путь | EMPTY_OR_INACCESSIBLE | 0 | no | no |
| 4 | 18036274999576186 | Обо мне | EMPTY_OR_INACCESSIBLE | 0 | no | no |
| 5 | 17919926188005828 | КНИГИ | EMPTY_OR_INACCESSIBLE | 0 | no | no |

## Warnings

- 5 highlights returned 0 stories (EMPTY_OR_INACCESSIBLE)

## Output files

```
data/raw/stage5b2_stories_{id}_raw.json       ← raw per highlight (not committed)
data/normalized/stage5b2_highlights_stories_summary.json ← run summary (not committed)
data/normalized/stage5b2_stories_index.json              ← lightweight index (not committed)
report/stage_5b2_highlights_stories_report.md            ← this report (not committed)
```

## Final verdict

**FAIL** — нет highlights со stories. Stage 5C заблокирован.
- can_analyze_highlights: False

## Recommendation

→ Stage 5C заблокирован — исправить ошибки выше перед продолжением.
