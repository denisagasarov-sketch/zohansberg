# Stage 5B-1 — Highlights Index Report

## Scope

Что сделал:
- прочитал actor registry (`config/actors_registry.json`)
- запустил `singhera07/instagram-scraper` highlights index actor
- собрал список highlights
- создал `data/normalized/highlights_index.json`

Что НЕ сделал:
- не собирал stories по highlights
- не скачивал media
- не запускал OpenAI
- не анализировал содержание highlights
- не заполнял XLSX

## Run metadata

- account: `kate.jet`
- actor: `singhera07/instagram-scraper`
- run_timestamp: `2026-05-17T14:14:27.245781+00:00`
- planned_apify_calls: 1
- actual_apify_calls: 1
- apify_run_ids: ['syclQiH65mDGqvOCg']
- requested_limit: 12
- returned_highlights_count: 5
- unique_highlights_count: 5
- duplicates_count: 0
- raw_shape: `list`
- extraction_path: `root`
- limit_behavior: **unclear**

## Highlights index

| # | highlight_id | title | owner_username | cover |
|---|---|---|---|---|
| 1 | 18048529088454532 | Отзывы | kate.jet | yes |
| 2 | 18136644298466967 | Публикации | kate.jet | yes |
| 3 | 18145835785306063 | Мой путь | kate.jet | yes |
| 4 | 18036274999576186 | Обо мне | kate.jet | yes |
| 5 | 17919926188005828 | КНИГИ | kate.jet | yes |

## Limit behavior

- requested_limit = 12
- returned_highlights_count = 5
- user_reported_previous_count = 32  *(source: actors_registry.user_reported_previous_successful_run)*

**Вывод: unclear** — невозможно однозначно определить поведение limit. Проверить вручную или сравнить с no-limit запуском.

## Quality checks

- highlights_with_id: 5
- highlights_with_title: 5
- highlights_with_cover: 5
- highlights_with_owner_username: 5
- duplicates_count: 0

No warnings.

## Output files

```
data/raw/stage5b1_highlights_index_raw.json          ← raw actor output (not committed)
data/normalized/highlights_index.json                 ← normalized highlights list (not committed)
data/normalized/stage5b1_highlights_index_summary.json ← run summary (not committed)
report/stage_5b1_highlights_index_report.md           ← this report (not committed)
```

## Final verdict

**OK** — все highlights собраны с id и title.
- status: OK
- can_run_stage5b2: True

## Recommendation

highlights_index collected — Stage 5B-2 can proceed. limit behavior unclear — verify manually or compare with a no-limit run.

→ Stage 5B-2 можно запускать: использовать `highlight_id` из `highlights_index.json`.
