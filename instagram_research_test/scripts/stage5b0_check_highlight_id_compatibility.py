#!/usr/bin/env python3
"""
Stage 5B-0: Highlight ID Compatibility Check

Проверяет, подходят ли highlight IDs из singhera07/instagram-scraper
для actor igview-owner/instagram-highlights-stories-viewer.

Тестирует 2 ID:
  - control:   17874797856565339  (ранее вернул 57 stories)
  - candidate: 18110898391654002  (из highlights index scraper)

НЕ запускает OpenAI.
НЕ скачивает media.

Запуск:
    python scripts/stage5b0_check_highlight_id_compatibility.py --dry-run
    python scripts/stage5b0_check_highlight_id_compatibility.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv

BASE = Path(__file__).parent.parent  # instagram_research_test/
RAW_DIR  = BASE / "data/raw"
NORM_DIR = BASE / "data/normalized"
SUMMARY_PATH = NORM_DIR / "stage5b0_highlight_id_compatibility_summary.json"

ACTOR_ID = "igview-owner/instagram-highlights-stories-viewer"

HIGHLIGHT_IDS = [
    {"role": "control",   "original_id": "17874797856565339"},
    {"role": "candidate", "original_id": "18110898391654002"},
]

PROBE_FIELDS = [
    "storyNumber", "storyId", "storyType",
    "imageUrl", "videoUrl",
    "takenAt", "duration", "rawStoryData",
]

DRY_RUN = "--dry-run" in sys.argv

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# ID normalization
# ---------------------------------------------------------------------------

def normalize_id(original: str) -> dict:
    stripped = original.strip()
    if stripped.startswith("highlight:"):
        stripped = stripped[len("highlight:"):]
    valid = stripped.isdigit() and len(stripped) > 0
    return {
        "original_id":   original,
        "normalized_id": stripped,
        "id_valid":      valid,
    }

# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

def validate_token(token: str) -> list:
    errors = []
    if not token:
        errors.append("APIFY_TOKEN missing or empty in .env")
        return errors
    if not token.startswith("apify_api_"):
        errors.append("APIFY_TOKEN does not start with 'apify_api_' — check token format")
    if not token.isascii():
        errors.append("APIFY_TOKEN contains non-ASCII characters — likely corrupted")
    if any(c in token for c in (" ", "\t", "\n", "\r")):
        errors.append("APIFY_TOKEN contains whitespace — likely corrupted")
    return errors

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
        if "base64" in value[:30].lower() or len(value) > 300:
            return value[:300]
        return value
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
# Probe fields in items
# ---------------------------------------------------------------------------

def probe_items(items: list) -> dict:
    if not items:
        return {
            "fields_found":    [],
            "fields_missing":  list(PROBE_FIELDS),
            "has_imageUrl":    False,
            "has_videoUrl":    False,
            "has_any_media_url": False,
            "sample_values":   {},
        }

    found_set   = set()
    sample_vals = {}

    for item in items:
        for f in PROBE_FIELDS:
            if f in item and item[f] is not None and f not in found_set:
                found_set.add(f)
                sample_vals[f] = safe_sample(item[f])

    fields_found   = [f for f in PROBE_FIELDS if f in found_set]
    fields_missing = [f for f in PROBE_FIELDS if f not in found_set]

    has_image = any(
        item.get("imageUrl") for item in items if item.get("imageUrl")
    )
    has_video = any(
        item.get("videoUrl") for item in items if item.get("videoUrl")
    )

    return {
        "fields_found":      fields_found,
        "fields_missing":    fields_missing,
        "has_imageUrl":      has_image,
        "has_videoUrl":      has_video,
        "has_any_media_url": has_image or has_video,
        "sample_values":     sample_vals,
    }

# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def build_verdict(results: list, dry_run: bool) -> tuple:
    if dry_run:
        return "dry_run", False, "DRY RUN only — run without --dry-run to get real results."

    control   = next((r for r in results if r["role"] == "control"),   None)
    candidate = next((r for r in results if r["role"] == "candidate"), None)

    control_ok   = control   and control["status"]   == "OK" and control["stories_count"]   > 0
    candidate_ok = candidate and candidate["status"] == "OK" and candidate["stories_count"] > 0

    if not control_ok:
        verdict = "not_compatible"
        can_build = False
        rec = (
            "Control ID (17874797856565339) did not return stories. "
            "This ID previously returned 57 stories — the problem is likely in "
            "the current actor run, token, or network. "
            "Do NOT conclude that candidate IDs are incompatible. "
            "Fix the control ID run first, then re-test candidate IDs."
        )
        return verdict, can_build, rec

    if control_ok and candidate_ok:
        verdict = "compatible"
        can_build = True
        rec = (
            "Both control and candidate IDs returned stories with media URLs. "
            "Highlight IDs from singhera07/instagram-scraper are compatible with "
            "igview-owner/instagram-highlights-stories-viewer. "
            "Stage 5B can be built on this actor pair."
        )
        return verdict, can_build, rec

    # control ok, candidate not ok
    c_status = candidate["status"] if candidate else "UNKNOWN"
    verdict = "partially_compatible"
    can_build = "conditional"
    rec = (
        f"Viewer actor works (control returned {control['stories_count']} stories). "
        f"Candidate ID status: {c_status}. "
        "This may mean the candidate highlight is empty, deleted, or inaccessible, "
        "or the ID format requires additional normalization. "
        "Recommended: test 2-3 more candidate IDs from the highlights index "
        "before concluding incompatibility."
    )
    return verdict, can_build, rec

# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(token_errors: list):
    print("=== Stage 5B-0: DRY RUN ===")
    print(f"Actor: {ACTOR_ID}")
    print()

    token = os.environ.get("APIFY_TOKEN", "")
    if token_errors:
        print("APIFY_TOKEN: INVALID")
        for e in token_errors:
            print(f"  [ERROR] {e}")
    else:
        print("APIFY_TOKEN: found, format OK (not printed)")
    print()

    results = []
    for entry in HIGHLIGHT_IDS:
        norm = normalize_id(entry["original_id"])
        print(f"--- ID: {entry['original_id']}  role={entry['role']} ---")
        print(f"  normalized_id: {norm['normalized_id']}")
        print(f"  id_valid:      {norm['id_valid']}")
        if norm["id_valid"]:
            payload = {"highlightId": norm["normalized_id"]}
            print(f"  payload:       {json.dumps(payload)}")
        else:
            print(f"  [SKIP] ID invalid — actor would not be called")
        print()

        results.append({
            "role":             entry["role"],
            "original_id":      norm["original_id"],
            "normalized_id":    norm["normalized_id"],
            "id_valid":         norm["id_valid"],
            "status":           "DRY_RUN",
            "stories_count":    0,
            "fields_found":     [],
            "fields_missing":   list(PROBE_FIELDS),
            "has_imageUrl":     False,
            "has_videoUrl":     False,
            "has_any_media_url": False,
            "sample_values":    {},
            "raw_path":         f"data/raw/stage5b0_highlight_{norm['normalized_id']}_raw.json",
            "errors":           [],
        })

    summary = {
        "stage":                  "stage5b0_highlight_id_compatibility_check",
        "actor":                  ACTOR_ID,
        "highlight_ids_tested":   [e["original_id"] for e in HIGHLIGHT_IDS],
        "dry_run":                True,
        "token_valid":            not token_errors,
        "results":                results,
        "compatibility_verdict":  "dry_run",
        "can_build_stage5b":      False,
        "recommendation":         "DRY RUN only — run without --dry-run to get real results.",
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    print("\nDRY RUN complete — Apify was NOT called.")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Real run: one highlight ID
# ---------------------------------------------------------------------------

def run_highlight(entry: dict, client) -> dict:
    norm = normalize_id(entry["original_id"])
    role = entry["role"]

    base_result = {
        "role":             role,
        "original_id":      norm["original_id"],
        "normalized_id":    norm["normalized_id"],
        "id_valid":         norm["id_valid"],
        "status":           "FAIL",
        "stories_count":    0,
        "fields_found":     [],
        "fields_missing":   list(PROBE_FIELDS),
        "has_imageUrl":     False,
        "has_videoUrl":     False,
        "has_any_media_url": False,
        "sample_values":    {},
        "raw_path":         f"data/raw/stage5b0_highlight_{norm['normalized_id']}_raw.json",
        "errors":           [],
    }

    print(f"\n  ID: {norm['original_id']}  role={role}")

    if not norm["id_valid"]:
        base_result["status"] = "INVALID_ID"
        base_result["errors"].append(
            f"normalized_id '{norm['normalized_id']}' is not numeric — actor not called"
        )
        print(f"    INVALID_ID — skipping actor call")
        return base_result

    payload = {"highlightId": norm["normalized_id"]}
    print(f"    payload: {json.dumps(payload)}")

    try:
        run = client.actor(ACTOR_ID).call(run_input=payload)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        stories_count = len(items)
        base_result["stories_count"] = stories_count

        if stories_count == 0:
            base_result["status"] = "EMPTY_OR_INACCESSIBLE"
            base_result["errors"].append(
                "Actor returned 0 stories — highlight may be empty, deleted, or inaccessible"
            )
            print(f"    EMPTY_OR_INACCESSIBLE — 0 stories returned")
        else:
            probe = probe_items(items)
            base_result["status"]         = "OK"
            base_result["fields_found"]   = probe["fields_found"]
            base_result["fields_missing"] = probe["fields_missing"]
            base_result["has_imageUrl"]   = probe["has_imageUrl"]
            base_result["has_videoUrl"]   = probe["has_videoUrl"]
            base_result["has_any_media_url"] = probe["has_any_media_url"]
            base_result["sample_values"]  = probe["sample_values"]
            print(f"    OK — {stories_count} stories")
            print(f"    fields_found:   {probe['fields_found']}")
            print(f"    has_imageUrl:   {probe['has_imageUrl']}")
            print(f"    has_videoUrl:   {probe['has_videoUrl']}")

        # Save raw
        raw_path = BASE / base_result["raw_path"]
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        safe_items = [safe_item(i) for i in items]
        raw_path.write_text(json.dumps(safe_items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    raw saved: {raw_path.relative_to(BASE)}")

    except Exception as exc:
        base_result["status"] = "FAIL"
        base_result["errors"].append(str(exc))
        print(f"    FAIL: {exc}")

    return base_result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = validate_token(token)

    if DRY_RUN:
        run_dry_run(token_errors)
        return

    print("=== Stage 5B-0: Highlight ID Compatibility Check ===")
    print(f"Actor: {ACTOR_ID}")

    if token_errors:
        print("\nAPify token validation FAILED:")
        for e in token_errors:
            print(f"  [ERROR] {e}")
        sys.exit(1)

    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client = ApifyClient(token)
    results = []

    for entry in HIGHLIGHT_IDS:
        result = run_highlight(entry, client)
        results.append(result)

    verdict, can_build, recommendation = build_verdict(results, dry_run=False)

    summary = {
        "stage":                  "stage5b0_highlight_id_compatibility_check",
        "actor":                  ACTOR_ID,
        "highlight_ids_tested":   [e["original_id"] for e in HIGHLIGHT_IDS],
        "dry_run":                False,
        "token_valid":            True,
        "results":                results,
        "compatibility_verdict":  verdict,
        "can_build_stage5b":      can_build,
        "recommendation":         recommendation,
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*52}")
    print("SUMMARY")
    print(f"  compatibility_verdict: {verdict}")
    print(f"  can_build_stage5b:     {can_build}")
    for r in results:
        print(f"  [{r['role']:9}] {r['original_id']}  status={r['status']}  stories={r['stories_count']}")
    print(f"\nRecommendation: {recommendation}")
    print(f"\nSummary saved: {SUMMARY_PATH.relative_to(BASE)}")


if __name__ == "__main__":
    main()
