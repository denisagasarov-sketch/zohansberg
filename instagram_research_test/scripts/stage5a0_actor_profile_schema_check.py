#!/usr/bin/env python3
"""
Stage 5A-0: Actor Profile Schema Check

Проверяет, какие profile/pinned поля реально возвращает apify/instagram-scraper
для трёх режимов: details, profiles, posts_fallback.

НЕ запускает OpenAI.
НЕ скачивает media.
НЕ сохраняет base64.

Запуск из корня instagram_research_test/:
    python scripts/stage5a0_actor_profile_schema_check.py --dry-run
    python scripts/stage5a0_actor_profile_schema_check.py
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
import os

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent  # instagram_research_test/

RAW_DIR    = BASE / "data/raw"
NORM_DIR   = BASE / "data/normalized"
SUMMARY_PATH = NORM_DIR / "stage5a0_actor_schema_check.json"

ACCOUNT    = "vlada_kliuiko"
PROFILE_URL = "https://www.instagram.com/vlada_kliuiko/"
ACTOR_ID   = "apify/instagram-scraper"

DRY_RUN = "--dry-run" in sys.argv

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# Fields to probe in each mode's items
# ---------------------------------------------------------------------------

PROBE_FIELDS = [
    "biography",
    "bio",
    "fullName",
    "username",
    "externalUrl",
    "external_url",
    "followersCount",
    "followsCount",
    "followingCount",
    "postsCount",
    "ownerUsername",
    "ownerFullName",
    "ownerFollowersCount",
    "pinnedPosts",
    "isPinned",
    "isPinnedPost",
    "isPostPinned",
]

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

MODES = {
    "details": {
        "raw_path": "data/raw/stage5a0_profile_details_raw.json",
        "payload": {
            "directUrls":  [PROFILE_URL],
            "resultsType": "details",
            "resultsLimit": 1,
            "proxy":       {"useApifyProxy": True, "apifyProxyGroups": []},
        },
    },
    "profiles": {
        "raw_path": "data/raw/stage5a0_profile_profiles_raw.json",
        "payload": {
            "directUrls":  [PROFILE_URL],
            "resultsType": "profiles",
            "resultsLimit": 1,
            "proxy":       {"useApifyProxy": True, "apifyProxyGroups": []},
        },
    },
    "posts_fallback": {
        "raw_path": "data/raw/stage5a0_profile_posts_fallback_raw.json",
        "payload": {
            "directUrls":  [PROFILE_URL],
            "resultsType": "posts",
            "resultsLimit": 1,
            "proxy":       {"useApifyProxy": True, "apifyProxyGroups": []},
        },
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_sample(value):
    """Return a safe, compact representation for sample_values (no secrets, no bulk)."""
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


def probe_item(item: dict) -> dict:
    """
    Given one raw item dict, check PROBE_FIELDS and collect top-level fields.
    Returns dict with found/missing/null/sample_values.
    """
    top_level = sorted(item.keys())
    found   = []
    missing = []
    null    = []
    samples = {}

    for f in PROBE_FIELDS:
        if f in item:
            val = item[f]
            if val is None:
                null.append(f)
            else:
                found.append(f)
                samples[f] = safe_sample(val)
        else:
            missing.append(f)

    return {
        "top_level_fields": top_level,
        "fields_found":     found,
        "fields_missing":   missing,
        "fields_null":      null,
        "sample_values":    samples,
    }


def merge_probe_results(results: list) -> dict:
    """Merge probe results from multiple items (take union of found/null)."""
    if not results:
        return {
            "top_level_fields": [],
            "fields_found":     [],
            "fields_missing":   list(PROBE_FIELDS),
            "fields_null":      [],
            "sample_values":    {},
        }
    merged_top   = sorted(set(f for r in results for f in r["top_level_fields"]))
    merged_found = sorted(set(f for r in results for f in r["fields_found"]))
    merged_null  = sorted(set(f for r in results for f in r["fields_null"])
                          - set(merged_found))
    merged_miss  = [f for f in PROBE_FIELDS
                    if f not in merged_found and f not in merged_null]
    merged_samp  = {}
    for r in results:
        for k, v in r["sample_values"].items():
            if k not in merged_samp:
                merged_samp[k] = v
    return {
        "top_level_fields": merged_top,
        "fields_found":     merged_found,
        "fields_missing":   merged_miss,
        "fields_null":      merged_null,
        "sample_values":    merged_samp,
    }


# ---------------------------------------------------------------------------
# Token validation (no printing of key)
# ---------------------------------------------------------------------------

def validate_token(token: str):
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
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(token_errors):
    print("=== Stage 5A-0: DRY RUN ===")
    print(f"Account:    {ACCOUNT}")
    print(f"Actor:      {ACTOR_ID}")
    print(f"Profile URL:{PROFILE_URL}")
    print()

    token = os.environ.get("APIFY_TOKEN", "")
    if token_errors:
        print("APIFY_TOKEN: INVALID")
        for e in token_errors:
            print(f"  [ERROR] {e}")
    else:
        print("APIFY_TOKEN: found, format OK (not printed)")
    print()

    for mode_name, mode_cfg in MODES.items():
        print(f"--- Mode: {mode_name} ---")
        print(f"  raw_path:    {mode_cfg['raw_path']}")
        payload_safe = json.dumps(mode_cfg["payload"], ensure_ascii=False, indent=4)
        for line in payload_safe.splitlines():
            print(f"  {line}")
        print()

    print("DRY RUN complete — Apify was NOT called.")

    summary = {
        "stage":       "stage5a0_actor_profile_schema_check",
        "account":     ACCOUNT,
        "actor":       ACTOR_ID,
        "profile_url": PROFILE_URL,
        "dry_run":     True,
        "token_valid": not token_errors,
        "token_errors": token_errors,
        "modes_tested": {
            m: {"status": "DRY_RUN", "items_count": 0, "errors": []}
            for m in MODES
        },
        "profile_fields_available": {
            "bio_text":        "none",
            "full_name":       "none",
            "username":        "none",
            "external_url":    "none",
            "followers_count": "none",
            "following_count": "none",
            "posts_count":     "none",
        },
        "pinned_detection": {
            "available": False,
            "source":    "none",
            "field":     "none",
        },
        "can_use_actor_for_profile": False,
        "manual_needed":  [],
        "recommendation": "DRY RUN only — run without --dry-run to get real results.",
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Real run: one mode
# ---------------------------------------------------------------------------

def run_mode(mode_name: str, mode_cfg: dict, client) -> dict:
    raw_path = BASE / mode_cfg["raw_path"]
    result = {
        "status":          "FAIL",
        "items_count":     0,
        "top_level_fields": [],
        "fields_found":    [],
        "fields_missing":  list(PROBE_FIELDS),
        "fields_null":     [],
        "sample_values":   {},
        "raw_path":        mode_cfg["raw_path"],
        "errors":          [],
    }

    print(f"\n  Mode: {mode_name} ...")

    try:
        run = client.actor(ACTOR_ID).call(run_input=mode_cfg["payload"])
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        result["items_count"] = len(items)

        if not items:
            result["status"] = "FAIL"
            result["errors"].append(f"Actor returned 0 items for mode={mode_name}")
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps([], ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    FAIL — 0 items returned")
            return result

        # Probe fields from all items (typically 1)
        probe_results = [probe_item(item) for item in items]
        merged = merge_probe_results(probe_results)

        result["top_level_fields"] = merged["top_level_fields"]
        result["fields_found"]     = merged["fields_found"]
        result["fields_missing"]   = merged["fields_missing"]
        result["fields_null"]      = merged["fields_null"]
        result["sample_values"]    = merged["sample_values"]
        result["status"]           = "OK"

        print(f"    OK — {len(items)} item(s)")
        print(f"    fields_found:   {merged['fields_found']}")
        print(f"    fields_missing: {merged['fields_missing']}")
        print(f"    fields_null:    {merged['fields_null']}")

        # Save raw — no base64, truncate large string fields
        safe_items = []
        for item in items:
            safe_item = {}
            for k, v in item.items():
                if isinstance(v, str) and len(v) > 5000:
                    safe_item[k] = v[:5000] + "...[truncated]"
                elif isinstance(v, bytes):
                    safe_item[k] = "[bytes omitted]"
                else:
                    safe_item[k] = v
            safe_items.append(safe_item)

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(safe_items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    raw saved: {raw_path.relative_to(BASE)}")

    except Exception as exc:
        err_msg = str(exc)
        result["status"] = "FAIL"
        result["errors"].append(err_msg)
        print(f"    FAIL: {err_msg}")

    return result


# ---------------------------------------------------------------------------
# Build final summary
# ---------------------------------------------------------------------------

_PROFILE_FIELD_MAP = {
    "bio_text":        ["biography", "bio"],
    "full_name":       ["fullName"],
    "username":        ["username", "ownerUsername"],
    "external_url":    ["externalUrl", "external_url"],
    "followers_count": ["followersCount", "ownerFollowersCount"],
    "following_count": ["followingCount", "followsCount"],
    "posts_count":     ["postsCount"],
}

_PINNED_FIELDS = ["pinnedPosts", "isPinned", "isPinnedPost", "isPostPinned"]


def build_profile_fields_available(modes_results: dict) -> dict:
    available = {}
    for logical_name, candidates in _PROFILE_FIELD_MAP.items():
        source = "none"
        for mode_name, mode_res in modes_results.items():
            found = mode_res.get("fields_found", [])
            if any(c in found for c in candidates):
                source = mode_name
                break
        available[logical_name] = source
    return available


def build_pinned_detection(modes_results: dict) -> dict:
    for mode_name, mode_res in modes_results.items():
        found = mode_res.get("fields_found", [])
        for pf in _PINNED_FIELDS:
            if pf in found:
                return {
                    "available": True,
                    "source":    mode_name,
                    "field":     pf,
                }
    return {
        "available": False,
        "source":    "none",
        "field":     "none",
    }


def build_recommendation(
    profile_fields: dict,
    pinned_detection: dict,
    manual_needed: list,
    modes_results: dict,
) -> str:
    parts = []
    missing = [k for k, v in profile_fields.items() if v == "none"]
    if not missing:
        parts.append("Actor covers all profile fields — Stage 5A can be built on actor output.")
    else:
        parts.append(
            f"Actor missing: {missing}. "
            f"These must be provided via data/input/profile_manual.json."
        )
    if pinned_detection["available"]:
        parts.append(
            f"Pinned posts detectable via '{pinned_detection['field']}' in {pinned_detection['source']} mode."
        )
    else:
        parts.append(
            "Pinned posts NOT detectable by actor — use data/input/pinned_posts_manual.json."
        )
    profiles_status = modes_results.get("profiles", {}).get("status", "")
    if profiles_status == "FAIL":
        parts.append(
            "'profiles' resultsType is not supported by this actor and should not be used."
        )
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = validate_token(token)

    if DRY_RUN:
        run_dry_run(token_errors)
        return  # sys.exit called inside

    print("=== Stage 5A-0: Actor Profile Schema Check ===")
    print(f"Account:    {ACCOUNT}")
    print(f"Actor:      {ACTOR_ID}")
    print(f"Profile URL:{PROFILE_URL}")

    if token_errors:
        print("\nAPify token validation FAILED:")
        for e in token_errors:
            print(f"  [ERROR] {e}")
        summary = {
            "stage":       "stage5a0_actor_profile_schema_check",
            "account":     ACCOUNT,
            "actor":       ACTOR_ID,
            "profile_url": PROFILE_URL,
            "dry_run":     False,
            "token_valid": False,
            "token_errors": token_errors,
            "modes_tested": {
                m: {"status": "SKIPPED", "items_count": 0,
                    "top_level_fields": [], "fields_found": [],
                    "fields_missing": list(PROBE_FIELDS), "fields_null": [],
                    "sample_values": {}, "raw_path": cfg["raw_path"], "errors": []}
                for m, cfg in MODES.items()
            },
            "profile_fields_available": {k: "none" for k in _PROFILE_FIELD_MAP},
            "pinned_detection": {"available": False, "source": "none", "field": "none"},
            "can_use_actor_for_profile": False,
            "manual_needed": list(_PROFILE_FIELD_MAP.keys()) + ["pinned_posts"],
            "recommendation": "APIFY_TOKEN invalid — fix .env before running.",
        }
        NORM_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSummary saved (FAIL): {SUMMARY_PATH.relative_to(BASE)}")
        sys.exit(1)

    # Import apify-client only when we actually run
    try:
        from apify_client import ApifyClient
    except ImportError:
        raise SystemExit("apify-client not installed — run: pip install apify-client")

    client = ApifyClient(token)

    # Run each mode, collect results
    modes_results = {}
    for mode_name, mode_cfg in MODES.items():
        modes_results[mode_name] = run_mode(mode_name, mode_cfg, client)

    # Build derived summaries
    profile_fields  = build_profile_fields_available(modes_results)
    pinned_detect   = build_pinned_detection(modes_results)

    missing_logical = [k for k, v in profile_fields.items() if v == "none"]
    if not pinned_detect["available"]:
        missing_logical.append("pinned_posts")

    _REQUIRED_FOR_ACTOR = {
        "bio_text", "full_name", "username",
        "external_url", "followers_count", "posts_count",
    }
    can_use_actor = all(
        profile_fields.get(f, "none") != "none"
        for f in _REQUIRED_FOR_ACTOR
    )

    recommendation = build_recommendation(profile_fields, pinned_detect, missing_logical, modes_results)

    summary = {
        "stage":       "stage5a0_actor_profile_schema_check",
        "account":     ACCOUNT,
        "actor":       ACTOR_ID,
        "profile_url": PROFILE_URL,
        "dry_run":     False,
        "token_valid": True,
        "modes_tested": {
            mode_name: {
                "status":          res["status"],
                "items_count":     res["items_count"],
                "top_level_fields": res["top_level_fields"],
                "fields_found":    res["fields_found"],
                "fields_missing":  res["fields_missing"],
                "fields_null":     res["fields_null"],
                "sample_values":   res["sample_values"],
                "raw_path":        res["raw_path"],
                "errors":          res["errors"],
            }
            for mode_name, res in modes_results.items()
        },
        "profile_fields_available": profile_fields,
        "pinned_detection":          pinned_detect,
        "can_use_actor_for_profile": can_use_actor,
        "manual_needed":             missing_logical,
        "recommendation":            recommendation,
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*52}")
    print("SUMMARY")
    print(f"  can_use_actor_for_profile: {can_use_actor}")
    print(f"  manual_needed:             {missing_logical}")
    print(f"  pinned_detection:          {pinned_detect}")
    print(f"  profile_fields_available:")
    for k, v in profile_fields.items():
        print(f"    {k}: {v}")
    print(f"\nRecommendation: {recommendation}")
    print(f"\nSummary saved: {SUMMARY_PATH.relative_to(BASE)}")


if __name__ == "__main__":
    main()
