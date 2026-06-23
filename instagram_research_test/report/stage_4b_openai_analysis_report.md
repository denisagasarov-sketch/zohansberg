# Stage 4B — OpenAI Analysis Report

_Generated: 2026-05-12 04:57 UTC_

## Scope

Stage 4B did:
- OpenAI analysis of 5 posts
- OpenAI analysis of 8 highlight batches
- Structured JSON outputs per post and per batch

Stage 4B did NOT do:
- Highlight synthesis
- Final account report
- Bio analysis
- Pinned posts analysis
- New scraping or media downloading

## Plan Check

- stage4b_can_continue: `True`
- posts requests: `5`
- highlight batch requests: `8`
- all prepared files found: `True`
- limits ok: `True`
- planned calls: `13`
- max calls allowed: `13`

## Posts Analysis

- posts total: `5`
- OK: `5`
- PARTIAL: `0`
- FAIL: `0`
- skipped existing OK: `0`
- OpenAI calls made: `5`

| request_id | status | topic | cta | offer | funnel_role | score | confidence | evidence |
|------------|--------|-------|-----|-------|-------------|-------|------------|----------|
| post_DF2bxZHtdW8 | OK | Маркетинговые услуги для малого и средне | Писать слово «консультация» в  | Полный спектр маркетинговых ус | leadgen | 1 | high | 4 |
| post_DR5LoKnjQSQ | OK | Обучающий курс по маркетинговым стратеги | Писать «АНКЕТА» в директ и ком | Участие в курсе с эксклюзивным | leadgen | 1 | high | 4 |
| post_DTKl6n3jWnB | OK | Тенденции маркетинга в 2026 году и метод | Не найдено | Не найдено | expertise | 1 | high | 5 |
| post_DXv71MqjfNG | OK | Путешествие и отдых в Италии, семейные м | Не найдено | Не найдено | reach | 1 | high | 4 |
| post_DXxLzsNug-u | OK | маркетинг, разбор маркетинговых кейсов и | подписаться на аккаунт @vlada_ | не найдено | reach | 1 | high | 4 |

## Highlight Batches Analysis

- batches total: `8`
- OK: `8`
- PARTIAL: `0`
- FAIL: `0`
- skipped existing OK: `0`
- OpenAI calls made: `8`

| request_id | status | stories | inputs | main_roles | cta | offer | social_proof | dss | confidence | evidence |
|------------|--------|---------|--------|------------|-----|-------|-------------|-----|------------|----------|
| highlight_batch_1 | OK | 8 | 9 | social_proof, education, unknown | Прямой призыв к действию  | Явный оффер не найден | В батче представлены мног | 1 | high | 5 |
| highlight_batch_2 | OK | 8 | 10 | social_proof, education, course_tru | Прямой призыв к действию  | Предлагается обучение по  | Многочисленные отзывы уче | 4 | high | 8 |
| highlight_batch_3 | OK | 8 | 10 | social_proof, education, course_tru | Прямой призыв к действию  | Явный оффер не найден, но | Многочисленные отзывы и б | 4 | high | 8 |
| highlight_batch_4 | OK | 8 | 8 | social_proof, education, course_tru | Прямой призыв к действию  | Явный оффер не найден, но | В сторис содержится множе | 4 | high | 4 |
| highlight_batch_5 | OK | 8 | 10 | social_proof, education, course_tru | Рекомендации пройти курс  | Практический курс 'Маркет | Многочисленные отзывы и р | 4 | high | 5 |
| highlight_batch_6 | OK | 6 | 9 | social_proof, education, course_tru | Прямой призыв к действию  | Явный оффер не найден | Присутствуют многочисленн | 1 | high | 5 |
| highlight_batch_7 | OK | 5 | 9 | social_proof, education, course_tru | Прямой призыв к действию  | Явный оффер не найден, но | Присутствуют многочисленн | 1 | high | 5 |
| highlight_batch_8 | OK | 6 | 7 | education, social_proof, course_tru | Прямой призыв к действию  | Курс «маркетинговые страт | Многочисленные отзывы уче | 4 | high | 4 |

## Output Files

```
analysis/stage4b/posts/
analysis/stage4b/highlight_batches/
analysis/openai_responses/stage4b/posts/
analysis/openai_responses/stage4b/highlight_batches/
data/normalized/stage4b_posts_summary.json
data/normalized/stage4b_highlight_batches_summary.json
```

## Final Verdict

**OK**

## Recommendation

All posts and batches analyzed successfully.
Stage 4C (highlight synthesis + final account report) can proceed.

**Remaining limitations before Stage 4C:**
- Highlight synthesis not done — 8 batch outputs need synthesis pass
- Bio and pinned posts not analyzed
- Each batch analyzed independently; cross-batch patterns not resolved
