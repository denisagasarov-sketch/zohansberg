#!/usr/bin/env python3
"""
Stage 5B-2: Highlight Stories Collector

Читает highlight IDs из data/normalized/highlights_index.json,
вызывает igview-owner/instagram-highlights-stories-viewer для каждого
валидного ID и сохраняет raw + normalized outputs.

Создаёт:
  data/raw/stage5b2_stories_{id}_raw.json           (на каждый highlight)
  data/normalized/stage5b2_highlights_stories_summary.json
  data/normalized/stage5b2_stories_index.json

НЕ запускает OpenAI.
НЕ скачивает media.
НЕ собирает highlights index — использует готовый из Stage 5B-1.

Запуск через stage5b2_run_local.py:
    python scripts/stage5b2_run_local.py --dry-run
    python scripts/stage5b2_run_local.py
    python scripts/stage5b2_run_local.py --limit 3
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv

BASE     = Path(__file__).parent.parent
RAW_DIR  = BASE / "data/raw"
NORM_DIR = BASE / "data/normalized"

HIGHLIGHTS_INDEX_PATH = NORM_DIR / "highlights_index.json"
SUMMARY_PATH          = NORM_DIR / "stage5b2_highlights_stories_summary.json"
STORIES_INDEX_PATH    = NORM_DIR / "stage5b2_stories_index.json"

ACTOR_ID = "igview-owner/instagram-highlights-stories-viewer"
ACCOUNT  = "vlada_kliuiko"

# Fields to probe in story items (from igview-owner confirmed output)
STORY_PROBE_FIELDS = [
    "storyNumber", "storyId", "storyType",
    "imageUrl", "videoUrl",
    "takenAt", "duration", "rawStoryData",
]

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def validate_token(token: str) -> list:
    errors = []
    if not token:
        errors.append("APIFY_TOKEN missing or empty in .env")
        return errors
    if not token.startswith("apify_api_"):
        errors.append("APIFY_TOKEN does not start with 'apify_api_'")
    if not token.isascii():
        errors.append("APIFY_TOKEN contains non-ASCII characters")
    if any(c in token for c in (" ", "\t", "\n", "\r")):
        errors.append("APIFY_TOKEN contains whitespace")
    return errors

# ---------------------------------------------------------------------------
# Load and validate highlights_index.json
# ---------------------------------------------------------------------------

def load_highlights_index() -> list:
    """
    Load highlights from data/normalized/highlights_index.json.
    Returns list of dicts with keys: position, highlight_id_value, title_value, raw_id.
    Raises SystemExit if file not found.
    """
    if not HIGHLIGHTS_INDEX_PATH.exists():
        raise SystemExit(
            f"[ERROR] highlights_index.json not found at "
            f"{HIGHLIGHTS_INDEX_PATH.relative_to(BASE)}.\n"
            "Run Stage 5B-1 first: python scripts/stage5b1_run_local.py"
        )
    raw = json.loads(HIGHLIGHTS_INDEX_PATH.read_text(encoding="utf-8"))
    highlights_raw = raw.get("highlights", [])
    result = []
    for h in highlights_raw:
        hid_field  = h.get("highlight_id", {})
        title_field = h.get("title", {})
        hid_val    = hid_field.get("value") if isinstance(hid_field, dict) else None
        title_val  = title_field.get("value") if isinstance(title_field, dict) else None
        hid_status = hid_field.get("data_status") if isinstance(hid_field, dict) else None
        result.append({
            "position":       h.get("position", 0),
            "raw_id":         str(hid_val) if hid_val is not None else None,
            "highlight_id":   None,   # normalized (no "highlight:" prefix), filled below
            "id_valid":       False,
            "title":          title_val or "—",
            "id_status":      hid_status,
        })
    return result

# ---------------------------------------------------------------------------
# ID normalization
# ---------------------------------------------------------------------------

def normalize_id(raw_id: str) -> tuple:
    """Returns (normalized_id, is_valid)."""
    if not raw_id:
        return None, False
    stripped = raw_id.strip()
    if stripped.lower().startswith("highlight:"):
        stripped = stripped[len("highlight:"):]
    valid = stripped.isdigit() and len(stripped) > 0
    return stripped, valid


def prepare_highlights(highlights: list) -> list:
    for h in highlights:
        norm, valid = normalize_id(h["raw_id"])
        h["highlight_id"] = norm
        h["id_valid"]     = valid
    return highlights

# ---------------------------------------------------------------------------
# Safe sample helpers
# ---------------------------------------------------------------------------

def safe_sample(value) -> object:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:300]
    if isinstance(value, list):
        return f"list(len={len(value)})"
    if isinstance(value, dict):
        return f"object(keys={sorted(value.keys())[:15]})"
    return str(value)[:300]


def safe_item(item: dict) -> dict:
    result = {}
    for k, v in item.items():
        if isinstance(v, str) and len(v) > 5000:
            result[k] = v[:5000] + "...[truncated]"
        elif isinstance(v, bytes):
            result[k] = "[bytes omitted]"
        else:
            result[k] = v
    return result

# ---------------------------------------------------------------------------
# Probe story items
# ---------------------------------------------------------------------------

def probe_stories(items: list) -> dict:
    if not items:
        return {
            "fields_found":      [],
            "fields_missing":    list(STORY_PROBE_FIELDS),
            "has_imageUrl":      False,
            "has_videoUrl":      False,
            "has_any_media_url": False,
            "sample_values":     {},
        }
    found_set = set()
    samples   = {}
    for item in items:
        for f in STORY_PROBE_FIELDS:
            if f in item and item[f] is not None and f not in found_set:
                found_set.add(f)
                samples[f] = safe_sample(item[f])

    has_img = any(item.get("imageUrl") for item in items)
    has_vid = any(item.get("videoUrl") for item in items)
    return {
        "fields_found":      [f for f in STORY_PROBE_FIELDS if f in found_set],
        "fields_missing":    [f for f in STORY_PROBE_FIELDS if f not in found_set],
        "has_imageUrl":      has_img,
        "has_videoUrl":      has_vid,
        "has_any_media_url": has_img or has_vid,
        "sample_values":     samples,
    }

# ---------------------------------------------------------------------------
# Build one highlight result dict
# ---------------------------------------------------------------------------

def blank_highlight_result(h: dict, status: str, errors: list = None) -> dict:
    hid = h["highlight_id"] or h["raw_id"] or "unknown"
    return {
        "position":          h["position"],
        "highlight_id":      h["highlight_id"],
        "raw_id":            h["raw_id"],
        "id_valid":          h["id_valid"],
        "title":             h["title"],
        "status":            status,
        "stories_count":     0,
        "fields_found":      [],
        "fields_missing":    list(STORY_PROBE_FIELDS),
        "has_imageUrl":      False,
        "has_videoUrl":      False,
        "has_any_media_url": False,
        "sample_values":     {},
        "raw_path":          f"data/raw/stage5b2_stories_{hid}_raw.json",
        "errors":            errors or [],
    }

# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(highlights: list, limit: int):
    valid_highlights = [h for h in highlights if h["id_valid"]]
    invalid_count    = len(highlights) - len(valid_highlights)
    to_process       = valid_highlights[:limit] if limit else valid_highlights

    print("=== Stage 5B-2: DRY RUN ===")
    print(f"Actor:   {ACTOR_ID}")
    print(f"Account: {ACCOUNT}")
    print(f"Source:  {HIGHLIGHTS_INDEX_PATH.relative_to(BASE)}")
    print()
    print(f"highlights total:   {len(highlights)}")
    print(f"highlights valid:   {len(valid_highlights)}")
    print(f"highlights invalid: {invalid_count}")
    print(f"limit:              {limit if limit else 'none (all valid)'}")
    print(f"planned_apify_calls: {len(to_process)}")
    print()

    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = validate_token(token)
    if token_errors:
        print("APIFY_TOKEN: INVALID")
        for e in token_errors:
            print(f"  [ERROR] {e}")
    else:
        print("APIFY_TOKEN: found, format OK (not printed)")
    print()

    print("Planned calls (highlight_id → title):")
    for i, h in enumerate(to_process):
        print(f"  [{i+1:2}] {h['highlight_id']:20}  {h['title']}")
    if invalid_count:
        print(f"\n  [{invalid_count} invalid IDs will be skipped]")

    print()
    print("DRY RUN complete — Apify was NOT called.")

    # Save dry-run summary
    run_ts = datetime.now(timezone.utc).isoformat()
    dry_summary = {
        "stage":                 "stage5b2",
        "dry_run":               True,
        "actor":                 ACTOR_ID,
        "account":               ACCOUNT,
        "run_timestamp":         run_ts,
        "highlights_total":      len(highlights),
        "highlights_valid":      len(valid_highlights),
        "highlights_invalid":    invalid_count,
        "limit":                 limit,
        "planned_apify_calls":   len(to_process),
        "actual_apify_calls":    0,
        "status":                "DRY_RUN",
    }
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(dry_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Real collect: one highlight
# ---------------------------------------------------------------------------

def collect_one(h: dict, client) -> dict:
    if not h["id_valid"]:
        return blank_highlight_result(
            h, "INVALID_ID",
            errors=[f"highlight_id '{h['raw_id']}' is not numeric after normalization"]
        )

    hid      = h["highlight_id"]
    payload  = {"highlightId": hid}
    raw_path = BASE / f"data/raw/stage5b2_stories_{hid}_raw.json"
    result   = blank_highlight_result(h, "FAIL")
    result["raw_path"] = str(raw_path.relative_to(BASE))

    print(f"  [{h['position']:2}] {hid}  \"{h['title']}\" ...")

    try:
        run   = client.actor(ACTOR_ID).call(run_input=payload)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        result["stories_count"] = len(items)

        if not items:
            result["status"] = "EMPTY_OR_INACCESSIBLE"
            result["errors"].append("Actor returned 0 stories — highlight may be empty or inaccessible")
            print(f"       EMPTY_OR_INACCESSIBLE — 0 stories")
        else:
            probe = probe_stories(items)
            result["status"]           = "OK"
            result["fields_found"]     = probe["fields_found"]
            result["fields_missing"]   = probe["fields_missing"]
            result["has_imageUrl"]     = probe["has_imageUrl"]
            result["has_videoUrl"]     = probe["has_videoUrl"]
            result["has_any_media_url"] = probe["has_any_media_url"]
            result["sample_values"]    = probe["sample_values"]
            print(f"       OK — {len(items)} stories  "
                  f"imageUrl={probe['has_imageUrl']}  videoUrl={probe['has_videoUrl']}")

        # Save raw
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        safe_items = [safe_item(i) for i in items]
        raw_path.write_text(json.dumps(safe_items, ensure_ascii=False, indent=2), encoding="utf-8")

    except Exception as exc:
        result["status"] = "FAIL"
        result["errors"].append(str(exc))
        print(f"       FAIL: {exc}")

    return result

# ---------------------------------------------------------------------------
# Build normalized outputs
# ---------------------------------------------------------------------------

def build_outputs(results: list, highlights: list, run_ts: str, run_meta: dict) -> tuple:
    ok_count      = sum(1 for r in results if r["status"] == "OK")
    empty_count   = sum(1 for r in results if r["status"] == "EMPTY_OR_INACCESSIBLE")
    fail_count    = sum(1 for r in results if r["status"] == "FAIL")
    invalid_count = sum(1 for r in results if r["status"] == "INVALID_ID")
    skipped_count = len(highlights) - len(results)

    total_stories = sum(r.get("stories_count", 0) for r in results)
    highlights_with_media = sum(1 for r in results if r.get("has_any_media_url"))

    can_analyze = ok_count > 0
    warnings    = []
    blockers    = []
    if empty_count:
        warnings.append(f"{empty_count} highlights returned 0 stories (EMPTY_OR_INACCESSIBLE)")
    if fail_count:
        blockers.append(f"{fail_count} highlights FAIL — check actor/token")
    if invalid_count:
        warnings.append(f"{invalid_count} highlights skipped — invalid ID format")
    if skipped_count:
        warnings.append(f"{skipped_count} highlights not processed (limit applied)")

    summary = {
        "stage":                 "stage5b2",
        "account":               ACCOUNT,
        "actor":                 ACTOR_ID,
        "run_timestamp":         run_ts,
        "planned_apify_calls":   run_meta["planned"],
        "actual_apify_calls":    run_meta["actual"],
        "apify_run_ids":         run_meta["run_ids"],
        "highlights_total":      len(highlights),
        "highlights_processed":  len(results),
        "highlights_ok":         ok_count,
        "highlights_empty":      empty_count,
        "highlights_fail":       fail_count,
        "highlights_invalid":    invalid_count,
        "highlights_skipped":    skipped_count,
        "total_stories_count":   total_stories,
        "highlights_with_media": highlights_with_media,
        "can_analyze_highlights": can_analyze,
        "blockers":              blockers,
        "warnings":              warnings,
        "results":               results,
    }

    # Lightweight stories index (position, id, title, status, count, raw_path)
    stories_index = {
        "stage":         "stage5b2",
        "account":       ACCOUNT,
        "run_timestamp": run_ts,
        "highlights": [
            {
                "position":      r["position"],
                "highlight_id":  r["highlight_id"],
                "title":         r["title"],
                "status":        r["status"],
                "stories_count": r["stories_count"],
                "has_imageUrl":  r["has_imageUrl"],
                "has_videoUrl":  r["has_videoUrl"],
                "raw_path":      r["raw_path"],
            }
            for r in results
        ],
    }

    return summary, stories_index

# ---------------------------------------------------------------------------
# Real collect: all highlights
# ---------------------------------------------------------------------------

def collect(client, highlights: list, limit: int) -> dict:
    run_ts  = datetime.now(timezone.utc).isoformat()
    run_ids = []
    actual  = 0

    valid_highlights = [h for h in highlights if h["id_valid"]]
    to_process       = valid_highlights[:limit] if limit else valid_highlights

    print(f"\n[Stage 5B-2] Processing {len(to_process)} highlights ...")
    print(f"  (total valid: {len(valid_highlights)}, limit: {limit if limit else 'none'})\n")

    results = []
    for h in highlights:
        if h not in to_process:
            # Record skipped invalid or limit-excluded
            if not h["id_valid"]:
                results.append(blank_highlight_result(
                    h, "INVALID_ID",
                    errors=[f"highlight_id '{h['raw_id']}' is not numeric"]
                ))
            # limit-excluded: not added to results, counted in skipped_count
            continue

        result = collect_one(h, client)
        if result["status"] not in ("INVALID_ID", "FAIL"):
            actual += 1
        results.append(result)

    run_meta = {
        "planned": len(to_process),
        "actual":  actual,
        "run_ids": run_ids,
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)

    summary, stories_index = build_outputs(results, highlights, run_ts, run_meta)

    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    STORIES_INDEX_PATH.write_text(json.dumps(stories_index, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[Normalized outputs saved]")
    print(f"  {SUMMARY_PATH.relative_to(BASE)}")
    print(f"  {STORIES_INDEX_PATH.relative_to(BASE)}")

    print(f"\nSUMMARY")
    print(f"  processed:    {summary['highlights_processed']}")
    print(f"  OK:           {summary['highlights_ok']}")
    print(f"  empty:        {summary['highlights_empty']}")
    print(f"  fail:         {summary['highlights_fail']}")
    print(f"  total_stories:{summary['total_stories_count']}")
    print(f"  with_media:   {summary['highlights_with_media']}")
    print(f"  can_analyze:  {summary['can_analyze_highlights']}")

    return summary
