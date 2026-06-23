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

- account: `vlada_kliuiko`
- run_timestamp: `2026-05-19T15:00:50.378192+00:00`
- planned_apify_calls: 2
- actual_apify_calls: 2
- apify_run_ids: ['IxgBusANWIa8Se4Gg', 'OIRydc8gm8FD943pm']

## Profile

| Field | Value | Status |
|---|---|---|
| username | vlada_kliuiko | ✓ ok |
| full_name | продвижение • маркетолог • таргетолог • обучение смм | ✓ ok |
| bio_text | аналитически точные стратегии с опорой на цифры
основатель @elpodium_agency 
каждый четверг-рубрика разборов 
↓ курс по маркетинговым стратегиям с AI | ✓ ok |
| external_url | https://elpodium.org/strategy-prccnslt?utm_source=vladainst&utm_medium=bio | ✓ ok |
| external_url_type | site | ✓ ok |
| followers_count | 40200 | ✓ ok |
| following_count | 867 | ✓ ok |
| posts_count | 1390 | ✓ ok |

## Bio rule-based analysis

> **Note:** This is rule-based analysis only — partial, not final interpretation.
> Fields marked `partial` or `manual_needed` require human review or OpenAI analysis (Stage 5D).

| Field | Value | Status |
|---|---|---|
| niche | аналитически точные стратегии с опорой на цифры | ~ partial |
| target_audience | —  [manual_needed] | ⚠ manual_needed |
| result_promise | —  [manual_needed] | ⚠ manual_needed |
| positioning | —  [manual_needed] | ⚠ manual_needed |
| social_proof | основатель @elpodium_agency | ~ partial |
| trust_arguments | —  [manual_needed] | ⚠ manual_needed |
| cta_text | ↓ курс по маркетинговым стратегиям с AI | ~ partial |
| cta_destination | https://elpodium.org/strategy-prccnslt?utm_source=vladainst&utm_medium=bio | ✓ ok |

## Pinned posts

- posts_checked: 30
- pinned_count: 3
- detection_method: `actor_field`
- manual_needed: False

| # | URL | Shortcode | Type | Timestamp | Caption preview |
|---|---|---|---|---|---|
| 1 | https://www.instagram.com/p/DF2bxZHtdW8/ | DF2bxZHtdW8 | Sidecar | 2025-02-09T11:33:20.000Z | Мы с командой помогаем малым и средним бизнесам, экспертам и блогерам масштабиро... |
| 2 | https://www.instagram.com/p/DR5LoKnjQSQ/ | DR5LoKnjQSQ | Sidecar | 2025-12-05T19:26:42.000Z | 3 поток курса будет в ноябре 2026 год 

‼️Чтобы узнать все подробности о програм... |
| 3 | https://www.instagram.com/p/DTKl6n3jWnB/ | DTKl6n3jWnB | Video | 2026-01-06T10:15:24.000Z | Тенденции маркетинга в 2026: как прогнозировать результаты еще до старта и работ... |

## Coverage by sheet

| Sheet | Status |
|---|---|
| Описание профиля | partial |
| Закрепленные посты | ok |
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

**OK** — Profile collected and 3+ pinned posts detected.

- profile_status: ok
- bio_status: partial
- pinned_posts_status: ok

## Recommendation

- Лист 'Описание профиля': **partial** — можно заполнять факты; интерпретация (niche/positioning) требует проверки.
- Лист 'Закрепленные посты': **ok**

Profile and facts are available. Bio analysis is rule-based/partial — review bio_analysis.json and fill manual fields. Before Stage 5B: provide highlight IDs in data/input/highlights_manual.json.
