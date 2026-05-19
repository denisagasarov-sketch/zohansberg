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
- run_timestamp: `2026-05-17T14:12:58.202330+00:00`
- planned_apify_calls: 2
- actual_apify_calls: 2
- apify_run_ids: ['bG5uTqedt7lafE7X6', 'Q6OZkZ01RYcevbaan']

## Profile

| Field | Value | Status |
|---|---|---|
| username | kate.jet | ✓ ok |
| full_name | Кейт Семёнова | SMM Adviser | ✓ ok |
| bio_text | 💵 Ex-Head of SMM Refocus: сделала выручку $1 млн
📰 US Forbes писали о моей стратегии в SMM
⚡ Систематизируй SMM с помощью курса | занять место 👇🏽 | ✓ ok |
| external_url | https://t.me/SMMworkshopBot | ✓ ok |
| external_url_type | telegram | ✓ ok |
| followers_count | 2523 | ✓ ok |
| following_count | 1421 | ✓ ok |
| posts_count | 1220 | ✓ ok |

## Bio rule-based analysis

> **Note:** This is rule-based analysis only — partial, not final interpretation.
> Fields marked `partial` or `manual_needed` require human review or OpenAI analysis (Stage 5D).

| Field | Value | Status |
|---|---|---|
| niche | 💵 Ex-Head of SMM Refocus: сделала выручку $1 млн | ~ partial |
| target_audience | —  [manual_needed] | ⚠ manual_needed |
| result_promise | —  [manual_needed] | ⚠ manual_needed |
| positioning | —  [manual_needed] | ⚠ manual_needed |
| social_proof | 💵 Ex-Head of SMM Refocus: сделала выручку $1 млн | ~ partial |
| trust_arguments | —  [manual_needed] | ⚠ manual_needed |
| cta_text | ⚡ Систематизируй SMM с помощью курса | занять место 👇🏽 | ~ partial |
| cta_destination | https://t.me/SMMworkshopBot | ✓ ok |

## Pinned posts

- posts_checked: 30
- pinned_count: 2
- detection_method: `actor_field`
- manual_needed: False

| # | URL | Shortcode | Type | Timestamp | Caption preview |
|---|---|---|---|---|---|
| 1 | https://www.instagram.com/p/DVYs6lJEu3o/ | DVYs6lJEu3o | Sidecar | 2026-03-02T14:48:13.000Z | Что мне помогло сделать выручку $1 МЛН с SMM 😎

В первую неделю запуска соцсетей... |
| 2 | https://www.instagram.com/p/DRhjE6mEk_o/ | DRhjE6mEk_o | Sidecar | 2025-11-26T15:09:50.000Z | Вы ждали мой новый курс как ждал Оскара Том Круз, как на Чукотке ждали орбит арб... |

## Coverage by sheet

| Sheet | Status |
|---|---|
| Описание профиля | partial |
| Закрепленные посты | partial |
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

- profile_status: ok
- bio_status: partial
- pinned_posts_status: partial

## Recommendation

- Лист 'Описание профиля': **partial** — можно заполнять факты; интерпретация (niche/positioning) требует проверки.
- Лист 'Закрепленные посты': **partial**

Profile and facts are available. Bio analysis is rule-based/partial — review bio_analysis.json and fill manual fields. Before Stage 5B: provide highlight IDs in data/input/highlights_manual.json.
