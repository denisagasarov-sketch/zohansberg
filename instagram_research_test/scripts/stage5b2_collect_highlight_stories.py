#!/usr/bin/env python3
"""
Stage 5B-2: Highlight Stories Collector

Читает highlight IDs из data/normalized/highlights_index.json,
делает ОДИН вызов automation-lab/instagram-stories-scraper для всех хайлайтов,
затем разбивает ответ по highlight_id и сохраняет raw + normalized outputs.

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
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT  = _args.account
RAW_DIR  = BASE / "data" / ACCOUNT / "raw"
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"

HIGHLIGHTS_INDEX_PATH = NORM_DIR / "highlights_index.json"
SUMMARY_PATH          = NORM_DIR / "stage5b2_highlights_stories_summary.json"
STORIES_INDEX_PATH    = NORM_DIR / "stage5b2_stories_index.json"

ACTOR_ID          = "automation-lab/instagram-stories-scraper"
ACTOR_ID_FALLBACK = "igview-owner/instagram-highlights-stories-viewer"

# Fields to probe in story items (automation-lab confirmed output)
STORY_PROBE_FIELDS = [
    "id", "type", "timestamp",
    "imageUrl", "videoUrl",
    "highlightId", "highlightTitle",
]

# igview-owner has different field names (used only in fallback path)
STORY_PROBE_FIELDS_FALLBACK = [
    "storyNumber", "storyId", "storyType",
    "imageUrl", "videoUrl",
    "takenAt", "duration",
]

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# Token / cookie validation
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


def validate_cookie(cookie: str) -> list:
    errors = []
    if not cookie:
        errors.append("INSTAGRAM_SESSION_COOKIE missing or empty in .env")
    elif any(c in cookie for c in ("\n", "\r")):
        errors.append("INSTAGRAM_SESSION_COOKIE contains newlines — likely corrupted")
    return errors

# ---------------------------------------------------------------------------
# Load and validate highlights_index.json
# ---------------------------------------------------------------------------

def load_highlights_index() -> list:
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
        hid_field   = h.get("highlight_id", {})
        title_field = h.get("title", {})
        hid_val    = hid_field.get("value") if isinstance(hid_field, dict) else None
        title_val  = title_field.get("value") if isinstance(title_field, dict) else None
        hid_status = hid_field.get("data_status") if isinstance(hid_field, dict) else None
        result.append({
            "position":     h.get("position", 0),
            "raw_id":       str(hid_val) if hid_val is not None else None,
            "highlight_id": None,
            "id_valid":     False,
            "title":        title_val or "—",
            "id_status":    hid_status,
        })
    return result

# ---------------------------------------------------------------------------
# ID normalization
# ---------------------------------------------------------------------------

def normalize_id(raw_id: str) -> tuple:
    """Returns (normalized_id, is_valid). Strips 'highlight:' prefix if present."""
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

def probe_stories(items: list, fields: list = None) -> dict:
    if fields is None:
        fields = STORY_PROBE_FIELDS
    if not items:
        return {
            "fields_found":      [],
            "fields_missing":    list(fields),
            "has_imageUrl":      False,
            "has_videoUrl":      False,
            "has_any_media_url": False,
            "sample_values":     {},
        }
    found_set = set()
    samples   = {}
    for item in items:
        for f in fields:
            if f in item and item[f] is not None and f not in found_set:
                found_set.add(f)
                samples[f] = safe_sample(item[f])

    has_img = any(item.get("imageUrl") for item in items)
    has_vid = any(item.get("videoUrl") for item in items)
    return {
        "fields_found":      [f for f in fields if f in found_set],
        "fields_missing":    [f for f in fields if f not in found_set],
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
        "raw_path":          f"data/{ACCOUNT}/raw/stage5b2_stories_{hid}_raw.json",
        "errors":            errors or [],
        "apify_run_id":      None,
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
    print(f"highlights total:    {len(highlights)}")
    print(f"highlights valid:    {len(valid_highlights)}")
    print(f"highlights invalid:  {invalid_count}")
    print(f"limit:               {limit if limit else 'none (all valid)'}")
    print(f"planned_apify_calls: 1  (single batch call, maxHighlights={len(to_process)})")
    print()

    token  = os.environ.get("APIFY_TOKEN", "")
    cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE", "")
    for label, val, errs in [
        ("APIFY_TOKEN", token, validate_token(token)),
        ("INSTAGRAM_SESSION_COOKIE", cookie, validate_cookie(cookie)),
    ]:
        if errs:
            print(f"{label}: INVALID")
            for e in errs:
                print(f"  [ERROR] {e}")
        else:
            print(f"{label}: found, format OK (not printed)")
    print()

    print(f"Payload: usernames=[{ACCOUNT!r}]  maxHighlights={len(to_process)}")
    print()
    print("Highlights to process:")
    for i, h in enumerate(to_process):
        print(f"  [{i+1:2}] {h['highlight_id']:20}  {h['title']}")
    if invalid_count:
        print(f"\n  [{invalid_count} invalid IDs will be skipped]")

    print()
    print("DRY RUN complete — Apify was NOT called.")

    run_ts = datetime.now(timezone.utc).isoformat()
    dry_summary = {
        "stage":               "stage5b2",
        "dry_run":             True,
        "actor":               ACTOR_ID,
        "account":             ACCOUNT,
        "run_timestamp":       run_ts,
        "highlights_total":    len(highlights),
        "highlights_valid":    len(valid_highlights),
        "highlights_invalid":  invalid_count,
        "limit":               limit,
        "planned_apify_calls": 1,
        "actual_apify_calls":  0,
        "status":              "DRY_RUN",
    }
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(dry_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Fallback: igview-owner — one call per highlight
# ---------------------------------------------------------------------------

def collect_one_igview(h: dict, client) -> dict:
    """Fallback per-highlight call using igview-owner (deprecated primary, now fallback)."""
    if not h["id_valid"]:
        return blank_highlight_result(
            h, "INVALID_ID",
            errors=[f"highlight_id '{h['raw_id']}' is not numeric"],
        )

    hid     = h["highlight_id"]
    payload = {"highlightId": hid}
    result  = blank_highlight_result(h, "FAIL")

    print(f"  [{h['position']:2}] {hid}  \"{h['title']}\" [igview-owner fallback] ...")

    try:
        run   = client.actor(ACTOR_ID_FALLBACK).call(run_input=payload)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        result["apify_run_id"] = run.get("id")

        if not items:
            result["status"] = "EMPTY_OR_INACCESSIBLE"
            result["errors"].append("igview-owner returned 0 stories")
        else:
            probe = probe_stories(items, fields=STORY_PROBE_FIELDS_FALLBACK)
            result["status"]            = "OK"
            result["stories_count"]     = len(items)
            result["fields_found"]      = probe["fields_found"]
            result["fields_missing"]    = probe["fields_missing"]
            result["has_imageUrl"]      = probe["has_imageUrl"]
            result["has_videoUrl"]      = probe["has_videoUrl"]
            result["has_any_media_url"] = probe["has_any_media_url"]
            result["sample_values"]     = probe["sample_values"]

            raw_path = RAW_DIR / f"stage5b2_stories_{hid}_raw.json"
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(
                json.dumps([safe_item(i) for i in items], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"       OK — {len(items)} stories  "
                  f"imageUrl={probe['has_imageUrl']}  videoUrl={probe['has_videoUrl']}")

    except Exception as exc:
        result["errors"].append(str(exc))
        print(f"       FAIL: {exc}")

    return result


# ---------------------------------------------------------------------------
# Real collect: single batch call → split by highlight_id
# ---------------------------------------------------------------------------

def collect_batch(client, to_process: list, cookie: str) -> tuple[dict, str | None]:
    """
    One Apify call for all highlights. Returns (items_by_hid, run_id).
    items_by_hid: {bare_highlight_id: [items]}
    """
    max_h   = len(to_process)
    # Actor input schema uses "usernames" (array), not "username" (string).
    # "includeHighlights" defaults to false — must be set explicitly.
    payload = {
        "usernames":        [ACCOUNT],
        "maxHighlights":    max_h,
        "sessionCookie":    cookie,
        "includeHighlights": True,
    }

    print(f"  Calling {ACTOR_ID}")
    print(f"  Payload: username={ACCOUNT!r}  maxHighlights={max_h}")

    run   = client.actor(ACTOR_ID).call(run_input=payload)
    run_id = run.get("id")
    all_items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    print(f"  Run {run_id}: {len(all_items)} total items returned")

    # Split by highlightId; skip active stories (no highlightId)
    by_hid: dict[str, list] = {}
    skipped_active = 0
    for item in all_items:
        raw_hid = item.get("highlightId") or ""
        if not raw_hid:
            skipped_active += 1
            continue
        # Strip "highlight:" prefix
        hid = str(raw_hid).removeprefix("highlight:")
        by_hid.setdefault(hid, []).append(item)

    if skipped_active:
        print(f"  Skipped {skipped_active} active story items (no highlightId)")

    return by_hid, run_id


def collect(client, highlights: list, limit: int) -> dict:
    run_ts = datetime.now(timezone.utc).isoformat()

    valid_highlights = [h for h in highlights if h["id_valid"]]
    to_process       = valid_highlights[:limit] if limit else valid_highlights

    print(f"\n[Stage 5B-2] {len(to_process)} highlights → 1 batch Apify call\n")

    cookie = os.environ.get("INSTAGRAM_SESSION_COOKIE", "").strip()
    cookie_errors = validate_cookie(cookie)
    if cookie_errors:
        for e in cookie_errors:
            print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    results    = []
    run_id     = None
    actual     = 0
    actor_used = ACTOR_ID
    using_fallback = False

    try:
        by_hid, run_id = collect_batch(client, to_process, cookie)
        actual = 1
    except Exception as exc:
        print(f"[WARN] automation-lab batch call failed: {exc}", file=sys.stderr)
        print(f"[WARN] Switching to fallback: {ACTOR_ID_FALLBACK} (per-highlight calls)",
              file=sys.stderr)
        using_fallback = True
        actor_used     = ACTOR_ID_FALLBACK

        for h in highlights:
            result = collect_one_igview(h, client)
            results.append(result)

        run_meta = {
            "planned": len(to_process),
            "actual":  sum(1 for r in results if r.get("apify_run_id")),
            "run_ids": [r["apify_run_id"] for r in results if r.get("apify_run_id")],
        }
        summary, stories_index = build_outputs(results, highlights, run_ts, run_meta,
                                               actor_used=actor_used)
        _save_outputs(summary, stories_index)
        return summary

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for h in highlights:
        if not h["id_valid"]:
            results.append(blank_highlight_result(
                h, "INVALID_ID",
                errors=[f"highlight_id '{h['raw_id']}' is not numeric"]
            ))
            continue

        hid    = h["highlight_id"]
        result = blank_highlight_result(h, "FAIL")
        result["apify_run_id"] = run_id

        if h not in to_process:
            # limit-excluded — don't add to results (counted in skipped_count)
            continue

        items = by_hid.get(hid, [])
        print(f"  [{h['position']:2}] {hid}  \"{h['title']}\" — {len(items)} stories")

        if not items:
            result["status"] = "EMPTY_OR_INACCESSIBLE"
            result["errors"].append("No stories returned for this highlight")
        else:
            probe = probe_stories(items)
            result["status"]            = "OK"
            result["stories_count"]     = len(items)
            result["fields_found"]      = probe["fields_found"]
            result["fields_missing"]    = probe["fields_missing"]
            result["has_imageUrl"]      = probe["has_imageUrl"]
            result["has_videoUrl"]      = probe["has_videoUrl"]
            result["has_any_media_url"] = probe["has_any_media_url"]
            result["sample_values"]     = probe["sample_values"]

            raw_path = RAW_DIR / f"stage5b2_stories_{hid}_raw.json"
            raw_path.write_text(
                json.dumps([safe_item(i) for i in items], ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        results.append(result)

    run_meta = {
        "planned": 1,
        "actual":  actual,
        "run_ids": [run_id] if run_id else [],
    }

    summary, stories_index = build_outputs(results, highlights, run_ts, run_meta,
                                           actor_used=actor_used)
    _save_outputs(summary, stories_index)
    return summary


def _save_outputs(summary: dict, stories_index: dict):
    NORM_DIR.mkdir(parents=True, exist_ok=True)
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

# ---------------------------------------------------------------------------
# Build normalized outputs
# ---------------------------------------------------------------------------

def build_outputs(results: list, highlights: list, run_ts: str, run_meta: dict,
                  actor_used: str = None) -> tuple:
    ok_count      = sum(1 for r in results if r["status"] == "OK")
    empty_count   = sum(1 for r in results if r["status"] == "EMPTY_OR_INACCESSIBLE")
    fail_count    = sum(1 for r in results if r["status"] == "FAIL")
    invalid_count = sum(1 for r in results if r["status"] == "INVALID_ID")
    skipped_count = len(highlights) - len(results)

    total_stories         = sum(r.get("stories_count", 0) for r in results)
    highlights_with_media = sum(1 for r in results if r.get("has_any_media_url"))

    can_analyze = ok_count > 0
    warnings    = []
    blockers    = []
    if empty_count:
        warnings.append(f"{empty_count} highlights returned 0 stories (EMPTY_OR_INACCESSIBLE)")
    if fail_count:
        blockers.append(f"{fail_count} highlights FAIL — check actor/token/cookie")
    if invalid_count:
        warnings.append(f"{invalid_count} highlights skipped — invalid ID format")
    if skipped_count:
        warnings.append(f"{skipped_count} highlights not processed (limit applied)")

    summary = {
        "stage":                  "stage5b2",
        "account":                ACCOUNT,
        "actor":                  actor_used or ACTOR_ID,
        "run_timestamp":          run_ts,
        "planned_apify_calls":    run_meta["planned"],
        "actual_apify_calls":     run_meta["actual"],
        "apify_run_ids":          run_meta["run_ids"],
        "highlights_total":       len(highlights),
        "highlights_processed":   len(results),
        "highlights_ok":          ok_count,
        "highlights_empty":       empty_count,
        "highlights_fail":        fail_count,
        "highlights_invalid":     invalid_count,
        "highlights_skipped":     skipped_count,
        "total_stories_count":    total_stories,
        "highlights_with_media":  highlights_with_media,
        "can_analyze_highlights": can_analyze,
        "blockers":               blockers,
        "warnings":               warnings,
        "results":                results,
    }

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
