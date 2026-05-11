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

**schema_status:** `manual_confirmation_needed`  
**schema_source:** `unknown`

**Problem:** The actor `scrapio/instagram-highlights-scraper` was **not returned** by any Apify search or API call. Only `scrapio/instagram-profile-scraper` was found for the `scrapio` author. The highlights scraper actor may not exist under this exact ID, or may have been renamed, deprecated, or delisted.

**accepts:** unknown  
**Proxy required:** unknown  
**supports_limit:** unknown

**Test input:** NEEDS_MANUAL_CONFIRMATION

**Business fields to check (pending schema confirmation):**

| Business need | Probable field name | Status |
|---|---|---|
| Highlight title | `title` | unconfirmed |
| Raw highlight ID | `id` or `highlight_id` | unconfirmed |
| Clean highlight ID | extracted from raw ID | logic: strip `highlight:` prefix if present |
| Cover image | `coverMedia` or `cover_image` | unconfirmed |
| Username | `username` | unconfirmed |
| User ID | `userId` or `user_id` | unconfirmed |

**clean_highlight_id extraction rule (once confirmed):**  
If raw ID arrives as `highlight:18268617304253172` → clean to `18268617304253172`  
If raw ID already arrives as `18268617304253172` → use as-is

**Possible output field names:** none confirmed

**Risks:**
- Actor may not exist under ID `scrapio/instagram-highlights-scraper`
- If actor is renamed/deprecated, an alternative must be identified before Stage 2
- `clean_highlight_id` cannot be extracted until actor run produces real output

**can_run_stage_2:** `false`  
**stop_reason:** Actor `scrapio/instagram-highlights-scraper` could not be confirmed to exist. Manual action required:
1. Open `https://apify.com/scrapio/instagram-highlights-scraper` in browser
2. If page exists: capture exact input field names from the **Input** tab, update `actor_payloads.json`
3. If page does not exist: identify a working replacement actor and confirm with the user

---

## Actor 3: Highlight stories

**Actor:** `igview-owner/instagram-highlights-stories-viewer`

**Purpose:** Collect stories inside one highlight by clean highlight ID.

**schema_status:** `manual_confirmation_needed`  
**schema_source:** `unknown`

**What is confirmed:** Actor page exists on Apify. Actor accepts a `highlightId` parameter. Can also accept `username` to retrieve all highlights for a profile.

**What is NOT confirmed:**
- Exact input field name (`highlightId` vs `highlight_id` vs other)
- Required format of the ID: numeric-only (`18268617304253172`) vs prefixed (`highlight:18268617304253172`)
- Complete output schema with exact field names

**accepts:** `highlight_id`  
**Proxy required:** unknown  
**supports_limit:** unknown

**Test input template (not ready to run):**
```json
{
  "highlightId": "WILL_BE_FILLED_AFTER_HIGHLIGHTS_INDEX_TEST"
}
```
> Format unconfirmed. Confirm from actor Input tab before running.

**Why this actor cannot run before clean_highlight_id exists:**  
This actor requires a highlight ID as input. That ID comes from the output of Actor 2 (highlights index). Without running Actor 2 first, there is no valid highlight ID to pass. Even if the schema were confirmed, this actor must always run after Actor 2 in Stage 2.

**Business fields to check in Stage 2 raw output:**

| Business need | Probable field name | Status |
|---|---|---|
| Story number | `storyNumber` | unconfirmed |
| Story ID | `storyId` | unconfirmed |
| Story type | `storyType` | unconfirmed |
| Image URL | `imageUrl` | unconfirmed |
| Video URL | `videoUrl` | unconfirmed |
| Publish date | `takenAt` or `publishDate` | unconfirmed |
| Duration | `duration` | unconfirmed |
| Raw story data | `rawStoryData` | unconfirmed |

**Possible output field names (inferred from search results):** `storyId`, `publishDate`, `expiryDate`, `imageUrl`, `videoUrl`, `mentions`, `links`  
> Exact names (camelCase vs snake_case) unconfirmed.

**Risks:**
- highlightId format (prefix vs numeric-only) unconfirmed — wrong format will cause actor error
- Cannot run without clean_highlight_id from Actor 2
- Expired or private highlights may return empty results

**can_run_stage_2 (after clean_highlight_id):** `true` — conditionally  
**stop_reason:** none — but depends on Actor 2 output and highlightId format confirmation

---

## Stage 2 readiness

**stage_2_allowed:** `false`

**Blockers:**

1. **NO_ACCOUNT_PROVIDED** — No Instagram account URL given. Replace `PASTE_TEST_ACCOUNT_HERE` in `data/accounts.json`.

2. **HIGHLIGHTS_INDEX_SCHEMA_UNCONFIRMED** — `scrapio/instagram-highlights-scraper` actor existence and input schema require manual verification. Open `https://apify.com/scrapio/instagram-highlights-scraper` and confirm actor exists + capture input field names.

3. **HIGHLIGHTS_STORIES_FORMAT_UNCONFIRMED** — `igview-owner/instagram-highlights-stories-viewer` highlightId format (numeric-only vs `highlight:` prefix) unconfirmed. Open `https://apify.com/igview-owner/instagram-highlights-stories-viewer/input-schema` and confirm exact format.

**What user must confirm manually:**

| # | Action | Where |
|---|---|---|
| 1 | Provide Instagram account URL | `data/accounts.json` |
| 2 | Confirm `scrapio/instagram-highlights-scraper` exists and capture input schema | Browser → Apify Store |
| 3 | Confirm `highlightId` exact format for `igview-owner/instagram-highlights-stories-viewer` | Browser → actor Input tab |

---

## Minimal run plan for Stage 2

> Stage 2 is currently blocked. This plan becomes executable after all 3 blockers above are resolved.

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
