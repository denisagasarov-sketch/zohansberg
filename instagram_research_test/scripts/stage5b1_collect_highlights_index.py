#!/usr/bin/env python3
"""
Stage 5B-1: Highlights Index Collector

Собирает список highlights профиля vlada_kliuiko через actor
singhera07/instagram-scraper, используя payload из actors_registry.json.

Главный вопрос: ведёт ли параметр limit=12 к ограничению вывода,
если пользователь ранее сообщал о 32 highlights?

Создаёт:
  data/raw/stage5b1_highlights_index_raw.json          (не коммитить)
  data/normalized/highlights_index.json                 (не коммитить)
  data/normalized/stage5b1_highlights_index_summary.json (не коммитить)

НЕ запускает OpenAI.
НЕ скачивает media.
НЕ собирает stories.

Запуск через stage5b1_run_local.py:
    python scripts/stage5b1_run_local.py --dry-run
    python scripts/stage5b1_run_local.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv

BASE     = Path(__file__).parent.parent  # instagram_research_test/
RAW_DIR  = BASE / "data/raw"
NORM_DIR = BASE / "data/normalized"

REGISTRY_PATH    = BASE / "config/actors_registry.json"
RAW_PATH         = RAW_DIR  / "stage5b1_highlights_index_raw.json"
INDEX_PATH       = NORM_DIR / "highlights_index.json"
SUMMARY_PATH     = NORM_DIR / "stage5b1_highlights_index_summary.json"

ACTOR_ID         = "singhera07/instagram-scraper"
ACCOUNT          = "vlada_kliuiko"
REGISTRY_KEY     = "singhera07/instagram-scraper"
REGISTRY_ACTION  = "highlights"

USER_REPORTED_PREVIOUS_COUNT = {
    "value":      32,
    "source":     "actors_registry.user_reported_previous_successful_run",
    "confidence": "medium",
}

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# Registry loader
# ---------------------------------------------------------------------------

def load_payload_from_registry() -> dict:
    """Read safe_input_payload_example from actors_registry.json. Stops on error."""
    if not REGISTRY_PATH.exists():
        raise SystemExit(
            f"[ERROR] actors_registry.json not found at {REGISTRY_PATH.relative_to(BASE)}. "
            "Create or restore config/actors_registry.json before running Stage 5B-1."
        )
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    actor_entry = registry.get("actors", {}).get(REGISTRY_KEY)
    if not actor_entry:
        raise SystemExit(
            f"[ERROR] Actor '{REGISTRY_KEY}' not found in actors_registry.json. "
            "Update the registry before running Stage 5B-1."
        )
    action_entry = actor_entry.get("confirmed_actions", {}).get(REGISTRY_ACTION)
    if not action_entry:
        raise SystemExit(
            f"[ERROR] Action '{REGISTRY_ACTION}' not found under '{REGISTRY_KEY}' "
            "in actors_registry.json. Update the registry."
        )
    payload = action_entry.get("safe_input_payload_example")
    if not payload:
        raise SystemExit(
            f"[ERROR] 'safe_input_payload_example' missing for action '{REGISTRY_ACTION}' "
            "in actors_registry.json. Update the registry."
        )
    return dict(payload)

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
# Safe item for raw save
# ---------------------------------------------------------------------------

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
# Raw shape detection + highlight list extraction
# ---------------------------------------------------------------------------

def extract_highlights(raw) -> tuple:
    """
    Try to extract a list of highlight dicts from raw output (unknown shape).
    Returns (highlights_list, raw_shape, extraction_path, extraction_errors).
    """
    extraction_errors = []

    if isinstance(raw, list):
        return raw, "list", "root", extraction_errors

    if isinstance(raw, dict):
        for key in ("data", "items", "results", "highlights"):
            val = raw.get(key)
            if isinstance(val, list):
                return val, "dict", f"root.{key}", extraction_errors
        # single object that might be a highlight
        if "id" in raw or "title" in raw:
            return [raw], "dict", "root (single object)", extraction_errors
        extraction_errors.append(
            f"Dict raw has keys {sorted(raw.keys())[:20]} but none of "
            "data/items/results/highlights found as list"
        )
        return [], "dict", "none", extraction_errors

    extraction_errors.append(f"Unexpected raw type: {type(raw).__name__}")
    return [], str(type(raw).__name__), "none", extraction_errors

# ---------------------------------------------------------------------------
# Field wrapper helpers
# ---------------------------------------------------------------------------

def field_ok(value, source_ref: str, notes: str = "") -> dict:
    return {"value": value, "data_status": "ok", "source_ref": source_ref,
            "confidence": "high", "notes": notes}

def field_missing(source_ref: str, notes: str = "") -> dict:
    return {"value": None, "data_status": "missing", "source_ref": source_ref,
            "confidence": None, "notes": notes}

# ---------------------------------------------------------------------------
# Normalize one highlight item
# ---------------------------------------------------------------------------

def normalize_highlight(item: dict, position: int) -> dict:
    src = "singhera07.highlights"

    raw_id = item.get("id")
    title  = item.get("title")
    cover  = item.get("croppedThumbnail") or item.get("cover")
    owner  = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    owner_id  = owner.get("id")
    owner_user = owner.get("username")

    return {
        "position": position,
        "highlight_id": field_ok(str(raw_id), f"{src}.id") if raw_id is not None
                        else field_missing(f"{src}.id", "id field absent in actor output"),
        "title": field_ok(title, f"{src}.title") if title
                 else field_missing(f"{src}.title", "title field absent"),
        "cover_image_url": field_ok(cover[:2048] if isinstance(cover, str) else cover,
                                    f"{src}.croppedThumbnail") if cover
                           else field_missing(f"{src}.croppedThumbnail",
                                             "croppedThumbnail absent — non-blocking"),
        "owner_id": field_ok(str(owner_id), f"{src}.owner.id") if owner_id is not None
                    else field_missing(f"{src}.owner.id", "owner.id absent — non-blocking"),
        "owner_username": field_ok(owner_user, f"{src}.owner.username") if owner_user
                          else field_missing(f"{src}.owner.username",
                                            "owner.username absent — non-blocking"),
        "stories_collection_ready": field_ok(
            True, "stage5b0_compatibility_check",
            "highlight_id compatible with igview-owner stories viewer based on Stage 5B-0"
        ),
    }

# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def deduplicate(highlights_raw: list) -> tuple:
    """Returns (unique_items, duplicates_count)."""
    seen_ids = set()
    unique   = []
    dupes    = 0
    for item in highlights_raw:
        hid = str(item.get("id", "")) if item.get("id") is not None else ""
        if hid and hid in seen_ids:
            dupes += 1
            continue
        if hid:
            seen_ids.add(hid)
        unique.append(item)
    return unique, dupes

# ---------------------------------------------------------------------------
# Limit behavior logic
# ---------------------------------------------------------------------------

def infer_limit_behavior(returned_count: int, requested_limit: int, status: str) -> str:
    if status == "FAIL" or returned_count == 0:
        return "unclear"
    if returned_count > requested_limit:
        return "likely_not_limited"
    if returned_count == requested_limit and returned_count < USER_REPORTED_PREVIOUS_COUNT["value"]:
        return "likely_limited"
    return "unclear"

# ---------------------------------------------------------------------------
# Build normalized outputs
# ---------------------------------------------------------------------------

def build_outputs(
    highlights_raw: list,
    raw_shape: str,
    extraction_path: str,
    extraction_errors: list,
    payload: dict,
    run_ts: str,
    run_meta: dict,
    actor_status: str,
    actor_errors: list,
) -> tuple:

    requested_limit = payload.get("limit", 0)
    unique_raw, dupes_count = deduplicate(highlights_raw)

    normalized = [normalize_highlight(item, pos + 1) for pos, item in enumerate(unique_raw)]

    # Quality counters
    with_id    = sum(1 for h in normalized if h["highlight_id"]["data_status"] == "ok")
    with_title = sum(1 for h in normalized if h["title"]["data_status"] == "ok")
    with_cover = sum(1 for h in normalized if h["cover_image_url"]["data_status"] == "ok")
    with_owner = sum(1 for h in normalized if h["owner_username"]["data_status"] == "ok")

    returned_count = len(unique_raw)

    # Status
    warnings = []
    if actor_status == "FAIL":
        status = "FAIL"
    elif with_id == 0:
        status = "FAIL"
    elif with_title < returned_count or with_cover < returned_count or with_owner < returned_count:
        status = "PARTIAL"
        if with_title < returned_count:
            warnings.append(f"{returned_count - with_title} highlights missing title")
        if with_cover < returned_count:
            warnings.append(f"{returned_count - with_cover} highlights missing croppedThumbnail (non-blocking)")
        if with_owner < returned_count:
            warnings.append(f"{returned_count - with_owner} highlights missing owner.username (non-blocking)")
    else:
        status = "OK"

    if dupes_count > 0:
        warnings.append(f"{dupes_count} duplicate highlights removed (deduplicated by id)")

    can_run_stage5b2 = status in ("OK", "PARTIAL") and with_id > 0
    limit_behavior   = infer_limit_behavior(returned_count, requested_limit, status)

    blockers = []
    if status == "FAIL":
        blockers.append("No highlights with id returned — cannot run Stage 5B-2")
    if extraction_errors:
        blockers.append(f"Extraction errors: {extraction_errors}")

    next_rec = _build_next_rec(status, limit_behavior, requested_limit, returned_count, can_run_stage5b2)

    index = {
        "account":              ACCOUNT,
        "stage":                "stage5b1",
        "actor":                ACTOR_ID,
        "run_timestamp":        run_ts,
        "planned_apify_calls":  run_meta["planned"],
        "actual_apify_calls":   run_meta["actual"],
        "apify_run_ids":        run_meta["run_ids"],
        "source_payload":       payload,
        "highlights_count":     len(highlights_raw),
        "unique_highlights_count": returned_count,
        "duplicates_count":     dupes_count,
        "highlights":           normalized,
        "raw_source":           "data/raw/stage5b1_highlights_index_raw.json",
    }

    summary = {
        "account":              ACCOUNT,
        "stage":                "stage5b1",
        "actor":                ACTOR_ID,
        "run_timestamp":        run_ts,
        "planned_apify_calls":  run_meta["planned"],
        "actual_apify_calls":   run_meta["actual"],
        "apify_run_ids":        run_meta["run_ids"],
        "requested_limit":      requested_limit,
        "returned_highlights_count":  returned_count,
        "unique_highlights_count":    returned_count,
        "duplicates_count":     dupes_count,
        "raw_shape":            raw_shape,
        "extraction_path":      extraction_path,
        "extraction_errors":    extraction_errors,
        "user_reported_previous_count": USER_REPORTED_PREVIOUS_COUNT,
        "limit_behavior":       limit_behavior,
        "highlights_with_id":           with_id,
        "highlights_with_title":        with_title,
        "highlights_with_cover":        with_cover,
        "highlights_with_owner_username": with_owner,
        "status":               status,
        "can_run_stage5b2":     can_run_stage5b2,
        "blockers":             blockers,
        "warnings":             warnings,
        "actor_errors":         actor_errors,
        "next_recommendation":  next_rec,
    }

    return index, summary


def _build_next_rec(status, limit_behavior, requested_limit, returned_count, can_run_stage5b2):
    parts = []
    if status == "FAIL":
        return (
            "Actor FAIL or no highlights returned. "
            "Check token, network, and actor availability before retrying."
        )
    if can_run_stage5b2:
        parts.append("highlights_index collected — Stage 5B-2 can proceed.")
    if limit_behavior == "likely_limited":
        parts.append(
            f"limit={requested_limit} appears to restrict output "
            f"(returned {returned_count}, user reported 32 previously). "
            "Consider testing with a higher limit after explicit user approval."
        )
    elif limit_behavior == "likely_not_limited":
        parts.append(
            f"limit={requested_limit} did not restrict output "
            f"(returned {returned_count} highlights). "
            "Current payload is suitable for production use."
        )
    else:
        parts.append(
            "limit behavior unclear — verify manually or compare with a no-limit run."
        )
    return " ".join(parts)

# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(token_errors: list, payload: dict):
    print("=== Stage 5B-1: DRY RUN ===")
    print(f"Actor:   {ACTOR_ID}")
    print(f"Account: {ACCOUNT}")
    print(f"Registry: {REGISTRY_PATH.relative_to(BASE)}")
    print()

    token = os.environ.get("APIFY_TOKEN", "")
    if token_errors:
        print("APIFY_TOKEN: INVALID")
        for e in token_errors:
            print(f"  [ERROR] {e}")
    else:
        print("APIFY_TOKEN: found, format OK (not printed)")

    print()
    print("Payload from actors_registry.json:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print()
    print("planned_apify_calls: 1")
    print("actual_apify_calls:  0  (dry-run)")
    print()
    print(f"user_reported_previous_count: {USER_REPORTED_PREVIOUS_COUNT['value']} "
          f"({USER_REPORTED_PREVIOUS_COUNT['source']})")
    print(f"requested_limit:              {payload.get('limit')}")
    print("limit_behavior will be checked after real run.")
    print()
    print("DRY RUN complete — Apify was NOT called.")

    run_ts = datetime.now(timezone.utc).isoformat()
    dry_summary = {
        "stage":               "stage5b1",
        "dry_run":             True,
        "actor":               ACTOR_ID,
        "account":             ACCOUNT,
        "run_timestamp":       run_ts,
        "planned_apify_calls": 1,
        "actual_apify_calls":  0,
        "token_valid":         not token_errors,
        "payload_from_registry": payload,
        "status":              "DRY_RUN",
        "can_run_stage5b2":    False,
    }
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(dry_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Real collect
# ---------------------------------------------------------------------------

def collect(client, payload: dict) -> dict:
    run_ts  = datetime.now(timezone.utc).isoformat()
    run_ids = []
    actual  = 0

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORM_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/1] Calling {ACTOR_ID} ...")
    print(f"  payload: {json.dumps(payload)}")

    raw          = None
    actor_errors = []
    raw_shape    = "none"
    extr_path    = "none"
    extr_errors  = []
    highlights_raw = []

    try:
        run = client.actor(ACTOR_ID).call(run_input=payload)
        actual += 1
        rid = run.get("id") or run.get("defaultDatasetId") or ""
        if rid:
            run_ids.append(rid)

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  dataset items: {len(items)}")

        # Dataset items could be a flat list of highlight objects,
        # or a single wrapper object per item.
        if len(items) == 1 and isinstance(items[0], dict):
            # Single wrapper — try extraction paths
            highlights_raw, raw_shape, extr_path, extr_errors = extract_highlights(items[0])
            if not highlights_raw:
                # Maybe the single item IS a highlight
                if items[0].get("id") or items[0].get("title"):
                    highlights_raw = items
                    raw_shape = "list(single_item)"
                    extr_path = "root"
        elif len(items) > 1:
            # Each dataset item is a highlight
            highlights_raw = items
            raw_shape = "list"
            extr_path = "root"
        else:
            highlights_raw, raw_shape, extr_path, extr_errors = extract_highlights(items)

        print(f"  highlights extracted: {len(highlights_raw)}")
        print(f"  raw_shape: {raw_shape}  extraction_path: {extr_path}")

        # Save raw
        safe_raw = [safe_item(i) if isinstance(i, dict) else i for i in highlights_raw]
        RAW_PATH.write_text(json.dumps(safe_raw, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  raw saved: {RAW_PATH.relative_to(BASE)}")

        actor_status = "OK" if highlights_raw else "FAIL"
        if not highlights_raw:
            actor_errors.append("No highlights extracted from actor output")

    except Exception as exc:
        actor_status = "FAIL"
        actor_errors.append(str(exc))
        print(f"  FAIL: {exc}")

    run_meta = {"planned": 1, "actual": actual, "run_ids": run_ids}

    index, summary = build_outputs(
        highlights_raw, raw_shape, extr_path, extr_errors,
        payload, run_ts, run_meta, actor_status, actor_errors,
    )

    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[Normalized outputs saved]")
    print(f"  {INDEX_PATH.relative_to(BASE)}")
    print(f"  {SUMMARY_PATH.relative_to(BASE)}")

    print(f"\nSUMMARY")
    print(f"  status:             {summary['status']}")
    print(f"  returned_count:     {summary['returned_highlights_count']}")
    print(f"  unique_count:       {summary['unique_highlights_count']}")
    print(f"  limit_behavior:     {summary['limit_behavior']}")
    print(f"  can_run_stage5b2:   {summary['can_run_stage5b2']}")
    if summary["warnings"]:
        for w in summary["warnings"]:
            print(f"  [WARN] {w}")

    return summary
