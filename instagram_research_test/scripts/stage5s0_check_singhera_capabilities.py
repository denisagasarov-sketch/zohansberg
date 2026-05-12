#!/usr/bin/env python3
"""
Stage 5S-0: Singhera07 Capability Check

Проверяет, может ли singhera07/instagram-scraper заменить или дополнить
текущие actors в Instagram competitor research pipeline.

Проверяет 4 capability-блока:
  1. profile          — замена apify/instagram-scraper details
  2. posts_pinned     — замена apify/instagram-scraper posts
  3. highlights_index — замена scrapio/instagram-highlights-scraper
  4. highlight_stories — замена igview-owner/instagram-highlights-stories-viewer

ВАЖНО ПО INPUT SCHEMA:
  Перед каждым actor call обязательно найти подтверждённый payload в project files.
  Если payload не найден — action помечается SKIPPED, actor НЕ вызывается.

  Результат поиска по проекту (scripts, data, report, notes):
  - action=profile:          payload NOT FOUND in project files → SKIPPED
  - action=posts:            payload NOT FOUND in project files → SKIPPED
  - action=highlights:       action name confirmed by user context; full payload
                             (url/username parameter format) NOT FOUND in project files → SKIPPED
  - action=highlight_stories: payload NOT FOUND in project files → SKIPPED

  Для добавления action: заполнить CONFIRMED_PAYLOADS ниже точным payload
  после его подтверждения. Actor будет вызван только если payload в словаре.

НЕ запускает OpenAI.
НЕ скачивает media.
НЕ использует угаданные payloads.

Запуск:
    python scripts/stage5s0_check_singhera_capabilities.py --dry-run
    python scripts/stage5s0_check_singhera_capabilities.py
"""

import json
import sys
from pathlib import Path

import os
os.environ["PYTHONUTF8"] = "1"

from dotenv import load_dotenv

BASE     = Path(__file__).parent.parent
RAW_DIR  = BASE / "data/raw"
NORM_DIR = BASE / "data/normalized"
SUMMARY_PATH = NORM_DIR / "stage5s0_singhera_capability_summary.json"

ACTOR_ID    = "singhera07/instagram-scraper"
ACCOUNT     = "vlada_kliuiko"
PROFILE_URL = "https://www.instagram.com/vlada_kliuiko/"

DRY_RUN = "--dry-run" in sys.argv

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ---------------------------------------------------------------------------
# CONFIRMED PAYLOADS
# Fill in each action's payload ONLY after it is confirmed from project files,
# logs, or user-provided schema. Leave None to keep the action SKIPPED.
# ---------------------------------------------------------------------------

CONFIRMED_PAYLOADS = {
    # action=profile
    # Status: NOT confirmed — payload not found in project files
    # To enable: fill with exact confirmed payload dict
    "profile": None,

    # action=posts (or equivalent)
    # Status: NOT confirmed — payload not found in project files
    "posts_pinned": None,

    # action=highlights
    # Status: action name confirmed by user (returned 32 highlights),
    # but url/username parameter format NOT found in project files.
    # To enable: fill with exact confirmed payload dict, e.g.:
    #   {"action": "highlights", "url": PROFILE_URL}
    #   or {"action": "highlights", "username": ACCOUNT}
    "highlights_index": None,

    # action=highlight_stories (or equivalent)
    # Status: NOT confirmed — payload not found in project files
    "highlight_stories": None,
}

# ---------------------------------------------------------------------------
# Capability block definitions
# ---------------------------------------------------------------------------

CAPABILITY_BLOCKS = [
    {
        "key":           "profile",
        "label":         "Profile",
        "purpose":       "Replace apify/instagram-scraper details for profile fields",
        "current_actor": "apify/instagram-scraper (resultsType=details)",
        "raw_path":      "data/raw/stage5s0_singhera_profile_raw.json",
        "probe_fields": [
            "biography", "bio", "fullName", "username",
            "externalUrl", "followersCount", "followingCount",
            "followsCount", "postsCount",
        ],
        "required_for_replace": [
            "biography", "username", "fullName", "externalUrl",
            "followersCount", "postsCount",
        ],
        "skip_reason": "input schema for action=profile not found in project files",
    },
    {
        "key":           "posts_pinned",
        "label":         "Posts + Pinned",
        "purpose":       "Replace apify/instagram-scraper posts for posts and isPinned detection",
        "current_actor": "apify/instagram-scraper (resultsType=posts)",
        "raw_path":      "data/raw/stage5s0_singhera_posts_raw.json",
        "probe_fields": [
            "id", "shortCode", "url", "caption", "timestamp", "type",
            "displayUrl", "images", "videoUrl", "videoViewCount",
            "videoPlayCount", "likesCount", "commentsCount", "isPinned",
        ],
        "required_for_replace": [
            "caption", "url", "timestamp", "displayUrl",
            "shortCode", "isPinned",
        ],
        "skip_reason": "input schema for action=posts not found in project files",
    },
    {
        "key":           "highlights_index",
        "label":         "Highlights Index",
        "purpose":       "Primary actor for highlights list (id, title, cover)",
        "current_actor": "scrapio/instagram-highlights-scraper (blocked — paid rental)",
        "raw_path":      "data/raw/stage5s0_singhera_highlights_raw.json",
        "probe_fields": [
            "id", "title", "croppedThumbnail", "cover",
            "owner",
        ],
        "required_for_replace": [
            "id", "title", "croppedThumbnail",
        ],
        "skip_reason": (
            "action=highlights confirmed by user (returned 32 highlights) but full "
            "input payload (url/username parameter format) not found in project files"
        ),
    },
    {
        "key":           "highlight_stories",
        "label":         "Highlight Stories",
        "purpose":       "Replace igview-owner/instagram-highlights-stories-viewer",
        "current_actor": "igview-owner/instagram-highlights-stories-viewer",
        "raw_path":      "data/raw/stage5s0_singhera_highlight_stories_raw.json",
        "probe_fields": [
            "storyId", "storyNumber", "storyType",
            "imageUrl", "videoUrl", "takenAt", "duration",
        ],
        "required_for_replace": [
            "storyId", "imageUrl",
        ],
        "skip_reason": "input schema for highlight_stories action not found in project files",
    },
]

# Highlight IDs for highlight_stories check (when payload is confirmed)
HIGHLIGHT_IDS_FOR_STORIES = [
    "17874797856565339",  # control — returned 57 stories via igview-owner
    "18110898391654002",  # candidate — returned 17 stories via igview-owner
]

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
# Field probe
# ---------------------------------------------------------------------------

def probe_items(items: list, probe_fields: list) -> dict:
    if not items:
        return {
            "top_level_fields": [],
            "fields_found":     [],
            "fields_missing":   list(probe_fields),
            "sample_values":    {},
        }

    top_level = sorted(set(k for item in items for k in item.keys()))
    found_set = set()
    samples   = {}

    for item in items:
        for f in probe_fields:
            if f in item and item[f] is not None and f not in found_set:
                found_set.add(f)
                samples[f] = safe_sample(item[f])
        # also sample nested owner fields if owner is a dict
        if "owner" in item and isinstance(item["owner"], dict) and "owner" not in found_set:
            found_set.add("owner")
            owner = item["owner"]
            samples["owner.id"]       = safe_sample(owner.get("id"))
            samples["owner.username"] = safe_sample(owner.get("username"))

    return {
        "top_level_fields": top_level,
        "fields_found":     [f for f in probe_fields if f in found_set],
        "fields_missing":   [f for f in probe_fields if f not in found_set],
        "sample_values":    samples,
    }

# ---------------------------------------------------------------------------
# Replace decision logic
# ---------------------------------------------------------------------------

def make_replace_decision(block: dict, fields_found: list, items_count: int, status: str) -> str:
    if status in ("SKIPPED", "DRY_RUN"):
        return "skipped"
    if status == "FAIL":
        return "keep current actor"
    if items_count == 0:
        return "not enough evidence"

    required = block["required_for_replace"]
    found_set = set(fields_found)
    missing_required = [f for f in required if f not in found_set]

    if not missing_required:
        return "replace current actor"
    # partial coverage
    if len(missing_required) < len(required):
        return "use as fallback"
    return "keep current actor"

# ---------------------------------------------------------------------------
# Build blank action result
# ---------------------------------------------------------------------------

def blank_result(block: dict, status: str, errors: list = None, notes: str = "") -> dict:
    return {
        "status":              status,
        "input_schema_source": "not_found_in_project_files",
        "items_count":         0,
        "top_level_fields":    [],
        "fields_found":        [],
        "fields_missing":      list(block["probe_fields"]),
        "sample_values":       {},
        "raw_path":            block["raw_path"] if status not in ("SKIPPED", "DRY_RUN") else None,
        "errors":              errors or [],
        "replace_decision":    "skipped" if status in ("SKIPPED", "DRY_RUN") else "not enough evidence",
        "notes":               notes,
    }

# ---------------------------------------------------------------------------
# Build recommended_architecture and can_replace
# ---------------------------------------------------------------------------

def build_can_replace(actions_tested: dict) -> dict:
    def is_replace(key):
        return actions_tested.get(key, {}).get("replace_decision") == "replace current actor"

    return {
        "profile_actor":           is_replace("profile"),
        "posts_actor":             is_replace("posts_pinned"),
        "highlights_index_actor":  is_replace("highlights_index"),
        "highlight_stories_actor": is_replace("highlight_stories"),
    }


def build_architecture(can_replace: dict, actions_tested: dict) -> str:
    parts = []

    if can_replace["highlights_index_actor"] and not can_replace["highlight_stories_actor"]:
        parts.append(
            "singhera07/instagram-scraper as primary highlights index actor "
            "+ igview-owner/instagram-highlights-stories-viewer for highlight stories"
        )
    elif can_replace["highlights_index_actor"] and can_replace["highlight_stories_actor"]:
        parts.append(
            "singhera07/instagram-scraper for both highlights index and highlight stories"
        )
    else:
        hi_decision = actions_tested.get("highlights_index", {}).get("replace_decision", "skipped")
        hs_decision = actions_tested.get("highlight_stories", {}).get("replace_decision", "skipped")
        parts.append(
            f"highlights_index: {hi_decision}; "
            f"highlight_stories: {hs_decision}"
        )

    if can_replace["profile_actor"]:
        parts.append("singhera07 can replace apify/instagram-scraper for profile")
    else:
        parts.append("apify/instagram-scraper (details) remains primary for profile")

    if can_replace["posts_actor"]:
        parts.append("singhera07 can replace apify/instagram-scraper for posts+pinned")
    else:
        parts.append("apify/instagram-scraper (posts) remains primary for posts+pinned")

    return "; ".join(parts)


def build_recommendation(actions_tested: dict, can_replace: dict, all_skipped: bool) -> str:
    if all_skipped:
        return (
            "All capability blocks are SKIPPED — confirmed input payloads not found in project files. "
            "To enable checks: (1) confirm exact payload for each singhera07 action; "
            "(2) fill CONFIRMED_PAYLOADS dict in the script; "
            "(3) re-run. "
            "Known: action=highlights returned 32 highlights (user confirmed) — "
            "provide full payload format to enable highlights_index check."
        )

    skipped = [k for k, v in actions_tested.items() if v.get("status") == "SKIPPED"]
    ok      = [k for k, v in actions_tested.items() if v.get("status") == "OK"]
    failed  = [k for k, v in actions_tested.items() if v.get("status") == "FAIL"]

    parts = []
    if ok:
        parts.append(f"Working actions: {ok}.")
    if failed:
        parts.append(f"Failed actions: {failed} — check actor/token/network.")
    if skipped:
        parts.append(
            f"Skipped (input schema not confirmed): {skipped}. "
            "Fill CONFIRMED_PAYLOADS in the script to enable."
        )
    return " ".join(parts)

# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(token_errors: list):
    print("=== Stage 5S-0: DRY RUN ===")
    print(f"Actor:   {ACTOR_ID}")
    print(f"Account: {ACCOUNT}")
    print()

    token = os.environ.get("APIFY_TOKEN", "")
    if token_errors:
        print("APIFY_TOKEN: INVALID")
        for e in token_errors:
            print(f"  [ERROR] {e}")
    else:
        print("APIFY_TOKEN: found, format OK (not printed)")
    print()

    confirmed_count = sum(1 for v in CONFIRMED_PAYLOADS.values() if v is not None)
    print(f"planned_apify_calls: {confirmed_count}  (only actions with confirmed payloads)")
    print()

    for block in CAPABILITY_BLOCKS:
        key = block["key"]
        payload = CONFIRMED_PAYLOADS.get(key)
        print(f"--- {block['label']} ({key}) ---")
        print(f"  purpose:       {block['purpose']}")
        print(f"  current_actor: {block['current_actor']}")
        if payload is not None:
            print(f"  schema_status: CONFIRMED")
            print(f"  payload:       {json.dumps(payload)}")
        else:
            print(f"  schema_status: SKIPPED")
            print(f"  reason:        {block['skip_reason']}")
        print()

    results = []
    for block in CAPABILITY_BLOCKS:
        payload = CONFIRMED_PAYLOADS.get(block["key"])
        status = "DRY_RUN" if payload is not None else "SKIPPED"
        results.append({
            "key":    block["key"],
            "status": status,
            "reason": "" if payload is not None else block["skip_reason"],
        })

    print("Summary:")
    for r in results:
        tag = "WOULD RUN" if r["status"] == "DRY_RUN" else "SKIPPED"
        print(f"  [{tag:9}] {r['key']}")
        if r["reason"]:
            print(f"              reason: {r['reason']}")

    print()
    print("DRY RUN complete — Apify was NOT called.")

    # Save dry-run summary
    actions_tested = {}
    for block in CAPABILITY_BLOCKS:
        payload = CONFIRMED_PAYLOADS.get(block["key"])
        status = "DRY_RUN" if payload is not None else "SKIPPED"
        actions_tested[block["key"]] = blank_result(block, status, notes=block["skip_reason"] if payload is None else "")

    summary = {
        "stage":                  "stage5s0_singhera_capability_check",
        "actor":                  ACTOR_ID,
        "account":                ACCOUNT,
        "dry_run":                True,
        "token_valid":            not token_errors,
        "planned_apify_calls":    confirmed_count,
        "actual_apify_calls":     0,
        "actions_tested":         actions_tested,
        "can_replace":            {
            "profile_actor":           False,
            "posts_actor":             False,
            "highlights_index_actor":  False,
            "highlight_stories_actor": False,
        },
        "recommended_architecture": "dry_run — no data",
        "manual_needed":           [],
        "recommendation":          "DRY RUN only — run without --dry-run to get real results.",
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDry-run summary saved: {SUMMARY_PATH.relative_to(BASE)}")
    sys.exit(0)

# ---------------------------------------------------------------------------
# Real run: one capability block
# ---------------------------------------------------------------------------

def run_block(block: dict, client) -> dict:
    key     = block["key"]
    payload = CONFIRMED_PAYLOADS.get(key)

    print(f"\n  [{block['label']}]")

    if payload is None:
        print(f"    SKIPPED — {block['skip_reason']}")
        return blank_result(block, "SKIPPED", notes=block["skip_reason"])

    result = blank_result(block, "FAIL")
    result["input_schema_source"] = "confirmed"
    print(f"    payload: {json.dumps(payload)}")

    try:
        run  = client.actor(ACTOR_ID).call(run_input=payload)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        result["items_count"] = len(items)

        if not items:
            result["status"] = "FAIL"
            result["errors"].append("Actor returned 0 items")
            print(f"    FAIL — 0 items")
        else:
            probe = probe_items(items, block["probe_fields"])
            result["status"]           = "OK"
            result["top_level_fields"] = probe["top_level_fields"]
            result["fields_found"]     = probe["fields_found"]
            result["fields_missing"]   = probe["fields_missing"]
            result["sample_values"]    = probe["sample_values"]
            result["raw_path"]         = block["raw_path"]
            print(f"    OK — {len(items)} item(s)")
            print(f"    fields_found:   {probe['fields_found']}")
            print(f"    fields_missing: {probe['fields_missing']}")

            # Save raw
            raw_path = BASE / block["raw_path"]
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            safe_items = [safe_item(i) for i in items]
            raw_path.write_text(json.dumps(safe_items, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    raw saved: {raw_path.relative_to(BASE)}")

    except Exception as exc:
        result["status"] = "FAIL"
        result["errors"].append(str(exc))
        print(f"    FAIL: {exc}")

    result["replace_decision"] = make_replace_decision(
        block, result["fields_found"], result["items_count"], result["status"]
    )
    print(f"    replace_decision: {result['replace_decision']}")
    return result

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("APIFY_TOKEN", "")
    token_errors = validate_token(token)

    if DRY_RUN:
        run_dry_run(token_errors)
        return

    print("=== Stage 5S-0: Singhera Capability Check ===")
    print(f"Actor:   {ACTOR_ID}")
    print(f"Account: {ACCOUNT}")

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

    confirmed_count = sum(1 for v in CONFIRMED_PAYLOADS.values() if v is not None)
    print(f"\nplanned_apify_calls: {confirmed_count}")

    actions_tested = {}
    actual_calls   = 0

    for block in CAPABILITY_BLOCKS:
        result = run_block(block, client)
        actions_tested[block["key"]] = result
        if result["status"] not in ("SKIPPED", "FAIL"):
            actual_calls += 1

    all_skipped = all(
        v.get("status") == "SKIPPED" for v in actions_tested.values()
    )

    can_replace = build_can_replace(actions_tested)
    arch        = build_architecture(can_replace, actions_tested)
    rec         = build_recommendation(actions_tested, can_replace, all_skipped)

    summary = {
        "stage":                   "stage5s0_singhera_capability_check",
        "actor":                   ACTOR_ID,
        "account":                 ACCOUNT,
        "dry_run":                 False,
        "token_valid":             True,
        "planned_apify_calls":     confirmed_count,
        "actual_apify_calls":      actual_calls,
        "actions_tested":          actions_tested,
        "can_replace":             can_replace,
        "recommended_architecture": arch,
        "manual_needed":           [],
        "recommendation":          rec,
    }

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*52}")
    print("SUMMARY")
    for key, res in actions_tested.items():
        print(f"  [{key:20}] status={res['status']:25} replace_decision={res['replace_decision']}")
    print(f"\nRecommended architecture: {arch}")
    print(f"\nRecommendation: {rec}")
    print(f"\nSummary saved: {SUMMARY_PATH.relative_to(BASE)}")


if __name__ == "__main__":
    main()
