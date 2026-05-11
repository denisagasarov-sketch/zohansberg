# Actor inspection

## Working directory

- pwd: `/home/user/zohansberg`
- project directory: `instagram_research_test/`
- project found/created: found (created in previous session)

---

## Security check

- `.env`: found
- `APIFY_TOKEN`: found (non-empty)
- `.env` ignored by git: yes (`instagram_research_test/.gitignore` line 1)
- `.env` tracked by git: no — OK
- secrets found outside `.env`: no (README.md contains only masked placeholders `sk-...` and `apify_api_...` in comments, not real keys)
- action required: none

---

## Test account

- first account: **not provided** — placeholder `PASTE_TEST_ACCOUNT_HERE` remains in `data/accounts.json`
- clean username: **not available** — will be extracted from URL after account is provided
- posts_limit: 5
- highlights_limit: 1

> **Action required before Stage 2:** Replace `PASTE_TEST_ACCOUNT_HERE` in `data/accounts.json` with a real public Instagram account URL.

---

## Network access note

All direct calls to `api.apify.com` returned HTTP 403 "Host not in allowlist".  
All WebFetch calls to `apify.com` returned HTTP 403 Forbidden.  
Actor inspection was performed via WebSearch only.  
For Actor 2 and Actor 3, input-schema pages were not accessible — see schema_status per actor below.

---

## Actor 1: Posts/Reels

**Actor:** `apify/instagram-scraper`

**Purpose:** Collect last 5 posts/reels from the first test account.

**schema_status:** `confirmed`  
**schema_source:** `readme` — schema confirmed from multiple GitHub forks and search results returning consistent field names.

**accepts:** profile URL via `directUrls` array

**Test input (ready — pending account URL):**
```json
{
  "directUrls": ["https://www.instagram.com/PASTE_TEST_ACCOUNT_HERE/"],
  "resultsType": "posts",
  "resultsLimit": 5,
  "proxy": {
    "useApifyProxy": true,
    "apifyProxyGroups": []
  }
}
```

**How the limit works:** `resultsLimit: 5` sets the maximum results per URL. `resultsType: "posts"` returns posts and reels together — the `type` field on each item distinguishes them.

**Proxy required:** yes — `useApifyProxy: true` with empty `apifyProxyGroups` uses Apify's residential proxy pool automatically.

**Business fields to check in Stage 2 raw output:**

| Business need | Probable field name | Status |
|---|---|---|
| Caption | `caption` | unconfirmed — verify in Stage 2 |
| Post date | `timestamp` | unconfirmed |
| Post URL | `url` | unconfirmed |
| Short code | `shortCode` | unconfirmed |
| Content type | `type` | unconfirmed (Image/Video/Sidecar/Reel?) |
| Likes | `likesCount` | unconfirmed |
| Comments | `commentsCount` | unconfirmed |
| Views (reels) | `videoViewCount` | unconfirmed |
| Image URL | `displayUrl` | unconfirmed |
| Video URL | `videoUrl` | unconfirmed |
| Carousel images | `images` | unconfirmed |
| Author | `ownerUsername` | unconfirmed |

> Field names above are probable based on GitHub source READMEs. Do **not** use them in production code until confirmed against a real raw run output.

**Possible output field names:** `caption`, `timestamp`, `url`, `shortCode`, `likesCount`, `commentsCount`, `videoViewCount`, `displayUrl`, `videoUrl`, `type`, `images`, `ownerUsername`, `id`, `locationName`, `hashtags`, `mentions`

**Risks:**
- Instagram anti-scraping may reduce actual result count below `resultsLimit`
- Free Apify proxy tier may be rate-limited
- Reel detection depends on `type` field — exact enum values unknown until Stage 2

**can_run_stage_2:** `true`  
**stop_reason:** none — ready after account URL is provided

---

## Actor 2: Highlights index

**Actor:** `scrapio/instagram-highlights-scraper`

**Purpose:** Collect highlights list and highlight IDs from the first test account.

**schema_status:** `user_provided`  
**schema_source:** `user_provided` — input schema and output fields confirmed manually via Apify Store actor page.

**accepts:** profile URL via `startUrls` array  
**Proxy required:** yes  
**supports_limit:** no — actor returns all highlights; limit to 1 applied in post-processing

**Test input (ready — pending account URL):**
```json
{
  "proxyConfiguration": {
    "useApifyProxy": true
  },
  "startUrls": [
    "https://www.instagram.com/PASTE_TEST_ACCOUNT_HERE/"
  ]
}
```

**Business fields to check in Stage 2 raw output:**

| Business need | Confirmed field name | Notes |
|---|---|---|
| Highlight title | `title` | confirmed |
| Raw highlight ID | `id` | confirmed — may arrive as `highlight:18268617304253172` |
| Clean highlight ID | extracted from `id` | strip `highlight:` prefix if present |
| Cover image | `cover_media` | confirmed |
| Username | `username` | confirmed |
| User ID | `user_id` | confirmed |
| Source URL | `input_url` | confirmed |
| Content type | `type` | confirmed |
| Success flag | `success` | confirmed |
| Error message | `error` | confirmed |
| Timestamp | `timestamp` | confirmed |

**clean_highlight_id extraction rule:**  
`id` arrives as `highlight:18268617304253172` → strip prefix → `18268617304253172`  
If `id` is already numeric → use as-is

**Possible output field names:** `input_url`, `username`, `user_id`, `type`, `id`, `title`, `cover_media`, `success`, `error`, `timestamp`

**Risks:**
- `id` field includes `highlight:` prefix — must be stripped before passing to Actor 3
- Actor has no built-in limit — post-processing must select only 1 highlight for Stage 2 test

**can_run_stage_2:** `true`  
**stop_reason:** none — ready after account URL is provided

---

## Actor 3: Highlight stories

**Actor:** `igview-owner/instagram-highlights-stories-viewer`

**Purpose:** Collect stories inside one highlight by clean highlight ID.

**schema_status:** `user_provided`  
**schema_source:** `user_provided` — input field name and highlightId format confirmed manually via Apify Store actor page.

**accepts:** `highlightId` — 17-digit numeric only, **no `highlight:` prefix**  
**Proxy required:** unknown  
**supports_limit:** unknown

**Test input template (waiting for clean_highlight_id from Actor 2):**
```json
{
  "highlightId": "WILL_BE_FILLED_AFTER_HIGHLIGHTS_INDEX_TEST"
}
```
Example with real ID: `{ "highlightId": "18268617304253172" }`

**Why this actor cannot run before clean_highlight_id exists:**  
`highlightId` must come from Actor 2 output. Actor 2 returns `id` as `highlight:XXXXXXXXXXXXXXX` — the `highlight:` prefix must be stripped before passing to this actor. Running this actor before Actor 2 produces output is not possible.

**Business fields to check in Stage 2 raw output:**

| Business need | Confirmed field name | Notes |
|---|---|---|
| Story number | `storyNumber` | confirmed |
| Story ID | `storyId` | confirmed |
| Story type | `storyType` | confirmed |
| Image URL | `imageUrl` | confirmed |
| Video URL | `videoUrl` | confirmed |
| Publish date | `takenAt` | confirmed |
| Duration | `duration` | confirmed |
| Raw story data | `rawStoryData` | confirmed |

**Possible output field names:** `storyNumber`, `storyId`, `storyType`, `imageUrl`, `videoUrl`, `takenAt`, `duration`, `rawStoryData`

**Risks:**
- Cannot run before `clean_highlight_id` is obtained from Actor 2
- Passing `highlight:XXXX` format (with prefix) will cause actor error — must strip prefix
- Expired or private highlights may return empty results

**can_run_stage_2 (after clean_highlight_id):** `true`  
**stop_reason:** none — ready after Actor 2 provides a valid clean_highlight_id

---

## Stage 2 readiness

**stage_2_allowed:** `true`

**Remaining blocker (operational, not schema):**

- **NO_ACCOUNT_PROVIDED** — Replace `PASTE_TEST_ACCOUNT_HERE` in `data/accounts.json` and in `actor_payloads.json` (`posts_reels.test_input.directUrls[0]` and `highlights_index.test_input.startUrls[0]`) with a real public Instagram account URL before running.

All schema blockers resolved via manual user confirmation.

---

## Minimal run plan for Stage 2

> Ready to execute after account URL is provided.

1. Replace `PASTE_TEST_ACCOUNT_HERE` in `data/accounts.json` with real account URL
2. Update `actor_payloads.json` → `posts_reels.test_input.directUrls[0]` with real URL
3. Run `apify/instagram-scraper` with confirmed test_input (limit 5)
4. Save raw output → `data/raw/posts_raw.json`
5. Save sample post item → `data/normalized/sample_post.json`
6. Build field inventory: map raw field names to business fields table above
7. Update confirmed `scrapio/instagram-highlights-scraper` test_input with real account URL
8. Run highlights index actor on first account
9. Save raw output → `data/raw/highlights_raw.json`
10. Save sample highlight item → `data/normalized/sample_highlight.json`
11. Extract `clean_highlight_id` (strip `highlight:` prefix if present)
12. Validate: confirm `clean_highlight_id` is numeric, 15–20 digits
13. Fill `actor_payloads.json` → `highlight_stories.test_input_template.highlightId` with clean value
14. Run `igview-owner/instagram-highlights-stories-viewer` with clean_highlight_id
15. Save raw output → `data/raw/stories_raw.json`
16. Save sample story item → `data/normalized/sample_story.json`
17. Build short verdict per actor: **OK** (all business fields present) / **PARTIAL** (some fields missing) / **FAIL** (actor returned error or empty)

---

## Stop point

Stage 1 complete. Waiting for approval before Apify runs.
