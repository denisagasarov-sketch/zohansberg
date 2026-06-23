# Stage 3 inputs check

## File check

| File | Status | Items |
|---|---|---|
| `data/raw/posts_test_raw.json` | found | 0 — empty array |
| `data/raw/highlight_stories_manual_test_raw.json` | found | 0 — empty array |
| `data/normalized/posts_field_inventory.json` | found | status: FAIL (sandbox run) |
| `data/normalized/highlight_stories_manual_summary.json` | found | status: FAIL (sandbox run) |

## Detail

- **posts raw**: found, but empty — sandbox could not reach Apify API (Host not in allowlist); local run returned 5 posts but output was not synced back
- **posts count**: 0 in sandbox file
- **manual highlight stories raw**: found, but empty — same reason; local run returned 57 stories
- **stories count**: 0 in sandbox file
- **imageUrl available**: no (file empty)
- **videoUrl available**: no (file empty)

## Why the files are empty

`data/raw/` is listed in `.gitignore`. The successful local Stage 2B run saved output to the local machine only. Those files were never committed or pushed, so the sandbox only has the empty stubs written during the failed sandbox runs.

## Keys check

- APIFY_TOKEN: found
- OPENAI_API_KEY: found

## Can Stage 3 run from this sandbox?

**No.**

The sandbox has no outgoing access to `api.apify.com`. All three Apify actors return `Host not in allowlist`. Stage 3 media download also requires outgoing HTTP to Instagram CDN URLs, which will face the same restriction.

## What is needed to run Stage 3

Stage 3 must be run **locally**, where network access is open. Two options:

**Option A — run fully locally:**
1. Clone the branch locally
2. Copy `.env` with both keys
3. Run `python3 scripts/run_scraping_test.py` to re-collect posts raw data
4. Run `python3 scripts/test_highlight_stories_manual.py` to re-collect stories raw data
5. Then run Stage 3 scripts (to be created) against the real local raw files

**Option B — provide raw data manually:**
1. Copy `posts_test_raw.json` and `highlight_stories_manual_test_raw.json` from the local Stage 2B run into this repo's `data/raw/` folder
2. Temporarily remove `data/raw/` from `.gitignore` (or keep local only)
3. Run Stage 3 scripts here against the real data

## Recommendation

Use Option A — run the full pipeline locally. Stage 3 scripts will be written to work from `data/raw/` files regardless of where they were collected.

## Verdict

Stage 3 scripts can be created now, but execution requires a local environment with open network access.
