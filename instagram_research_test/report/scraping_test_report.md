# Instagram scraping test report

## Scope

Stage 2 checks only:
- posts dataset raw output
- highlights index raw output
- highlight stories raw output

Stage 2 does NOT check:
- bio
- profile link
- pinned posts
- website
- bot funnel
- content quality
- marketing strategy
- OpenAI analysis
- media download

## Test account

https://www.instagram.com/vlada_kliuiko/

## Posts dataset actor

- actor id: apify/instagram-scraper
- status: OK (confirmed locally)
- items returned: 5
- sample item path: data/raw/sample_post_item.json
- raw path: data/raw/posts_test_raw.json
- field inventory path: data/normalized/posts_field_inventory.json
- note: FAIL in sandbox (Host not in allowlist) — confirmed working when run locally
- errors: none (local run)

## Highlights index actor

- actor id: scrapio/instagram-highlights-scraper
- status: BLOCKED
- highlights returned: n/a
- clean highlight id available: no
- clean highlight id valid: no
- clean highlight id value: n/a
- sample item path: n/a
- raw path: n/a
- summary path: data/normalized/highlights_index_summary.json
- block reason: actor requires paid rental — not available on current Apify plan
- workaround: highlight IDs provided manually for Stage 2B and Stage 3

## Highlight stories actor — Stage 2B manual test

- actor id: igview-owner/instagram-highlights-stories-viewer
- status: OK
- highlight id tested: 17874797856565339
- stories returned: 57
- imageUrl available: yes
- videoUrl available: yes
- any media URL available: yes
- sample item path: data/raw/sample_story_manual_item.json
- raw path: data/raw/highlight_stories_manual_test_raw.json
- summary path: data/normalized/highlight_stories_manual_summary.json
- errors: none

## Final verdict

PARTIAL — strong enough to continue

## What is confirmed working

1. `apify/instagram-scraper` — returns posts dataset with media URLs, captions, engagement fields
2. `igview-owner/instagram-highlights-stories-viewer` — returns 57 stories with imageUrl and videoUrl for manually provided highlightId

## What is not solved

1. Automatic highlight ID extraction — `scrapio/instagram-highlights-scraper` requires paid rental. Workaround: provide highlight IDs manually before Stage 3 run.

## Recommendation

- Масштабирование на 20 публикаций: возможно — изменить `resultsLimit` в actor_payloads.json.
- Масштабирование на все аккаунты: возможно — добавить URLs в accounts.json, запускать по одному.
- Анализ highlights внутри: возможно при ручном предоставлении highlight IDs — actor подтверждён, возвращает imageUrl и videoUrl.
- Перед Stage 3: предоставить highlight IDs вручную для каждого аккаунта; автоматическая экстракция через scrapio недоступна без paid rental.
