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
- status: FAIL
- items returned: 0
- sample item path: data/raw/sample_post_item.json
- raw path: data/raw/posts_test_raw.json
- field inventory path: data/normalized/posts_field_inventory.json
- key fields available: caption=no, url/shortcode=no, timestamp=no, likes=no, comments=no, views=no, visual=no, video_url=no, carousel=no, reel=no
- errors: Unexpected error: Host not in allowlist

## Highlights index actor

- actor id: scrapio/instagram-highlights-scraper
- status: FAIL
- highlights returned: 0
- clean highlight id available: no
- clean highlight id valid: no
- clean highlight id value: n/a
- sample item path: data/raw/sample_highlight_item.json
- raw path: data/raw/highlights_index_test_raw.json
- summary path: data/normalized/highlights_index_summary.json
- errors: Unexpected error: Host not in allowlist

## Highlight stories actor

- actor id: igview-owner/instagram-highlights-stories-viewer
- status: SKIPPED
- highlight id tested: n/a
- stories returned: 0
- imageUrl available: no
- videoUrl available: no
- any media URL available: no
- sample item path: data/raw/sample_story_item.json
- raw path: data/raw/highlight_stories_test_raw.json
- summary path: data/normalized/highlight_stories_summary.json
- errors: none

## Final verdict

FAIL — нужно менять actor или способ сбора

## Recommendation

- Масштабирование на 20 публикаций: нет — posts actor вернул FAIL, нужно устранить причину.
- Масштабирование на все аккаунты: нет — сначала исправить posts actor.
- Анализ highlights внутри: не проверялось — clean_highlight_id не был получен.
- Перед Stage 3: исправить — posts=FAIL, highlights_index=FAIL. Проверь error log: data/raw/errors_test.json.
