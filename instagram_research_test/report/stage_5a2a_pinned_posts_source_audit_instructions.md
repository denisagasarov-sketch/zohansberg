# Stage 5A-2A: Pinned Posts Source Audit — Local Run Instructions

## What this stage does

Audits `data/normalized/pinned_posts_index.json` to determine which fields are
available for each of the 3 pinned posts and which Google Sheets fields can be
filled now vs. which require more data.

**Does NOT:**
- Call Apify
- Call OpenAI
- Download media
- Write to Google Sheets
- Modify any existing normalized files

---

## Prerequisites

- `data/normalized/pinned_posts_index.json` — produced by Stage 5A-1 (requires Apify run)

---

## Running locally

### 1. Dry-run (always first)

```bash
cd instagram_research_test
python3 scripts/stage5a2a_run_local.py --dry-run
```

Prints:
- Top-level fields in `pinned_posts_index.json`
- Per-post field inventory (url, shortcode, caption_preview status, type, timestamp)
- List of all 11 Google Sheets fields that will be assessed
- Planned output paths
- Writes no files

### 2. Real run

```bash
python3 scripts/stage5a2a_run_local.py
```

Writes:
- `data/normalized/stage5a2a_pinned_posts_source_audit.json`
- `report/stage_5a2a_pinned_posts_source_audit.md`

---

## Output files

Both outputs are gitignored and must NOT be committed.

| File | Description |
|---|---|
| `data/normalized/stage5a2a_pinned_posts_source_audit.json` | Full audit JSON with per-post analysis and field assessment |
| `report/stage_5a2a_pinned_posts_source_audit.md` | Human-readable audit report |

---

## What the audit tells you

### Per post
- Which fields exist and which are missing
- Whether caption is full or truncated (current index stores max 300 chars)
- Whether CTA signals are detectable in caption preview
- Whether media fields (cover, carousel, video) are present

### Google Sheets field assessment
For each of the 11 "Закрепленные посты" fields:

| Field | Status with current data |
|---|---|
| Конкурент | Ready now |
| Ссылка на пост | Ready now |
| Позиция закрепа | Ready now |
| Что в тексте поста | Partial now (300-char preview only) |
| Тема поста | Needs full caption + semantic analysis |
| Почему закреплен | Needs full caption + semantic analysis |
| Хук / первый экран | Needs media (cover_url/display_url) + visual/OCR |
| Ключевые смыслы | Needs full caption + semantic analysis |
| Какой CTA | Needs full caption (CTA often at end of post) |
| Куда ведет CTA | Needs full caption + semantic analysis |
| Роль в воронке | Needs full caption + semantic analysis |

---

## Known structural limitations of current pinned_posts_index.json

`build_pinned_posts_index` in `stage5a1_collect_profile_and_pinned.py` stores:

| Field | Available | Notes |
|---|---|---|
| `url` | ✓ | Post permalink (field-wrapped) |
| `content_id` | ✓ | Post ID (field-wrapped) |
| `shortcode` | ✓ | shortCode (field-wrapped) |
| `caption_preview` | Partial | First 300 chars only — `caption_raw[:300]` |
| `type` | ✓ | image / video / sidecar (field-wrapped) |
| `timestamp` | ✓ | Post timestamp (field-wrapped) |
| `is_pinned` | ✓ | Always True |
| `full_caption` | ✗ | Not stored (truncated at 300) |
| `cover_url` | ✗ | Not collected |
| `thumbnail_url` | ✗ | Not collected |
| `display_url` | ✗ | Not collected |
| `carousel_items` | ✗ | Not collected |
| `media_urls` | ✗ | Not collected |
| `video_url` | ✗ | Not collected |

---

## Recommended next steps

1. **Stage 5A-2B (Pinned Posts Details Collector)**
   - New Apify call using same actor (`apify/instagram-scraper`, `resultsType=posts`)
   - Collect: full caption (no 300-char truncation), displayUrl, carouselMedia
   - Save as `data/normalized/pinned_posts_details.json`

2. **Stage 5A-2C (Caption-Only Semantic Analyzer)**
   - After Stage 5A-2B has full captions
   - OpenAI analysis: Тема поста, Почему закреплен, Ключевые смыслы, Какой CTA, Куда ведет CTA, Роль в воронке

3. **Stage 5A-2D (Visual Hook Analyzer)**
   - After Stage 5A-2B has cover/display URLs
   - Vision API analysis of first slide/cover for: Хук / первый экран

---

## Validation rules

- Fails if `pinned_posts_index.json` not found
- Fails if 0 pinned posts in index
- Warns if pinned post count ≠ 3
- Fails if any post has neither permalink, shortcode, nor content_id
- Fails if audit does not assess all 11 Google Sheets fields
- Does NOT fail if caption or media fields are missing — marks as limitation
