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
# Validation
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
# Item normalization
# ---------------------------------------------------------------------------

def normalize_item(item: dict) -> dict:
    """Normalized story item. Media URLs preserved (not downloaded)."""
    return {
        "id":               item.get("id"),
        "type":             item.get("type") or item.get("mediaType"),
        "timestamp":        item.get("timestamp") or item.get("takenAtTimestamp"),
        "imageUrl":         item.get("imageUrl") or item.get("displayUrl"),
        "videoUrl":         item.get("videoUrl"),
        "highlightId":      item.get("highlightId"),
        "highlightTitle":   item.get("highlightTitle"),  # raw from actor, secondary only
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
    print("Highlights that would be fetched (canonical order from singhera07 index):")
    ordered = sorted(canonical_index.items(), key=lambda kv: kv[1]["position"])
    for bare_id, meta in ordered[:planned]:
        title = meta["canonical_title"] or "—"
        print(f"  [{meta['position']:>2}] {bare_id}  \"{title}\"")
    print()
    print("Session cookie: read from .env at runtime (not shown in dry-run).")
    print("[DRY RUN] No Apify call made. No files written.")
    sys.exit(0)


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
        "username":      ACCOUNT,
        "maxHighlights": max_highlights,
        "sessionCookie": cookie,  # never printed
    }

    print(f"[INFO] Calling {ACTOR_ID} (single call) ...")
    print(f"[INFO] username={ACCOUNT}  maxHighlights={max_highlights}")
    print(f"[COST] pay-per-story. Rough estimate: up to ~{max_highlights * 60} items billed.")

    run        = client.actor(ACTOR_ID).call(run_input=payload)
    run_id     = run.get("id", "unknown")
    dataset_id = run.get("defaultDatasetId", "")

    raw_items   = list(client.dataset(dataset_id).iterate_items())
    total_items = len(raw_items)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(
        json.dumps(raw_items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[INFO] Raw output: {RAW_OUTPUT_PATH.relative_to(BASE)} ({total_items} items)")

    active_stories, highlight_map = split_items(raw_items)

    # Build highlight entries with canonical metadata joined from singhera07 index
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

    # Warnings
    warnings: list[str] = []
    if len(highlight_map) < min(max_highlights, total_in_index):
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
        "run_timestamp":            datetime.now(timezone.utc).isoformat(),
        "apify_run_id":             run_id,
        "apify_dataset_id":         dataset_id,
        "max_highlights_requested": max_highlights,
        "total_items_returned":     total_items,
        "active_stories_count":     len(active_stories),
        "highlight_stories_count":  total_items - len(active_stories),
        "highlights_returned":      len(highlight_map),
        "highlights_in_index":      total_in_index,
        "can_analyze_highlights":   can_analyze,
        "warnings":                 warnings,
        "blockers":                 [] if can_analyze else ["No highlight stories returned."],
    }

    stories_index = {
        "account":              ACCOUNT,
        "actor":                ACTOR_ID,
        "run_timestamp":        summary["run_timestamp"],
        "apify_run_id":         run_id,
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
