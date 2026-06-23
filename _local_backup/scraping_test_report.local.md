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
- status: OK
- items returned: 5
- sample item path: data/raw/sample_post_item.json
- raw path: data/raw/posts_test_raw.json
- field inventory path: data/normalized/posts_field_inventory.json
- key fields available: caption=yes, url/shortcode=yes, timestamp=yes, likes=yes, comments=yes, views=no, visual=yes, video_url=no, carousel=yes, reel=yes
- errors: none

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
- errors: You must rent a paid Actor in order to run it after its free trial has expired. To rent this Actor, go to https://console.apify.com/actors/hZihPOyiPyET6bbrc

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

PARTIAL — часть данных доступна, но есть ограничения

## Recommendation

- Масштабирование на 20 публикаций: возможно — изменить `resultsLimit` в actor_payloads.json.
- Масштабирование на все аккаунты: возможно — добавить URL в accounts.json, запускать по одному.
- Анализ highlights внутри: не проверялось — clean_highlight_id не был получен.
- Перед Stage 3: исправить — highlights_index=FAIL. Проверь error log: data/raw/errors_test.json.
