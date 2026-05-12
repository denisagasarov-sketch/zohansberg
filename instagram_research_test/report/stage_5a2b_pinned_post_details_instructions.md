# Stage 5A-2B: Pinned Posts Details Collector — Local Run Instructions

## What this stage does

Collects full technical details for the 3 pinned posts:
- full caption (no 300-char truncation)
- displayUrl / cover image URL
- thumbnailUrl
- carousel slides (for Sidecar posts)
- video URL / video thumbnail
- media type, shortcode, post_id, timestamp

**Does NOT:**
- Call OpenAI or perform semantic analysis
- Download media files
- Write to Google Sheets
- Modify any existing normalized files

---

## Why this stage is needed

Stage 5A-1 stores only `caption[:300]` and does NOT collect `displayUrl`,
`thumbnailUrl`, or `carouselMedia`. Stage 5A-2A audit confirmed this.

This stage provides the data foundation for:
- **Stage 5A-2C**: Caption-only semantic analyzer (Тема поста, Почему закреплен,
  Ключевые смыслы, Какой CTA, Куда ведет CTA, Роль в воронке)
- **Stage 5A-2D**: Visual/OCR analyzer (Хук / первый экран)

---

## Actor

`apify/instagram-scraper` — same actor as Stage 5A-1.

**Schema status:**
- Confirmed fields (from Stage 5A-1 source code): `url`, `id`, `shortCode`, `caption`, `type`, `timestamp`, `isPinned`
- Candidate media fields (NOT confirmed in local raw — discovered at runtime): `displayUrl`, `thumbnailUrl`, `carouselMedia`, `videoUrl`

---

## Collection strategy

### Preferred: direct post URL mode
```
directUrls: [post_url_1, post_url_2, post_url_3]
resultsType: "posts"
resultsLimit: 3
```

### Fallback: account scrape + filter
```
directUrls: ["https://www.instagram.com/vlada_kliuiko/"]
resultsType: "posts"
resultsLimit: 30   ← hard limit
```
Then filter results to the 3 pinned shortcodes from `pinned_posts_index.json`.

---

## Prerequisites

- `data/normalized/pinned_posts_index.json` — from Stage 5A-1
- `APIFY_TOKEN` in `.env` — for `--collect` only
- `apify-client` Python package: `pip install apify-client`

---

## Running locally

### 1. Dry-run (always first)

```bash
cd instagram_research_test
python3 scripts/stage5a2b_run_local.py --dry-run
```

Prints:
- 3 pinned posts (permalink, shortcode, media_type)
- Exact sanitized input payload for preferred and fallback strategies
- Confirmed vs. candidate field lists
- Stage 5A-1 raw file status
- APIFY_TOKEN presence (value never printed)
- Planned output paths

### 2. Try from existing Stage 5A-1 raw (if available)

If Stage 5A-1 was run and `data/raw/stage5a1_posts_for_pinned_raw.json` exists:

```bash
python3 scripts/stage5a2b_run_local.py --from-existing-raw
```

Normalizes from existing raw. If the raw contains full captions and media fields,
no new Apify call is needed. If raw is insufficient, script reports `insufficient_source`.

### 3. Fresh Apify collection

```bash
set -a; source .env; set +a
python3 scripts/stage5a2b_run_local.py --collect --max-posts 3
```

`--max-posts 3` is a required safety parameter (must be exactly 3).

### 4. Generate report from existing normalized output

```bash
python3 scripts/stage5a2b_run_local.py --create-report
```

---

## Output files

All runtime outputs are gitignored.

| File | Description |
|---|---|
| `data/raw/stage5a2b_pinned_posts_details_raw.json` | Full raw actor output (all fields preserved) |
| `data/normalized/stage5a2b_pinned_posts_details.json` | Normalized per-post details |
| `data/normalized/stage5a2b_pinned_posts_schema_summary.json` | Actor field schema inspection result |
| `report/stage_5a2b_pinned_post_details_report.md` | Human-readable collection report |

---

## Understanding the normalized output

Key fields per post:

| Field | Meaning |
|---|---|
| `caption_is_full` | `true` if len>300; `false` if truncated; `"unknown"` if ≤300 chars (could be short post) |
| `has_full_caption` | `true` only when caption_is_full=true |
| `display_url` | First candidate display URL found in actor output |
| `has_cover_or_thumbnail` | Whether any cover/thumbnail URL was found |
| `carousel_items` | Normalized slide list for Sidecar posts |
| `source_quality` | `full` / `partial` / `weak` |
| `analysis_readiness.caption_semantic_possible` | Whether Stage 5A-2C can proceed |
| `analysis_readiness.visual_ocr_input_possible` | Whether Stage 5A-2D can proceed |

---

## Schema confidence note

The `apify/instagram-scraper` actor is confirmed in Stage 5A-1 code for:
`url`, `id`, `shortCode`, `caption`, `type`, `timestamp`, `isPinned`.

Fields like `displayUrl`, `thumbnailUrl`, `carouselMedia` are **candidate fields**
that may or may not appear in the actor output. The schema inspector in the
collector will determine which are actually present at runtime and record this
in `stage5a2b_pinned_posts_schema_summary.json`.

If `displayUrl` is absent from the actor output, Stage 5A-2D (visual/OCR) will
require a different data source or actor.

---

## What is NOT done in this stage

- No semantic inference (Тема, Почему закреплен, Роль в воронке, etc.)
- No OpenAI calls
- No media file downloads
- No Google Sheets writes
- No URL signing or CDN access

Instagram CDN URLs in reports are redacted to `<instagram_cdn_redacted>`.
Raw and normalized files may preserve original URLs for the visual analysis stage.

---

## Recommended run order

1. `--dry-run` → verify 3 posts detected, check payloads
2. `--from-existing-raw` → if Stage 5A-1 raw exists (zero Apify cost)
3. If insufficient → `--collect --max-posts 3` (requires APIFY_TOKEN)
4. `--create-report` → review field coverage
5. If `caption_semantic_possible = true` → proceed to Stage 5A-2C
6. If `visual_ocr_input_possible = true` → proceed to Stage 5A-2D
