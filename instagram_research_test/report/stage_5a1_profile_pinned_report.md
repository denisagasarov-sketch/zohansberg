# Stage 5A-1 — Profile + Pinned Index Report

## Scope

Что сделал:
- собрал профиль через `apify/instagram-scraper` режим `details`
- собрал posts (limit 30) через `apify/instagram-scraper` режим `posts` для pinned detection
- создал normalized JSON: `profile_summary.json`, `bio_analysis.json`, `pinned_posts_index.json`, `stage5a_summary.json`

Что НЕ сделал:
- не анализировал highlights
- не анализировал landing
- не заполнял XLSX
- не запускал OpenAI
- не скачивал media

## Run metadata

- account: `kate.jet`
- run_timestamp: `2026-05-16T02:17:13.195317+00:00`
- planned_apify_calls: 2
- actual_apify_calls: 0
- apify_run_ids: []

## Profile

| Field | Value | Status |
|---|---|---|
| username | —  [manual_needed] | ⚠ manual_needed |
| full_name | —  [manual_needed] | ⚠ manual_needed |
| bio_text | —  [manual_needed] | ⚠ manual_needed |
| external_url | —  [manual_needed] | ⚠ manual_needed |
| external_url_type | —  [missing] | ✗ missing |
| followers_count | —  [manual_needed] | ⚠ manual_needed |
| following_count | —  [manual_needed] | ⚠ manual_needed |
| posts_count | —  [manual_needed] | ⚠ manual_needed |

## Bio rule-based analysis

> **Note:** This is rule-based analysis only — partial, not final interpretation.
> Fields marked `partial` or `manual_needed` require human review or OpenAI analysis (Stage 5D).

| Field | Value | Status |
|---|---|---|
| niche | —  [manual_needed] | ⚠ manual_needed |
| target_audience | —  [manual_needed] | ⚠ manual_needed |
| result_promise | —  [manual_needed] | ⚠ manual_needed |
| positioning | —  [manual_needed] | ⚠ manual_needed |
| social_proof | —  [manual_needed] | ⚠ manual_needed |
| trust_arguments | —  [manual_needed] | ⚠ manual_needed |
| cta_text | —  [manual_needed] | ⚠ manual_needed |
| cta_destination | —  [manual_needed] | ⚠ manual_needed |

## Pinned posts

- posts_checked: 0
- pinned_count: 0
- detection_method: `not_detected`
- manual_needed: True
- notes: isPinned field absent in all posts — fill pinned_posts_manual.json manually

No pinned posts detected.

## Coverage by sheet

| Sheet | Status |
|---|---|
| Описание профиля | missing |
| Закрепленные посты | manual_needed |
| Воронка | missing |
| Анализ хайлайтс | not_started |
| Лендинг | not_started |
| Бот лид-магнит | not_started |

## Output files

```
data/raw/stage5a1_profile_details_raw.json      ← raw details actor output (not committed)
data/raw/stage5a1_posts_for_pinned_raw.json     ← raw posts actor output (not committed)
data/normalized/profile_summary.json            ← structured profile fields
data/normalized/bio_analysis.json               ← rule-based bio analysis
data/normalized/pinned_posts_index.json         ← pinned posts list
data/normalized/stage5a_summary.json            ← stage coverage summary
report/stage_5a1_profile_pinned_report.md       ← this report
```

## Final verdict

**PARTIAL** — Profile collected, pinned posts incomplete or manual_needed.

- profile_status: partial
- bio_status: missing
- pinned_posts_status: manual_needed

## Recommendation

- Лист 'Описание профиля': **missing** — можно заполнять факты; интерпретация (niche/positioning) требует проверки.
- Лист 'Закрепленные посты': **manual_needed**

Blockers:
- pinned posts not detected — fill pinned_posts_manual.json

Profile and facts are available. Bio analysis is rule-based/partial — review bio_analysis.json and fill manual fields. Before Stage 5B: provide highlight IDs in data/input/highlights_manual.json.
