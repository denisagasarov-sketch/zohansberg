# Stage 5B-auto — Highlight Stories Report

## Scope

Что сделал:
- вызвал `automation-lab/instagram-stories-scraper` (1 call)
- разделил active stories и highlight stories
- сгруппировал highlight stories по `highlightId`
- присоединил canonical title/position/cover из `data/normalized/highlights_index.json`

Что НЕ сделал:
- не использовал `igview-owner` (deprecated fallback)
- не анализировал содержимое stories
- не скачивал media
- не запускал OpenAI
- не заполнял XLSX

## Run metadata

- account: `vlada_kliuiko`
- actor: `automation-lab/instagram-stories-scraper`
- mode: `normalize_only`
- run_timestamp: `2026-05-12T12:12:10.155958+00:00`
- apify_run_id: `xVKGkqmQoxQZCbvXx`
- max_highlights_requested: 3
- apify_calls: 0  (normalize-only, raw reused)

## Collection stats

- total_items_returned: 179
- active_stories_count: 6
- highlight_stories_count: 173
- highlights_returned: 3
- highlights_in_index: 32
- can_analyze_highlights: **True**

## Normalization stats

- image_stories:    143
- video_stories:    36
- null_id_count:    0
- null_media_count: 0

## Active stories (profile, last 24h)

Count: 6

| # | id | mediaType | timestamp | imageUrl | videoUrl |
|---|---|---|---|---|---|
| 1 | 3894831770150172158 | Image | 2026-05-11T17:22:29.000Z | yes | no |
| 2 | 3894835430099929548 | Image | 2026-05-11T17:29:45.000Z | yes | no |
| 3 | 3894956258013045703 | Video | 2026-05-11T21:30:03.000Z | no | yes |
| 4 | 3894962617156763175 | Video | 2026-05-11T21:42:42.000Z | no | yes |
| 5 | 3894965228480059740 | Video | 2026-05-11T21:47:57.000Z | no | yes |
| 6 | 3895280170633031362 | Image | 2026-05-12T08:13:23.000Z | yes | no |

## Highlight stories

| pos | highlight_id | canonical_title | auto_lab_title | stories | imageUrl | videoUrl |
|---|---|---|---|---|---|---|
| 1 | 17874797856565339 | отзывы курс | отзывы курс | 57 | yes | yes |
| 2 | 18110898391654002 | GEO | GEO | 17 | yes | yes |
| 3 | 18124257904515721 | отзывы курс | отзывы курс | 99 | yes | yes |

## Architecture note

| Actor | Role |
|---|---|
| `singhera07/instagram-scraper` | canonical highlights index (id, title, position, cover) |
| `automation-lab/instagram-stories-scraper` | highlight stories content |
| `igview-owner/instagram-highlights-stories-viewer` | deprecated fallback — not used |

highlightTitle from automation-lab is stored as `automation_lab_title` (raw).
Source of truth for title/order/cover is `highlights_index.json` from singhera07.

## Output files

```
data/raw/stage5b_auto_stories_raw.json              ← raw actor output (not committed)
data/normalized/stage5b_auto_stories_summary.json   ← run summary (not committed)
data/normalized/stage5b_auto_stories_index.json     ← grouped index (not committed)
report/stage_5b_auto_stories_report.md              ← this report (not committed)
```

## Final verdict

**OK** — 3 highlights вернули stories (maxHighlights=3).
- can_analyze_highlights: True

## Recommendation

→ Stage 5C (анализ highlights через OpenAI Vision) можно запускать.
  Использовать `data/normalized/stage5b_auto_stories_index.json`.
  Если нужны все highlights — повторить с `--max-highlights 32`.
