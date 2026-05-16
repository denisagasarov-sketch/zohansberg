# Stage 5C — Competitor Content Analysis Report

## Run metadata

- model: `gpt-4o-mini`
- detail: `low`
- image_input_mode: `base64`
- prompt_version: `v1`
- stories total in output: 15
- stories analyzed:        15
- stories from cache:      3
- skipped_media_fetch_failed:    0
- skipped_invalid_content_type:  0
- skipped_media_too_large:       0
- skipped_no_url:                0
- openai_errors:                 0

Что НЕ сделал:
- не запускал Apify
- не скачивал media файлы на диск
- не делал XLSX (Stage 5D)

## По highlights

| pos | highlight_id | canonical_title | analyzed | dominant content | dominant role | CTA% | text% |
|---|---|---|---|---|---|---|---|
| 1 | 17874797856565339 | отзывы курс | 5/57 | student_review | trust | 0% | 100% |
| 2 | 18110898391654002 | GEO | 5/17 | educational | education | 80% | 100% |
| 3 | 18124257904515721 | отзывы курс | 5/99 | student_review | proof | 0% | 100% |

## Распределение content_type (все highlights)

| content_type | count | % |
|---|---|---|
| student_review | 10 | 67% |
| educational | 2 | 13% |
| other | 1 | 7% |
| community_social_proof | 1 | 7% |
| authority_proof | 1 | 7% |

## Распределение commercial_role (все highlights)

| commercial_role | count | % |
|---|---|---|
| trust | 7 | 47% |
| proof | 4 | 27% |
| education | 3 | 20% |
| none | 1 | 7% |

## Детально по highlights

### [1] отзывы курс  `17874797856565339`

- stories_total:       57
- stories_analyzed:    5
- stories_skipped:     0
- stories_from_cache:  1
- dominant_content_type:    **student_review**
- dominant_commercial_role: **trust**
- cta_rate:            0%
- has_visible_text:    100%

  **Content types:**
  - student_review: 5

  **Commercial roles:**
  - trust: 4
  - proof: 1

  **Common tags:** курс, отзывы, маркетинг, успех, клиент, гордость, доверие, возврат

### [2] GEO  `18110898391654002`

- stories_total:       17
- stories_analyzed:    5
- stories_skipped:     0
- stories_from_cache:  1
- dominant_content_type:    **educational**
- dominant_commercial_role: **education**
- cta_rate:            80%
- has_visible_text:    100%

  **Content types:**
  - educational: 2
  - other: 1
  - community_social_proof: 1
  - authority_proof: 1

  **Commercial roles:**
  - education: 3
  - none: 1
  - trust: 1

  **Common tags:** продвижение, GEO, отзыв, маркетинг, инструменты, сториз, предприниматели, нейросеть

  **Detected CTAs:**
  - обязательно посмотрите эту линейку сториз до конца
  - выход в топ выдачи от нейросети
  - тыкните на любую реакцию
  - пишите в директ, чтобы узнать об этой услуге, и получить бесплатную консультацию по GEO

### [3] отзывы курс  `18124257904515721`

- stories_total:       99
- stories_analyzed:    5
- stories_skipped:     0
- stories_from_cache:  1
- dominant_content_type:    **student_review**
- dominant_commercial_role: **proof**
- cta_rate:            0%
- has_visible_text:    100%

  **Content types:**
  - student_review: 5

  **Commercial roles:**
  - proof: 3
  - trust: 2

  **Common tags:** отзывы, маркетинг, обучение, курс, успех, курсы, студенты, обсуждение

## Все обнаруженные CTA

- обязательно посмотрите эту линейку сториз до конца
- выход в топ выдачи от нейросети
- тыкните на любую реакцию
- пишите в директ, чтобы узнать об этой услуге, и получить бесплатную консультацию по GEO

## Output files

```
data/raw/stage5c_cache/                          ← per-story cache (not committed)
data/normalized/stage5c_stories_analysis.json    ← all story results (not committed)
data/normalized/stage5c_highlights_summary.json  ← per-highlight aggregate (not committed)
report/stage_5c_analysis_report.md               ← this report (not committed)
```

## Recommendation

→ Analyzed 15 of 173 total stories.
  Increase --max-stories-per-highlight or run for remaining highlights.
→ Stage 5D (XLSX): use stage5c_highlights_summary.json for competitive table.
