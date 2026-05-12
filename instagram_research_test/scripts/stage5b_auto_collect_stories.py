#!/usr/bin/env python3
"""
Stage 5B-auto: automation-lab/instagram-stories-scraper collector.

Single Apify call per run. Returns active profile stories (last 24h)
and archived highlight stories grouped by highlightId.

Joins canonical title/position/cover from data/normalized/highlights_index.json
(produced by Stage 5B-1 via singhera07). automation-lab highlightTitle is
stored as secondary/raw field only — not used as source of truth.

NOTE: automation-lab is pay-per-story. Always use --max-highlights.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data/normalized"
RAW_DIR   = BASE / "data/raw"

ACTOR_ID              = "automation-lab/instagram-stories-scraper"
ACCOUNT               = "vlada_kliuiko"
HIGHLIGHTS_INDEX_PATH = NORM_DIR / "highlights_index.json"
RAW_OUTPUT_PATH       = RAW_DIR / "stage5b_auto_stories_raw.json"
SUMMARY_PATH          = NORM_DIR / "stage5b_auto_stories_summary.json"
STORIES_INDEX_PATH    = NORM_DIR / "stage5b_auto_stories_index.json"


# ---------------------------------------------------------------------------
# Validation helpers (credentials)
# ---------------------------------------------------------------------------

def validate_token(token: str) -> list[str]:
    errors = []
    if not token:
        errors.append("APIFY_TOKEN is empty")
    elif not token.startswith("apify_api_"):
        errors.append(f"APIFY_TOKEN does not start with 'apify_api_' (got prefix: {token[:10]}...)")
    return errors


def validate_cookie(cookie: str) -> list[str]:
    errors = []
    if not cookie:
        errors.append("INSTAGRAM_SESSION_COOKIE is empty — required for automation-lab actor")
    elif len(cookie) < 20:
        errors.append("INSTAGRAM_SESSION_COOKIE looks too short — check .env value")
    return errors


# ---------------------------------------------------------------------------
# Highlights index (canonical source from Stage 5B-1 / singhera07)
# ---------------------------------------------------------------------------

def load_highlights_index() -> list[dict]:
    if not HIGHLIGHTS_INDEX_PATH.exists():
        print(f"[ERROR] {HIGHLIGHTS_INDEX_PATH.relative_to(BASE)} not found.", file=sys.stderr)
        print("  Run Stage 5B-1 first to produce the highlights index.", file=sys.stderr)
        sys.exit(1)
    data = json.loads(HIGHLIGHTS_INDEX_PATH.read_text(encoding="utf-8"))
    highlights = data.get("highlights", [])
    if not highlights:
        print("[ERROR] highlights_index.json contains no highlights.", file=sys.stderr)
        sys.exit(1)
    return highlights


def build_canonical_index(highlights: list[dict]) -> dict:
    """
    Returns {bare_id: {position, canonical_title, canonical_cover}}
    bare_id = highlight_id with 'highlight:' prefix stripped.
    Field wrappers are unwrapped transparently.
    """
    index = {}
    for i, h in enumerate(highlights, start=1):
        raw_id = h.get("highlight_id", {})
        if isinstance(raw_id, dict):
            raw_id = raw_id.get("value", "")
        bare_id = str(raw_id or "").removeprefix("highlight:").strip()
        if not bare_id:
            continue

        title_field = h.get("title", {})
        title = title_field.get("value", "") if isinstance(title_field, dict) else str(title_field or "")

        cover_field = h.get("cover_image_url", {})
        cover = cover_field.get("value", "") if isinstance(cover_field, dict) else str(cover_field or "")

        index[bare_id] = {
            "position":        i,
            "canonical_title": title or None,
            "canonical_cover": cover or None,
        }
    return index


# ---------------------------------------------------------------------------
# Item normalization (automation-lab field names)
# ---------------------------------------------------------------------------

def normalize_item(item: dict) -> dict:
    """
    Map automation-lab field names to normalized schema.

    automation-lab fields:
      storyId, mediaUrl, mediaType, thumbnailUrl, timestamp,
      expiresAt, durationSecs, caption, isHighlight,
      highlightId, highlightTitle, hasLink, linkUrl,
      stickerTypes, scrapedAt
    """
    media_type = item.get("mediaType") or ""
    media_url  = item.get("mediaUrl")

    if media_type == "Image":
        image_url = media_url
        video_url = None
    elif media_type == "Video":
        image_url = None
        video_url = media_url
    else:
        image_url = media_url
        video_url = None

    return {
        "id":           item.get("storyId"),
        "mediaUrl":     media_url,
        "mediaType":    media_type or None,
        "thumbnailUrl": item.get("thumbnailUrl"),
        "imageUrl":     image_url,
        "videoUrl":     video_url,
        "timestamp":    item.get("timestamp"),
        "expiresAt":    item.get("expiresAt"),
        "durationSecs": item.get("durationSecs"),
        "caption":      item.get("caption"),
        "isHighlight":  item.get("isHighlight"),
        "highlightId":  item.get("highlightId"),
        "highlightTitle": item.get("highlightTitle"),   # raw from actor, secondary only
        "hasLink":      item.get("hasLink"),
        "linkUrl":      item.get("linkUrl"),
        "stickerTypes": item.get("stickerTypes"),
        "scrapedAt":    item.get("scrapedAt"),
    }


def split_items(
    raw_items: list[dict],
) -> tuple[list[dict], dict[str, list[dict]]]:
    """
    Returns:
      active_stories  — items with no highlightId (profile stories, last 24h)
      highlight_map   — {bare_id: [normalized_item, ...]}
                        bare_id = highlightId with 'highlight:' prefix stripped
    """
    active: list[dict] = []
    highlight_map: dict[str, list[dict]] = {}

    for item in raw_items:
        hid = (item.get("highlightId") or "").strip()
        if not hid:
            active.append(normalize_item(item))
        else:
            bare = hid.removeprefix("highlight:")
            highlight_map.setdefault(bare, []).append(normalize_item(item))

    return active, highlight_map


# ---------------------------------------------------------------------------
# Validation (normalized data quality)
# ---------------------------------------------------------------------------

def validate_normalized(
    active_stories: list[dict],
    highlight_map: dict[str, list[dict]],
) -> dict:
    """
    Returns stats dict. Calls sys.exit(1) on hard failures:
      - highlight_stories_count > 0 but all highlight mediaUrl are null
      - > 10% of normalized stories have null id
      - > 10% of normalized stories have null mediaUrl
    """
    all_stories = list(active_stories)
    for stories in highlight_map.values():
        all_stories.extend(stories)

    total = len(all_stories)
    image_count   = sum(1 for s in all_stories if s.get("mediaType") == "Image")
    video_count   = sum(1 for s in all_stories if s.get("mediaType") == "Video")
    null_id       = sum(1 for s in all_stories if s.get("id") is None)
    null_media    = sum(1 for s in all_stories if s.get("mediaUrl") is None)

    highlight_stories = [s for stories in highlight_map.values() for s in stories]
    hl_count = len(highlight_stories)

    stats = {
        "total_normalized":   total,
        "image_stories":      image_count,
        "video_stories":      video_count,
        "null_id_count":      null_id,
        "null_media_count":   null_media,
        "highlight_stories":  hl_count,
    }

    # Hard failure: highlights returned but all mediaUrl null
    if hl_count > 0 and all(s.get("mediaUrl") is None for s in highlight_stories):
        print(
            f"[ERROR] {hl_count} highlight stories returned but ALL have null mediaUrl.",
            file=sys.stderr,
        )
        print("  Field mapping may be wrong. Check raw item keys vs normalize_item().", file=sys.stderr)
        sys.exit(1)

    # Hard failure: > 10% null id
    if total > 0 and null_id / total > 0.10:
        pct = null_id / total * 100
        print(f"[ERROR] {null_id}/{total} ({pct:.1f}%) normalized stories have null id.", file=sys.stderr)
        print("  Expected field: storyId. Check raw item keys.", file=sys.stderr)
        sys.exit(1)

    # Hard failure: > 10% null mediaUrl
    if total > 0 and null_media / total > 0.10:
        pct = null_media / total * 100
        print(f"[ERROR] {null_media}/{total} ({pct:.1f}%) normalized stories have null mediaUrl.", file=sys.stderr)
        print("  Expected field: mediaUrl. Check raw item keys.", file=sys.stderr)
        sys.exit(1)

    return stats


# ---------------------------------------------------------------------------
# Build and save outputs (shared by collect and normalize_from_raw)
# ---------------------------------------------------------------------------

def _build_and_save(
    raw_items: list[dict],
    canonical_index: dict,
    total_in_index: int,
    run_meta: dict,
) -> dict:
    """
    Normalize raw_items, validate, build highlight entries, save outputs.
    run_meta keys: apify_run_id, apify_dataset_id, max_highlights_requested, mode
    """
    active_stories, highlight_map = split_items(raw_items)
    total_items = len(raw_items)

    val_stats = validate_normalized(active_stories, highlight_map)

    print(f"[INFO] Normalization stats:")
    print(f"  image_stories:   {val_stats['image_stories']}")
    print(f"  video_stories:   {val_stats['video_stories']}")
    print(f"  null_id_count:   {val_stats['null_id_count']}")
    print(f"  null_media_count:{val_stats['null_media_count']}")

    # Build highlight entries with canonical metadata from singhera07 index
    highlight_entries: list[dict] = []
    for bare_id, stories in highlight_map.items():
        canonical  = canonical_index.get(bare_id, {})
        auto_title = next(
            (s["highlightTitle"] for s in stories if s.get("highlightTitle")), None
        )
        highlight_entries.append({
            "highlight_id":         bare_id,
            "position":             canonical.get("position"),        # from singhera07
            "canonical_title":      canonical.get("canonical_title"), # from singhera07
            "canonical_cover":      canonical.get("canonical_cover"), # from singhera07
            "automation_lab_title": auto_title,                       # secondary / raw
            "stories_count":        len(stories),
            "stories":              stories,
        })

    highlight_entries.sort(key=lambda h: (h["position"] is None, h["position"] or 9999))

    max_highlights = run_meta.get("max_highlights_requested")

    # Warnings
    warnings: list[str] = []
    if max_highlights and len(highlight_map) < min(max_highlights, total_in_index):
        warnings.append(
            f"Returned {len(highlight_map)} highlights; expected up to "
            f"{min(max_highlights, total_in_index)}."
        )
    unmatched = [bid for bid in highlight_map if bid not in canonical_index]
    if unmatched:
        warnings.append(
            f"highlightIds not found in canonical index (title/position unavailable): {unmatched}"
        )

    can_analyze = len(highlight_entries) > 0 and any(
        e["stories_count"] > 0 for e in highlight_entries
    )

    summary = {
        "account":                  ACCOUNT,
        "actor":                    ACTOR_ID,
        "mode":                     run_meta.get("mode", "collect"),
        "run_timestamp":            datetime.now(timezone.utc).isoformat(),
        "apify_run_id":             run_meta.get("apify_run_id"),
        "apify_dataset_id":         run_meta.get("apify_dataset_id"),
        "max_highlights_requested": max_highlights,
        "total_items_returned":     total_items,
        "active_stories_count":     len(active_stories),
        "highlight_stories_count":  total_items - len(active_stories),
        "highlights_returned":      len(highlight_map),
        "highlights_in_index":      total_in_index,
        "can_analyze_highlights":   can_analyze,
        "normalization_stats":      val_stats,
        "warnings":                 warnings,
        "blockers":                 [] if can_analyze else ["No highlight stories returned."],
    }

    stories_index = {
        "account":              ACCOUNT,
        "actor":                ACTOR_ID,
        "mode":                 run_meta.get("mode", "collect"),
        "run_timestamp":        summary["run_timestamp"],
        "apify_run_id":         run_meta.get("apify_run_id"),
        "max_highlights":       max_highlights,
        "active_stories_count": len(active_stories),
        "active_stories":       active_stories,
        "highlights":           highlight_entries,
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    STORIES_INDEX_PATH.write_text(
        json.dumps(stories_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] Summary:       {SUMMARY_PATH.relative_to(BASE)}")
    print(f"[INFO] Stories index: {STORIES_INDEX_PATH.relative_to(BASE)}")

    return summary


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(max_highlights: int) -> None:
    highlights = load_highlights_index()
    canonical_index = build_canonical_index(highlights)
    total_in_index  = len(highlights)
    planned         = min(max_highlights, total_in_index)

    print("=== Stage 5B-auto: DRY RUN ===")
    print(f"Actor:               {ACTOR_ID}")
    print(f"Account:             {ACCOUNT}")
    print(f"Highlights in index: {total_in_index}")
    print(f"--max-highlights:    {max_highlights}")
    print(f"Planned scope:       {planned} highlights")
    print(f"planned_apify_calls: 1  (single call, NOT per-highlight)")
    print(f"actual_apify_calls:  0  (dry-run)")
    print()
    print("[COST WARNING] automation-lab charges per story item.")
    print(f"  Rough estimate: up to ~{planned * 60} story items billed.")
    print("  Reduce --max-highlights to limit cost.")
    print()
    print("Payload shape (sanitized — no secrets printed):")
    print(f"  usernames:          list[str], length=1  [\"{ACCOUNT}\"]")
    print( "  sessionCookie:      present / redacted")
    print( "  includeHighlights:  true")
    print(f"  maxHighlights:      {max_highlights}")
    print( "  includeProfile:     false")
    print( "  proxyConfiguration: {useApifyProxy: true}")
    print()
    print("Highlights that would be fetched (canonical order from singhera07 index):")
    ordered = sorted(canonical_index.items(), key=lambda kv: kv[1]["position"])
    for bare_id, meta in ordered[:planned]:
        title = meta["canonical_title"] or "—"
        print(f"  [{meta['position']:>2}] {bare_id}  \"{title}\"")
    print()
    print("[DRY RUN] No Apify call made. No files written.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Normalize-only mode (rebuild from existing raw, no Apify call)
# ---------------------------------------------------------------------------

def normalize_from_raw() -> dict:
    """
    Rebuild normalized outputs from data/raw/stage5b_auto_stories_raw.json
    without making any Apify call. Reads existing summary for run metadata.
    """
    if not RAW_OUTPUT_PATH.exists():
        print(f"[ERROR] Raw file not found: {RAW_OUTPUT_PATH.relative_to(BASE)}", file=sys.stderr)
        print("  Run without --normalize-only first to collect data from Apify.", file=sys.stderr)
        sys.exit(1)

    raw_items = json.loads(RAW_OUTPUT_PATH.read_text(encoding="utf-8"))
    total_items = len(raw_items)
    print(f"[INFO] Loaded {total_items} items from {RAW_OUTPUT_PATH.relative_to(BASE)}")

    # Recover run metadata from existing summary if available (best-effort)
    run_id     = None
    dataset_id = None
    max_hl     = None
    if SUMMARY_PATH.exists():
        prev = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        run_id     = prev.get("apify_run_id")
        dataset_id = prev.get("apify_dataset_id")
        max_hl     = prev.get("max_highlights_requested")

    highlights      = load_highlights_index()
    canonical_index = build_canonical_index(highlights)
    total_in_index  = len(highlights)

    run_meta = {
        "apify_run_id":             run_id,
        "apify_dataset_id":         dataset_id,
        "max_highlights_requested": max_hl,
        "mode":                     "normalize_only",
    }

    return _build_and_save(raw_items, canonical_index, total_in_index, run_meta)


# ---------------------------------------------------------------------------
# Real collect
# ---------------------------------------------------------------------------

def collect(client, max_highlights: int) -> dict:
    highlights      = load_highlights_index()
    canonical_index = build_canonical_index(highlights)
    total_in_index  = len(highlights)

    cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE", "")
    cookie_errors = validate_cookie(cookie)
    if cookie_errors:
        print("[ERROR] INSTAGRAM_SESSION_COOKIE validation failed:", file=sys.stderr)
        for e in cookie_errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    payload = {
        "usernames":          [ACCOUNT],
        "sessionCookie":      cookie,           # never printed
        "includeHighlights":  True,
        "maxHighlights":      max_highlights,
        "includeProfile":     False,
        "proxyConfiguration": {"useApifyProxy": True},
    }

    print(f"[INFO] Calling {ACTOR_ID} (single call) ...")
    print(f"[INFO] usernames=['{ACCOUNT}']  maxHighlights={max_highlights}  includeHighlights=true")
    print(f"[COST] pay-per-story. Rough estimate: up to ~{max_highlights * 60} items billed.")

    run        = client.actor(ACTOR_ID).call(run_input=payload)
    run_id     = run.get("id", "unknown")
    run_status = run.get("status", "UNKNOWN")
    dataset_id = run.get("defaultDatasetId", "")

    raw_items   = list(client.dataset(dataset_id).iterate_items())
    total_items = len(raw_items)

    # Dataset validation: SUCCEEDED with 0 items means actor-level error (wrong payload etc.)
    if total_items == 0:
        print(f"[ERROR] Actor status={run_status} but dataset has 0 items.", file=sys.stderr)
        print(f"  run_id={run_id}  dataset_id={dataset_id}", file=sys.stderr)
        print("  Check Apify run log for actor-level errors.", file=sys.stderr)
        sys.exit(1)

    highlight_item_count = sum(
        1 for item in raw_items if (item.get("highlightId") or "").strip()
    )
    if highlight_item_count == 0:
        print(
            f"[ERROR] includeHighlights=true but 0 highlight story items returned "
            f"(total_items={total_items}).",
            file=sys.stderr,
        )
        print(f"  run_id={run_id}", file=sys.stderr)
        print("  Possible causes: sessionCookie expired, highlights not accessible.", file=sys.stderr)
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(
        json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] Raw output: {RAW_OUTPUT_PATH.relative_to(BASE)} ({total_items} items)")

    run_meta = {
        "apify_run_id":             run_id,
        "apify_dataset_id":         dataset_id,
        "max_highlights_requested": max_highlights,
        "mode":                     "collect",
    }

    return _build_and_save(raw_items, canonical_index, total_in_index, run_meta)
