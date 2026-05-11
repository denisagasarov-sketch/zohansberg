# Stage 3 plan: media download + OpenAI analysis

## Status

Not started. Requires explicit approval before execution.

## Prerequisites (all must be confirmed before running)

- [ ] Posts raw data available from `apify/instagram-scraper` local run
- [ ] Highlight IDs provided manually (scrapio actor not available — see Stage 2B)
- [ ] `OPENAI_API_KEY` set in `.env`
- [ ] `APIFY_TOKEN` set in `.env`
- [ ] Scripts run locally (not in sandbox)

## Scope

One account: `https://www.instagram.com/vlada_kliuiko/`

| Item | Limit |
|---|---|
| Posts/reels | 5 (from Stage 2 raw output) |
| Highlight stories | 1 highlight, up to 5 stories |
| OpenAI calls | 1 per post + 1 per story analyzed |

## What Stage 3 does NOT do

- No full account analysis
- No all-highlights download
- No competitor comparison
- No bio / profile link / pinned post analysis
- No marketing strategy generation

---

## Step-by-step plan

### Step 1 — Prepare posts data

Input: `data/raw/posts_test_raw.json` (from Stage 2 local run)

Actions:
- Parse raw posts output
- Extract per post: `shortCode` / `url`, `displayUrl`, `videoUrl`, `caption`, `timestamp`, `type`
- Save normalized list: `data/normalized/posts_normalized.json`

No Apify call — reuse existing raw data.

### Step 2 — Download post media

For each of the 5 posts:
- If image: download `displayUrl` → `output/media/posts/{shortCode}.jpg`
- If video/reel: download `videoUrl` → `output/media/reels/{shortCode}.mp4`
- If carousel: download first image only

Tool: `requests` + streaming download.  
No OpenAI at this step.

### Step 3 — Analyze posts via OpenAI

For each downloaded post media + caption:
- Send image to OpenAI Vision (`gpt-4o`) with structured prompt
- Prompt asks for: content type, key visual elements, tone, CTA presence, format (post/reel/carousel)
- Save response: `analysis/openai_responses/post_{shortCode}.json`

Input per call:
```
image_url: <local file as base64 or direct URL>
caption: <from normalized data>
```

OpenAI model: `gpt-4o`  
Max tokens: 500 per call  
No streaming.

### Step 4 — Prepare highlight stories data

Input: manually provided `highlightId` (e.g. `17874797856565339`)

Actions:
- Run `igview-owner/instagram-highlights-stories-viewer` once with the highlight ID
- Save raw output: `data/raw/highlight_stories_stage3_raw.json`
- Select first 5 stories with `imageUrl` or `videoUrl`
- Save normalized: `data/normalized/stories_normalized.json`

### Step 5 — Download story media

For each of up to 5 stories:
- If imageUrl: download → `output/media/highlights/{storyId}.jpg`
- If videoUrl: download → `output/media/highlights/{storyId}.mp4`

### Step 6 — Extract video frames (optional)

For video stories only:
- Extract 1 frame at 1s using `opencv-python`
- Save frame: `output/frames/{storyId}_frame.jpg`
- Use frame (not full video) for OpenAI Vision call

### Step 7 — Analyze highlight stories via OpenAI

For each story (image or frame):
- Send to OpenAI Vision with structured prompt
- Prompt asks for: story format, visual style, text overlays, CTA, product/service presence
- Save response: `analysis/openai_responses/story_{storyId}.json`

### Step 8 — Build analysis report

Aggregate all OpenAI responses into:
`report/stage_3_analysis_report.md`

Report sections:
- Posts: content type breakdown, recurring visual patterns, CTA presence
- Highlight stories: format patterns, visual style, topics
- Short summary: what works, what repeats, what to check in Stage 4

---

## Scripts to create (not yet created)

| Script | Purpose |
|---|---|
| `scripts/download_media.py` | Steps 2 + 5 |
| `scripts/analyze_with_openai.py` | Steps 3 + 7 |
| `scripts/build_stage3_report.py` | Step 8 |

## Constraints

- Each OpenAI call: max 1 per media item
- No retries on OpenAI errors — log and skip
- No git operations during run
- No secret values in any output file
- Highlight ID must be provided manually before run

## Approval checkpoint

Stage 3 does not start until explicitly approved.  
After approval, provide:
1. Confirmed highlight ID(s) for stories test
2. Confirmation that posts raw data from Stage 2 local run is available
