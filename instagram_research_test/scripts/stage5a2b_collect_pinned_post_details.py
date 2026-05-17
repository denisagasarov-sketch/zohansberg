"""Stage 5A-2B: Pinned Posts Details Collector.

Collects full technical details for the 3 pinned posts:
  full_caption, media_type, permalink, shortcode/post_id,
  timestamp, displayUrl/cover/thumbnail, carousel slides if any,
  video thumbnail/cover if any.

Actor: apify/instagram-scraper  (same as Stage 5A-1)
Strategy: prefer direct post URL mode; fallback to account scrape (max 30).

Does NOT call OpenAI, download media files, or write to Google Sheets.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE     = Path(__file__).parent.parent
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT     = _args.account
PROFILE_URL = f"https://www.instagram.com/{ACCOUNT}/"
RAW_DIR     = BASE / "data" / ACCOUNT / "raw"
NORM_DIR    = BASE / "data" / ACCOUNT / "normalized"

# Actor confirmed from Stage 5A-1 source code
ACTOR_ID = "apify/instagram-scraper"

PINNED_INDEX_PATH    = NORM_DIR / "pinned_posts_index.json"
AUDIT_PATH           = NORM_DIR / "stage5a2a_pinned_posts_source_audit.json"
PROFILE_SUMMARY_PATH = NORM_DIR / "profile_summary.json"

RAW_OUTPUT_PATH     = RAW_DIR / "stage5a2b_pinned_posts_details_raw.json"
STAGE5A1_RAW_POSTS  = RAW_DIR / "stage5a1_posts_for_pinned_raw.json"

NORM_OUTPUT_PATH    = NORM_DIR / "stage5a2b_pinned_posts_details.json"
SCHEMA_SUMMARY_PATH = NORM_DIR / "stage5a2b_pinned_posts_schema_summary.json"

# ── Fields confirmed from Stage 5A-1 source code ──────────────────────────
# build_pinned_posts_index accesses: url, id, shortCode, caption, isPinned,
# timestamp, type. Full caption was NOT stored (truncated to [:300]).
# These fields definitely exist in the actor output when isPinned is present.
CONFIRMED_MAP = {
    "url":       "permalink",
    "id":        "post_id",
    "shortCode": "shortcode",
    "caption":   "full_caption",
    "type":      "media_type",
    "timestamp": "timestamp",
    "isPinned":  "is_pinned",
}

# ── Candidate media/visual fields — NOT confirmed in local raw ─────────────
# Listed in discovery priority order. At runtime, schema inspector will
# record which are actually present.
CANDIDATE_DISPLAY_URL_FIELDS  = ["displayUrl", "displaySrc", "display_url"]
CANDIDATE_THUMBNAIL_FIELDS    = ["thumbnailSrc", "thumbnailUrl", "thumbnail_src", "thumbnail_url"]
CANDIDATE_VIDEO_URL_FIELDS    = ["videoUrl", "video_url", "videoSrc"]
CANDIDATE_CAROUSEL_FIELDS     = ["carouselMedia", "sidecar", "sidecars", "carousel_media",
                                  "edge_sidecar_to_children", "childPosts"]
CANDIDATE_LIKES_FIELDS        = ["likesCount", "likes_count"]
CANDIDATE_COMMENTS_FIELDS     = ["commentsCount", "comments_count"]
CANDIDATE_DATE_FIELDS         = ["takenAt", "taken_at", "date"]

ALL_CANDIDATE_FIELDS = (
    CANDIDATE_DISPLAY_URL_FIELDS + CANDIDATE_THUMBNAIL_FIELDS +
    CANDIDATE_VIDEO_URL_FIELDS + CANDIDATE_CAROUSEL_FIELDS +
    CANDIDATE_LIKES_FIELDS + CANDIDATE_COMMENTS_FIELDS + CANDIDATE_DATE_FIELDS
)

CDN_MARKERS = ("cdninstagram.com", "scontent", "fbcdn.net", "lookaside.fbsbx.com")

_TRUNCATION_SIGNALS = ["...", "…", "[truncated]"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _fval(d, *keys):
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict) and "value" in v:
            val = v["value"]
            if val not in (None, "", []):
                return val
        elif v not in (None, "", []):
            return v
    return None


def _redact_url(url, *, keep_post_urls=True) -> str:
    if not isinstance(url, str) or not url.startswith("http"):
        return str(url) if url else ""
    if any(m in url for m in CDN_MARKERS):
        return "<instagram_cdn_redacted>"
    return url


def _caption_fullness(caption: str | None) -> str:
    """Assess whether caption is likely full or truncated."""
    if not caption:
        return "missing"
    if any(sig in caption for sig in _TRUNCATION_SIGNALS):
        return False    # explicit truncation marker
    if len(caption) > 300:
        return True     # definitely longer than Stage 5A-1 cutoff
    # ≤ 300 chars: could be a genuinely short post, cannot confirm
    return "unknown"


def _safe_item(item: dict) -> dict:
    """Mirror of Stage 5A-1 safe_item for raw saving."""
    result = {}
    for k, v in item.items():
        if isinstance(v, str) and len(v) > 5000:
            result[k] = v[:5000] + "...[truncated]"
        elif isinstance(v, bytes):
            result[k] = "[bytes omitted]"
        else:
            result[k] = v
    return result


# ── Source loading ─────────────────────────────────────────────────────────

def load_pinned_index() -> tuple[dict, list[str]]:
    errors = []
    if not PINNED_INDEX_PATH.exists():
        errors.append(f"pinned_posts_index.json not found at {PINNED_INDEX_PATH}")
        return {}, errors
    try:
        index = json.loads(PINNED_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse pinned_posts_index.json: {e}")
        return {}, errors
    posts = index.get("pinned_posts") or []
    if not posts:
        errors.append("pinned_posts_index.json: 0 pinned posts found")
        return index, errors
    n = index.get("pinned_count", 0)
    warnings = []
    if n == 0:
        warnings.append("pinned_count is 0 — no pinned posts found in index")
    for i, p in enumerate(posts):
        has_url  = _fval(p, "url") is not None
        has_sc   = _fval(p, "shortcode") is not None
        has_id   = _fval(p, "content_id") is not None
        if not has_url and not has_sc and not has_id:
            errors.append(f"Post at index {i} has neither permalink, shortcode, nor content_id")
    return index, errors + ["WARNING: " + w for w in warnings]


def extract_pinned_refs(index: dict) -> list[dict]:
    """Return list of {position, permalink, shortcode, post_id, media_type} dicts."""
    posts = index.get("pinned_posts") or []
    refs = []
    for item in posts:
        refs.append({
            "position":   item.get("position"),
            "permalink":  _fval(item, "url"),
            "shortcode":  _fval(item, "shortcode"),
            "post_id":    _fval(item, "content_id"),
            "media_type": _fval(item, "type"),
        })
    return refs


# ── Apify payload builders ─────────────────────────────────────────────────

def build_direct_payload(post_urls: list[str]) -> dict:
    """Preferred: scrape exactly these 3 post URLs directly."""
    return {
        "directUrls":   post_urls,
        "resultsType":  "posts",
        "resultsLimit": len(post_urls),
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": []},
    }


def build_fallback_payload() -> dict:
    """Fallback: scrape account posts (max 30), then filter by pinned shortcodes."""
    return {
        "directUrls":   [PROFILE_URL],
        "resultsType":  "posts",
        "resultsLimit": 30,
        "proxy": {"useApifyProxy": True, "apifyProxyGroups": []},
    }


# ── Schema inspector ──────────────────────────────────────────────────────

def inspect_schema(items: list[dict]) -> dict:
    """
    Analyse which fields appear across all items.
    Returns schema_summary dict distinguishing confirmed vs candidate fields.
    """
    if not items:
        return {
            "items_count": 0,
            "all_fields": [],
            "confirmed_fields_present": [],
            "confirmed_fields_missing": list(CONFIRMED_MAP.keys()),
            "candidate_fields_present": {},
            "candidate_fields_missing": ALL_CANDIDATE_FIELDS,
            "caption_fields_found": [],
            "display_url_fields_found": [],
            "thumbnail_fields_found": [],
            "video_url_fields_found": [],
            "carousel_fields_found": [],
            "schema_confidence": "no_items",
        }

    all_keys: set[str] = set()
    for item in items:
        all_keys.update(item.keys())

    confirmed_present = [k for k in CONFIRMED_MAP if k in all_keys]
    confirmed_missing = [k for k in CONFIRMED_MAP if k not in all_keys]

    def _found(candidates):
        return [c for c in candidates if c in all_keys]

    display_found   = _found(CANDIDATE_DISPLAY_URL_FIELDS)
    thumb_found     = _found(CANDIDATE_THUMBNAIL_FIELDS)
    video_found     = _found(CANDIDATE_VIDEO_URL_FIELDS)
    carousel_found  = _found(CANDIDATE_CAROUSEL_FIELDS)
    likes_found     = _found(CANDIDATE_LIKES_FIELDS)
    comments_found  = _found(CANDIDATE_COMMENTS_FIELDS)

    # Caption check: look for non-empty caption values and measure length
    caption_lengths = []
    for item in items:
        cap = item.get("caption")
        if cap:
            caption_lengths.append(len(cap))

    schema_confidence = "high" if "caption" in all_keys and confirmed_present else "low"

    return {
        "items_count":              len(items),
        "all_fields":               sorted(all_keys),
        "confirmed_fields_present": confirmed_present,
        "confirmed_fields_missing": confirmed_missing,
        "caption_fields_found":     ["caption"] if "caption" in all_keys else [],
        "caption_lengths_observed": caption_lengths,
        "display_url_fields_found": display_found,
        "thumbnail_fields_found":   thumb_found,
        "video_url_fields_found":   video_found,
        "carousel_fields_found":    carousel_found,
        "likes_fields_found":       likes_found,
        "comments_fields_found":    comments_found,
        "candidate_fields_present": {
            "display_url":  display_found,
            "thumbnail":    thumb_found,
            "video_url":    video_found,
            "carousel":     carousel_found,
            "likes":        likes_found,
            "comments":     comments_found,
        },
        "candidate_fields_missing":  [
            f for f in ALL_CANDIDATE_FIELDS if f not in all_keys
        ],
        "schema_confidence": schema_confidence,
    }


# ── Per-post normalizer ───────────────────────────────────────────────────

def _first_nonempty(item: dict, *keys):
    for k in keys:
        v = item.get(k)
        if v is not None and v != "" and v != []:
            return v
    return None


def normalize_post_item(
    item: dict,
    schema: dict,
    pinned_ref: dict | None,
    position: int,
) -> dict:
    """
    Normalize a single raw actor item into the Stage 5A-2B post structure.
    Marks fields as null + notes limitation rather than inventing data.
    """
    permalink   = item.get("url")
    post_id     = item.get("id")
    shortcode   = item.get("shortCode")
    caption_raw = item.get("caption") or ""
    media_type  = item.get("type")
    timestamp   = item.get("timestamp")

    caption_fullness = _caption_fullness(caption_raw if caption_raw else None)

    # Media fields — try candidate lists
    display_url   = _first_nonempty(item, *CANDIDATE_DISPLAY_URL_FIELDS)
    thumbnail_url = _first_nonempty(item, *CANDIDATE_THUMBNAIL_FIELDS)
    video_url     = _first_nonempty(item, *CANDIDATE_VIDEO_URL_FIELDS)

    # Carousel / sidecar
    carousel_raw  = _first_nonempty(item, *CANDIDATE_CAROUSEL_FIELDS)
    carousel_items = []
    if isinstance(carousel_raw, list):
        for idx, slide in enumerate(carousel_raw, start=1):
            if not isinstance(slide, dict):
                continue
            slide_display = _first_nonempty(slide, "displayUrl", "displaySrc", "display_url")
            slide_thumb   = _first_nonempty(slide, "thumbnailSrc", "thumbnailUrl", "thumbnail_src")
            slide_video   = _first_nonempty(slide, "videoUrl", "video_url")
            slide_type    = slide.get("type") or slide.get("mediaType")
            carousel_items.append({
                "position":     idx,
                "media_type":   slide_type,
                "display_url":  slide_display,
                "thumbnail_url": slide_thumb,
                "video_url":    slide_video,
            })

    # Best candidate for visual analysis
    candidate_visual_urls = [u for u in [display_url, thumbnail_url, video_url] if u]
    for slide in carousel_items:
        for u in [slide.get("display_url"), slide.get("thumbnail_url")]:
            if u:
                candidate_visual_urls.append(u)

    primary_image_url  = display_url or thumbnail_url or (carousel_items[0]["display_url"] if carousel_items else None)
    source_fields_used = []
    for f in CANDIDATE_DISPLAY_URL_FIELDS:
        if item.get(f):
            source_fields_used.append(f); break
    for f in CANDIDATE_THUMBNAIL_FIELDS:
        if item.get(f):
            source_fields_used.append(f); break

    has_full_caption    = caption_fullness is True
    has_cover_or_thumb  = bool(display_url or thumbnail_url)
    has_carousel_items  = bool(carousel_items)
    has_media_urls      = bool(candidate_visual_urls)

    caption_semantic_possible = has_full_caption or (
        caption_fullness == "unknown" and len(caption_raw) > 0
    )
    visual_ocr_possible = has_cover_or_thumb or (has_carousel_items and bool(carousel_items[0].get("display_url")))

    limitations = []
    if caption_fullness is False:
        limitations.append("caption appears truncated — full caption still not available")
    elif caption_fullness == "missing":
        limitations.append("caption absent in actor output")
    elif caption_fullness == "unknown":
        limitations.append("caption ≤ 300 chars — cannot confirm if full or short post")
    if not has_cover_or_thumb:
        limitations.append("displayUrl / thumbnailUrl not found in actor output — visual hook analysis not possible")
    if not has_carousel_items and media_type in ("sidecar", "Sidecar", "GraphSidecar"):
        limitations.append("post is Sidecar but no carousel_items found in actor output")
    if not video_url and media_type in ("video", "Video", "Reel", "GraphVideo"):
        limitations.append("post is Video/Reel but no videoUrl found in actor output")

    source_quality = "full" if (has_full_caption and has_cover_or_thumb) else \
                     "partial" if (has_full_caption or has_cover_or_thumb) else "weak"

    missing_fields = []
    if not has_full_caption:
        missing_fields.append("full_caption")
    if not has_cover_or_thumb:
        missing_fields.append("display_url / thumbnail_url")
    if not has_carousel_items and media_type in ("sidecar", "Sidecar"):
        missing_fields.append("carousel_items")
    if not video_url and media_type in ("video", "Video", "Reel"):
        missing_fields.append("video_url")

    return {
        "position":           position,
        "permalink":          permalink,
        "shortcode":          shortcode,
        "post_id":            post_id,
        "timestamp":          timestamp,
        "media_type":         media_type,

        "full_caption":       caption_raw or None,
        "caption_for_analysis": caption_raw[:5000] if caption_raw else None,
        "caption_length":     len(caption_raw) if caption_raw else 0,
        "caption_is_full":    caption_fullness,
        "caption_source_field": "caption" if caption_raw else None,

        "display_url":        display_url,
        "thumbnail_url":      thumbnail_url,
        "video_url":          video_url,
        "cover_url":          display_url or thumbnail_url,

        "carousel_items":     carousel_items,
        "carousel_items_count": len(carousel_items),

        "media_for_visual_analysis": {
            "primary_image_url": primary_image_url,
            "candidate_urls":    candidate_visual_urls,
            "source_fields":     source_fields_used,
        },

        "has_full_caption":       has_full_caption,
        "has_cover_or_thumbnail": has_cover_or_thumb,
        "has_carousel_items":     has_carousel_items,
        "has_media_urls":         has_media_urls,

        "analysis_readiness": {
            "caption_semantic_possible": caption_semantic_possible,
            "visual_ocr_input_possible": visual_ocr_possible,
        },

        "source_quality":  source_quality,
        "missing_fields":  missing_fields,
        "limitations":     limitations,
    }


# ── Match items to pinned refs ─────────────────────────────────────────────

def match_items_to_pinned(
    items: list[dict],
    pinned_refs: list[dict],
) -> list[tuple[dict, dict | None]]:
    """
    For each pinned_ref, find the matching item by shortcode or post_id.
    Returns list of (pinned_ref, item_or_None).
    Direct mode returns items in the same order as directUrls,
    so we try shortcode match first, then index order.
    """
    matched = []
    pinned_shortcodes = {p["shortcode"] for p in pinned_refs if p.get("shortcode")}
    pinned_ids        = {p["post_id"]   for p in pinned_refs if p.get("post_id")}

    # Build lookup
    by_shortcode = {}
    by_id        = {}
    for item in items:
        sc = item.get("shortCode")
        iid = str(item.get("id") or "")
        if sc:
            by_shortcode[sc] = item
        if iid:
            by_id[iid] = item

    for ref in pinned_refs:
        sc  = ref.get("shortcode")
        iid = ref.get("post_id")
        item = by_shortcode.get(sc) or by_id.get(str(iid) if iid else "")
        matched.append((ref, item))

    return matched


# ── Build normalized output ────────────────────────────────────────────────

def build_normalized_output(
    matched: list[tuple[dict, dict | None]],
    schema: dict,
    source_info: dict,
) -> dict:
    run_ts = datetime.now(timezone.utc).isoformat()
    posts = []
    warnings = []

    for ref, item in matched:
        pos = ref.get("position", len(posts) + 1)
        if item is None:
            # Post not found in actor output
            warnings.append(
                f"Post {pos} (shortcode={ref.get('shortcode')}) not found in actor output"
            )
            posts.append({
                "position":           pos,
                "permalink":          ref.get("permalink"),
                "shortcode":          ref.get("shortcode"),
                "post_id":            ref.get("post_id"),
                "timestamp":          None,
                "media_type":         ref.get("media_type"),
                "full_caption":       None,
                "caption_for_analysis": None,
                "caption_length":     0,
                "caption_is_full":    "missing",
                "caption_source_field": None,
                "display_url":        None,
                "thumbnail_url":      None,
                "video_url":          None,
                "cover_url":          None,
                "carousel_items":     [],
                "carousel_items_count": 0,
                "media_for_visual_analysis": {
                    "primary_image_url": None,
                    "candidate_urls": [],
                    "source_fields": [],
                },
                "has_full_caption":       False,
                "has_cover_or_thumbnail": False,
                "has_carousel_items":     False,
                "has_media_urls":         False,
                "analysis_readiness": {
                    "caption_semantic_possible": False,
                    "visual_ocr_input_possible": False,
                },
                "source_quality": "weak",
                "missing_fields": ["full_caption", "display_url", "all media fields"],
                "limitations": ["post not found in actor output; shortcode match failed"],
            })
        else:
            posts.append(normalize_post_item(item, schema, ref, pos))

    n_full_cap  = sum(1 for p in posts if p["has_full_caption"])
    n_cover     = sum(1 for p in posts if p["has_cover_or_thumbnail"])
    n_carousel  = sum(1 for p in posts if p["has_carousel_items"])
    cap_sem_ok  = all(p["analysis_readiness"]["caption_semantic_possible"] for p in posts)
    vis_ok      = any(p["analysis_readiness"]["visual_ocr_input_possible"]  for p in posts)

    if n_full_cap < len(posts):
        warnings.append(
            f"{len(posts) - n_full_cap}/{len(posts)} posts still lack full caption after collection"
        )
    if n_cover < len(posts):
        warnings.append(
            f"{len(posts) - n_cover}/{len(posts)} posts still lack cover/thumbnail URL"
        )
    for p in posts:
        if p["media_type"] in ("sidecar", "Sidecar") and not p["has_carousel_items"]:
            warnings.append(
                f"Post {p['position']} is Sidecar but no carousel_items found"
            )

    if cap_sem_ok:
        next_rec = (
            "Stage 5A-2C: Caption-only semantic analyzer. "
            "All posts have full caption; run OpenAI analysis for "
            "Тема поста, Почему закреплен, Ключевые смыслы, Какой CTA, "
            "Куда ведет CTA, Роль в воронке."
        )
        if vis_ok:
            next_rec += " Stage 5A-2D (visual/OCR) can also proceed for Хук / первый экран."
        else:
            next_rec += " Stage 5A-2D (visual/OCR) still needs cover/display URLs."
    else:
        next_rec = (
            "Full caption still missing for some posts. "
            "Review actor output schema — 'caption' field may not be returned for all post types. "
            "Consider re-running with a different actor or resultsType."
        )

    return {
        "account":             ACCOUNT,
        "stage":               "stage5a2b",
        "run_timestamp":       run_ts,
        "source":              source_info.get("source", "unknown"),
        "actor":               source_info.get("actor", ACTOR_ID),
        "run_id":              source_info.get("run_id"),
        "dataset_id":          source_info.get("dataset_id"),
        "strategy":            source_info.get("strategy", "unknown"),
        "total_pinned_posts":  len(posts),
        "warnings":            warnings,
        "posts":               posts,
        "summary": {
            "posts_with_full_caption":       n_full_cap,
            "posts_with_cover_or_thumbnail": n_cover,
            "posts_with_carousel_items":     n_carousel,
            "caption_semantic_possible":     cap_sem_ok,
            "visual_ocr_input_possible":     vis_ok,
            "next_stage_recommendation":     next_rec,
        },
    }


# ── From-existing-raw normalizer ──────────────────────────────────────────

def normalize_from_existing_raw(pinned_refs: list[dict]) -> tuple[dict | None, str | None]:
    """
    Try to normalize from Stage 5A-1 raw posts file.
    Returns (normalized_output, error_or_None).
    """
    if not STAGE5A1_RAW_POSTS.exists():
        return None, (
            f"Stage 5A-1 raw posts file not found: {STAGE5A1_RAW_POSTS}. "
            "Run Stage 5A-1 first, or use --collect."
        )

    try:
        items = json.loads(STAGE5A1_RAW_POSTS.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"Cannot parse stage5a1_posts_for_pinned_raw.json: {e}"

    if not isinstance(items, list):
        return None, "stage5a1_posts_for_pinned_raw.json: expected a list of items"

    # Filter to pinned shortcodes only
    pinned_shortcodes = {p["shortcode"] for p in pinned_refs if p.get("shortcode")}
    pinned_ids        = {p["post_id"]   for p in pinned_refs if p.get("post_id")}
    filtered = [
        i for i in items
        if i.get("shortCode") in pinned_shortcodes
        or str(i.get("id") or "") in {str(p) for p in pinned_ids}
        or i.get("isPinned") is True
    ]

    # If pinned_refs is empty but isPinned=True items exist in raw, build synthetic refs
    # so match_items_to_pinned can drive the loop (it iterates refs, not items)
    if not pinned_refs and filtered:
        pinned_refs = [
            {
                "position":  idx + 1,
                "shortcode": item.get("shortCode") or item.get("shortcode"),
                "post_id":   str(item.get("id") or ""),
                "permalink": item.get("url") or item.get("permalink") or "",
                "media_type": item.get("type") or item.get("mediaType"),
            }
            for idx, item in enumerate(filtered)
        ]

    schema  = inspect_schema(filtered)
    matched = match_items_to_pinned(filtered, pinned_refs)
    output  = build_normalized_output(
        matched,
        schema,
        source_info={
            "source":   "stage5a1_existing_raw",
            "actor":    ACTOR_ID,
            "run_id":   None,
            "dataset_id": None,
            "strategy": "from_existing_stage5a1_raw",
        },
    )
    return output, None


# ── Apify collector ────────────────────────────────────────────────────────

def collect_from_apify(client, pinned_refs: list[dict]) -> tuple[list[dict], dict]:
    """
    Run Apify actor. Prefer direct post URL mode; fall back to account scrape.
    Returns (raw_items, source_info).
    """
    post_urls = [r["permalink"] for r in pinned_refs if r.get("permalink")]
    run_id    = None
    dataset_id = None

    if len(post_urls) == len(pinned_refs):
        # Preferred: direct post URL mode
        payload  = build_direct_payload(post_urls)
        strategy = "direct_post_urls"
        print(f"  Strategy: direct post URLs (preferred)")
        print(f"  directUrls: {post_urls}")
    else:
        # Fallback: account scrape, filter by shortcodes
        payload  = build_fallback_payload()
        strategy = "account_scrape_fallback"
        print(f"  Strategy: account posts scrape (fallback — some permalinks missing)")
        print(f"  resultsLimit: 30 (hard limit); will filter by pinned shortcodes")

    print(f"  Actor: {ACTOR_ID}")
    print(f"  Payload: {json.dumps(payload, ensure_ascii=False)}")

    run    = client.actor(ACTOR_ID).call(run_input=payload)
    run_id = run.get("id") or run.get("defaultDatasetId") or ""
    dataset_id = run.get("defaultDatasetId") or ""

    raw_items = list(client.dataset(dataset_id).iterate_items())

    if strategy == "account_scrape_fallback":
        # Filter to pinned shortcodes + isPinned flag
        pinned_shortcodes = {r["shortcode"] for r in pinned_refs if r.get("shortcode")}
        pinned_ids        = {r["post_id"]   for r in pinned_refs if r.get("post_id")}
        raw_items = [
            i for i in raw_items
            if i.get("shortCode") in pinned_shortcodes
            or str(i.get("id") or "") in {str(p) for p in pinned_ids}
            or i.get("isPinned") is True
        ]
        print(f"  Filtered to {len(raw_items)} pinned post(s)")

    source_info = {
        "source":     "apify",
        "actor":      ACTOR_ID,
        "run_id":     run_id,
        "dataset_id": dataset_id,
        "strategy":   strategy,
    }
    return raw_items, source_info


# ── Main entry points ─────────────────────────────────────────────────────

def run_from_existing_raw() -> dict:
    """Normalize from existing Stage 5A-1 raw output. No Apify call.

    If pinned_posts_index.json has 0 posts but the normalized output already
    exists (e.g. from a previous Apify run), reuse it without re-running.
    """
    index, errors = load_pinned_index()
    hard_errors = [e for e in errors if not e.startswith("WARNING")]
    if hard_errors:
        # Index has 0 pinned posts — try to fall through to raw file anyway;
        # normalize_from_existing_raw will pick up isPinned=True items directly.
        if STAGE5A1_RAW_POSTS.exists():
            print(
                f"  [INFO] pinned_posts_index has 0 posts — "
                f"falling back to isPinned=True scan of {STAGE5A1_RAW_POSTS.name}"
            )
        elif NORM_OUTPUT_PATH.exists():
            print(
                f"  [INFO] pinned_posts_index has 0 posts and raw not found — "
                f"reusing existing {NORM_OUTPUT_PATH.name}"
            )
            return json.loads(NORM_OUTPUT_PATH.read_text(encoding="utf-8"))
        else:
            raise ValueError("\n".join(hard_errors))

    pinned_refs = extract_pinned_refs(index)  # empty list when index has 0 posts
    output, err = normalize_from_existing_raw(pinned_refs)
    if err:
        raise ValueError(err)

    schema = inspect_schema([])  # recompute from raw items if needed
    _save_outputs(output, schema)
    return output


def run_collect(client, max_posts: int) -> dict:
    """Run Apify and collect full post details. Requires APIFY_TOKEN."""
    if max_posts < 1:
        raise ValueError(f"--max-posts must be at least 1, got {max_posts}")

    index, errors = load_pinned_index()
    hard_errors = [e for e in errors if not e.startswith("WARNING")]
    if hard_errors:
        raise ValueError("\n".join(hard_errors))

    pinned_refs  = extract_pinned_refs(index)
    raw_items, source_info = collect_from_apify(client, pinned_refs)

    # Save raw first
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe_raw = [_safe_item(i) for i in raw_items]
    RAW_OUTPUT_PATH.write_text(
        json.dumps(safe_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Raw saved: {RAW_OUTPUT_PATH.relative_to(BASE)}")

    schema  = inspect_schema(raw_items)
    matched = match_items_to_pinned(raw_items, pinned_refs)

    if len(matched) < len(pinned_refs):
        print(f"  WARNING: only {len(matched)}/{len(pinned_refs)} pinned posts matched in output")

    output = build_normalized_output(matched, schema, source_info)

    if len(output["posts"]) != len(pinned_refs):
        raise ValueError(
            f"Normalized output has {len(output['posts'])} posts, "
            f"expected {len(pinned_refs)}"
        )

    _save_outputs(output, schema)
    return output


def _save_outputs(output: dict, schema: dict):
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    NORM_OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    SCHEMA_SUMMARY_PATH.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Normalized: {NORM_OUTPUT_PATH.relative_to(BASE)}")
    print(f"  Schema:     {SCHEMA_SUMMARY_PATH.relative_to(BASE)}")
