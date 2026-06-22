"""
Stage 5A-1: сборщик профиля и индекса закрепов.

2 вызова Apify:
  1. apify/instagram-scraper  resultsType=details  → поля профиля
  2. apify/instagram-scraper  resultsType=posts     → определение isPinned

Без OpenAI. Без загрузки медиа.

Использование:
  python -m pipeline.stages.collect_profile --account vlada_kliuiko
  python -m pipeline.stages.collect_profile --account vlada_kliuiko --dry-run
"""

import argparse
import json
import logging
import re
from datetime import datetime, timezone

from pipeline.core.apify_client import run_actor
from pipeline.core.config import get_account
from pipeline.core.paths import raw, normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTOR_ID = "apify/instagram-scraper"

# ---------------------------------------------------------------------------
# Field wrapper helpers
# ---------------------------------------------------------------------------

def _field_ok(value, source_ref, notes=""):
    return {"value": value, "data_status": "ok", "source_ref": source_ref,
            "confidence": "high", "notes": notes}


def _field_partial(value, source_ref, notes=""):
    return {"value": value, "data_status": "partial", "source_ref": source_ref,
            "confidence": "medium", "notes": notes}


def _field_missing(notes=""):
    return {"value": None, "data_status": "missing", "source_ref": "none",
            "confidence": None, "notes": notes}


def _field_manual_needed(notes=""):
    return {"value": None, "data_status": "manual_needed",
            "source_ref": "manual_input", "confidence": None, "notes": notes}


# ---------------------------------------------------------------------------
# External URL type detector
# ---------------------------------------------------------------------------

def _detect_url_type(url: str) -> str:
    if not url:
        return "none"
    u = url.lower()
    if "t.me" in u or "telegram" in u:
        return "telegram"
    if "wa.me" in u or "whatsapp" in u:
        return "whatsapp"
    if "taplink" in u:
        return "taplink"
    if "linktr.ee" in u:
        return "linktree"
    if u.startswith("http"):
        return "site"
    return "none"


# ---------------------------------------------------------------------------
# Safe truncate for raw saves
# ---------------------------------------------------------------------------

def _safe_item(item: dict) -> dict:
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
# Build profile_summary.json
# ---------------------------------------------------------------------------

def _build_profile_summary(details_item: dict, username: str, profile_url: str,
                           run_ts: str, run_meta: dict) -> dict:
    src = "details_actor.apify/instagram-scraper"

    def get(key, *aliases):
        for a in (key,) + aliases:
            if a in details_item and details_item[a] is not None:
                return details_item[a]
        return None

    username_val  = get("username")
    full_name_val = get("fullName")
    bio_val       = get("biography", "bio")
    ext_url_val   = get("externalUrl", "external_url")
    followers_val = get("followersCount")
    following_val = get("followsCount", "followingCount")
    posts_val     = get("postsCount")

    url_type = _detect_url_type(ext_url_val or "")

    def wrap_int(val, label):
        if val is not None:
            return _field_ok(val, src)
        return _field_manual_needed(f"{label} not returned by actor")

    def wrap_str(val, label):
        if val:
            return _field_ok(val, src)
        return _field_manual_needed(f"{label} not returned by actor")

    ext_url_wrapped = (
        _field_ok(ext_url_val, src) if ext_url_val
        else _field_manual_needed("externalUrl not in actor output")
    )

    return {
        "account":             username,
        "stage":               "stage5a1",
        "run_timestamp":       run_ts,
        "planned_apify_calls": run_meta["planned"],
        "actual_apify_calls":  run_meta["actual"],
        "apify_run_ids":       run_meta["run_ids"],
        "profile_url":         _field_ok(profile_url, "config"),
        "username":            wrap_str(username_val, "username"),
        "full_name":           wrap_str(full_name_val, "fullName"),
        "bio_text":            wrap_str(bio_val, "biography"),
        "external_url":        ext_url_wrapped,
        "external_url_type":   (
            _field_ok(url_type, "rule_based") if url_type != "none"
            else _field_missing("external_url empty or not matched")
        ),
        "followers_count":     wrap_int(followers_val, "followersCount"),
        "following_count":     wrap_int(following_val, "followsCount/followingCount"),
        "posts_count":         wrap_int(posts_val, "postsCount"),
        "raw_source":          f"data/{username}/raw/stage5a1_profile_details_raw.json",
    }


# ---------------------------------------------------------------------------
# Build bio_analysis.json — rule-based, без OpenAI
# ---------------------------------------------------------------------------

_CTA_KEYWORDS = [
    "записаться", "получить", "скачать", "курс", "разбор", "консультация",
    "регистрация", "подписаться", "переходи", "жми", "нажми", "запись",
]

_SOCIAL_PROOF_KEYWORDS = [
    "кейс", "клиенты", "ученики", "основатель", "агентство", "результаты",
    "выпускник", "студент", "проект", "бизнес",
]


def _bio_rule_based(bio_text: str) -> dict:
    lines = [l.strip() for l in bio_text.splitlines() if l.strip()]

    # --- cta_text ---
    cta_text_val = None
    for i, line in enumerate(lines):
        if "↓" in line or "⬇" in line:
            cta_text_val = lines[i + 1] if i + 1 < len(lines) else line
            break
    if not cta_text_val:
        for line in lines:
            low = line.lower()
            if any(kw in low for kw in _CTA_KEYWORDS):
                cta_text_val = line
                break

    # --- social_proof ---
    sp_lines = []
    for line in lines:
        has_digit = bool(re.search(r"\d", line))
        low = line.lower()
        has_kw = any(kw in low for kw in _SOCIAL_PROOF_KEYWORDS)
        if has_digit or has_kw:
            sp_lines.append(line)

    # --- niche / target / result ---
    niche_line = lines[0] if lines else None
    target_line = None
    result_line = None
    for line in lines:
        low = line.lower()
        if any(w in low for w in ["помогаю", "работаю с", "для "]):
            target_line = line
            break
    for line in lines:
        low = line.lower()
        if any(w in low for w in ["результат", "доход", "прибыль", "рост", "выход", "масштаб"]):
            result_line = line
            break

    src = "profile_summary.bio_text"

    return {
        "niche": (
            _field_partial(niche_line, src, "First bio line — may be role/niche, rule-based")
            if niche_line else _field_manual_needed("Cannot extract niche from bio automatically")
        ),
        "target_audience": (
            _field_partial(target_line, src, "Line matching помогаю/работаю с/для — rule-based")
            if target_line else _field_manual_needed("Cannot extract target_audience from bio automatically")
        ),
        "result_promise": (
            _field_partial(result_line, src, "Line matching result keywords — rule-based")
            if result_line else _field_manual_needed("Cannot extract result_promise from bio automatically")
        ),
        "positioning": _field_manual_needed(
            "Positioning requires human interpretation — use OpenAI in Stage 5D or fill manually"
        ),
        "social_proof": (
            _field_partial(sp_lines if sp_lines else None, src,
                           "Lines with digits or social_proof keywords — rule-based")
            if sp_lines else _field_manual_needed("No social proof lines detected in bio")
        ),
        "trust_arguments": _field_manual_needed(
            "Trust arguments require human or OpenAI interpretation"
        ),
        "cta_text": (
            _field_partial(cta_text_val, src, "Arrow or CTA-keyword line — rule-based")
            if cta_text_val else _field_manual_needed("No CTA line detected in bio")
        ),
        "cta_destination": None,  # заполняется caller-ом
    }


def _build_bio_analysis(profile_summary: dict, username: str, run_ts: str) -> dict:
    bio_field = profile_summary.get("bio_text", {})
    bio_text = bio_field.get("value") or ""

    ext_url_field = profile_summary.get("external_url", {})
    ext_url = ext_url_field.get("value") or ""

    if bio_text:
        analysis = _bio_rule_based(bio_text)
    else:
        none_field = _field_manual_needed("bio_text missing — cannot analyse")
        analysis = {k: none_field for k in [
            "niche", "target_audience", "result_promise", "positioning",
            "social_proof", "trust_arguments", "cta_text",
        ]}
        analysis["cta_destination"] = None

    analysis["cta_destination"] = (
        _field_ok(ext_url, "profile_summary.external_url") if ext_url
        else _field_manual_needed("No external_url in profile — fill manually")
    )

    return {
        "account":         username,
        "stage":           "stage5a1",
        "run_timestamp":   run_ts,
        "analysis_method": "rule_based",
        "source_ref":      "profile_summary.bio_text",
        **analysis,
    }


# ---------------------------------------------------------------------------
# Build pinned_posts_index.json
# ---------------------------------------------------------------------------

def _build_pinned_posts_index(posts_items: list, username: str, run_ts: str) -> dict:
    total_checked = len(posts_items)
    has_field = any("isPinned" in item for item in posts_items)
    src_ref = "posts.resultsType=posts.isPinned"

    if not has_field:
        return {
            "account":          username,
            "stage":            "stage5a1",
            "run_timestamp":    run_ts,
            "detection_method": "not_detected",
            "source_ref":       src_ref,
            "posts_checked":    total_checked,
            "pinned_count":     0,
            "manual_needed":    True,
            "notes":            "isPinned field absent in all posts — fill pinned_posts_manual.json manually",
            "pinned_posts":     [],
            "raw_source":       f"data/{username}/raw/stage5a1_posts_for_pinned_raw.json",
        }

    pinned_items = [item for item in posts_items if item.get("isPinned") is True]
    pinned_count = len(pinned_items)

    def wrap_post_field(val, key_name):
        if val is not None and val != "":
            return _field_ok(val, f"posts_actor.{key_name}")
        return _field_missing(f"{key_name} not in actor output")

    pinned_list = []
    for pos, item in enumerate(pinned_items, start=1):
        caption_raw = item.get("caption") or ""
        caption_preview = caption_raw[:300] if caption_raw else None
        pinned_list.append({
            "position":        pos,
            "url":             wrap_post_field(item.get("url"), "url"),
            "content_id":      wrap_post_field(item.get("id"), "id"),
            "shortcode":       wrap_post_field(item.get("shortCode"), "shortCode"),
            "caption_preview": wrap_post_field(caption_preview, "caption"),
            "is_pinned":       _field_ok(True, "posts_actor.isPinned"),
            "timestamp":       wrap_post_field(item.get("timestamp"), "timestamp"),
            "type":            wrap_post_field(item.get("type"), "type"),
        })

    manual_needed = pinned_count == 0
    notes = (
        "actor supports isPinned but no pinned posts found in first 30 posts"
        if pinned_count == 0 else ""
    )

    return {
        "account":          username,
        "stage":            "stage5a1",
        "run_timestamp":    run_ts,
        "detection_method": "actor_field",
        "source_ref":       src_ref,
        "posts_checked":    total_checked,
        "pinned_count":     pinned_count,
        "manual_needed":    manual_needed,
        "notes":            notes,
        "pinned_posts":     pinned_list,
        "raw_source":       f"data/{username}/raw/stage5a1_posts_for_pinned_raw.json",
    }


# ---------------------------------------------------------------------------
# Build stage5a_summary.json
# ---------------------------------------------------------------------------

def _count_statuses(d: dict) -> dict:
    counts = {"ok": 0, "partial": 0, "missing": 0, "manual_needed": 0}
    for v in d.values():
        if isinstance(v, dict) and "data_status" in v:
            s = v["data_status"]
            if s in counts:
                counts[s] += 1
    return counts


def _build_stage5a_summary(profile_summary: dict, bio_analysis: dict,
                            pinned_index: dict, username: str,
                            run_ts: str, run_meta: dict) -> dict:
    ps_counts = _count_statuses(profile_summary)
    ba_counts = _count_statuses(bio_analysis)

    if ps_counts["missing"] == 0 and ps_counts["manual_needed"] == 0:
        profile_status = "ok"
    elif ps_counts["ok"] > 0 or ps_counts["partial"] > 0:
        profile_status = "partial"
    else:
        profile_status = "missing"

    if ba_counts["missing"] == 0 and ba_counts["manual_needed"] == 0:
        bio_status = "ok"
    elif ba_counts["ok"] > 0 or ba_counts["partial"] > 0:
        bio_status = "partial"
    else:
        bio_status = "missing"

    pinned_count = pinned_index.get("pinned_count", 0)
    manual_needed_pinned = pinned_index.get("manual_needed", True)
    if pinned_count >= 3:
        pinned_status = "ok"
    elif pinned_count in (1, 2):
        pinned_status = "partial"
    elif manual_needed_pinned:
        pinned_status = "manual_needed"
    else:
        pinned_status = "missing"

    total_ok      = ps_counts["ok"] + ba_counts["ok"]
    total_partial = ps_counts["partial"] + ba_counts["partial"]
    total_missing = ps_counts["missing"] + ba_counts["missing"]
    total_manual  = ps_counts["manual_needed"] + ba_counts["manual_needed"]

    has_facts = (
        profile_summary.get("username", {}).get("data_status") == "ok"
        and profile_summary.get("full_name", {}).get("data_status") == "ok"
        and profile_summary.get("bio_text", {}).get("data_status") == "ok"
        and profile_summary.get("external_url", {}).get("data_status") == "ok"
    )
    if has_facts and bio_status == "ok":
        can_fill_profile = "ok"
    elif has_facts:
        can_fill_profile = "partial"
    else:
        can_fill_profile = "missing"

    blockers = []
    if profile_status == "missing":
        blockers.append("profile fields missing — check actor output or fill profile_manual.json")
    if pinned_status == "manual_needed":
        blockers.append("pinned posts not detected — fill pinned_posts_manual.json")
    if pinned_status == "missing":
        blockers.append("pinned posts missing — isPinned not in actor output")

    return {
        "account":              username,
        "stage":                "stage5a1",
        "run_timestamp":        run_ts,
        "planned_apify_calls":  run_meta["planned"],
        "actual_apify_calls":   run_meta["actual"],
        "profile_status":       profile_status,
        "bio_status":           bio_status,
        "pinned_posts_status":  pinned_status,
        "fields_ok":            total_ok,
        "fields_partial":       total_partial,
        "fields_missing":       total_missing,
        "fields_manual_needed": total_manual,
        "profile_sheet_coverage": {
            "can_fill_facts":          has_facts,
            "can_fill_interpretation": bio_status if bio_status in ("ok", "partial") else "missing",
            "coverage_status":         can_fill_profile,
            "notes":                   "rule-based bio fields are partial — requires human review",
        },
        "coverage_by_sheet": {
            "Описание профиля":   can_fill_profile,
            "Закрепленные посты": pinned_status,
            "Воронка":            "missing",
            "Анализ хайлайтс":    "not_started",
            "Лендинг":            "not_started",
            "Бот лид-магнит":     "not_started",
        },
        "can_fill_profile_sheet":      can_fill_profile,
        "can_fill_pinned_posts_sheet": pinned_status,
        "can_run_stage5b":             False,
        "can_run_stage5d":             False,
        "blockers":                    blockers,
        "next_recommendation": (
            "Profile and facts are available. "
            "Bio analysis is rule-based/partial — review bio_analysis.json and fill manual fields. "
            "Before Stage 5B: provide highlight IDs in data/input/highlights_manual.json."
        ),
    }


# ---------------------------------------------------------------------------
# Main collect function
# ---------------------------------------------------------------------------

def collect(username: str, dry_run: bool = False) -> dict:
    """
    Собирает профиль и индекс закрепов аккаунта.
    Возвращает dict с profile_summary, bio_analysis, pinned_index, stage5a_summary.
    """
    account = get_account(username)
    profile_url = account["url"]
    logger.info(f"[5A-1] collect_profile | @{username} | dry_run={dry_run}")

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {
            "dry_run":    True,
            "account":    username,
            "profile_url": profile_url,
            "planned_apify_calls": 2,
            "actual_apify_calls":  0,
        }

    run_ts = datetime.now(timezone.utc).isoformat()
    run_ids = []
    actual_calls = 0

    # Обеспечиваем директории
    raw(username, "_placeholder").parent.mkdir(parents=True, exist_ok=True)
    normalized(username, "_placeholder").parent.mkdir(parents=True, exist_ok=True)

    # --- Call 1: details ---
    logger.info("[1/2] Запрос details mode ...")
    details_items = []
    try:
        details_items = run_actor(
            actor_id=ACTOR_ID,
            input_data={
                "directUrls":  [profile_url],
                "resultsType": "details",
                "resultsLimit": 1,
                "proxy": {"useApifyProxy": True, "apifyProxyGroups": []},
            },
        )
        actual_calls += 1
        logger.info(f"  OK — {len(details_items)} item(s)")
        raw1_path = raw(username, "stage5a1_profile_details_raw.json")
        raw1_path.write_text(
            json.dumps([_safe_item(i) for i in details_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"  raw saved: {raw1_path}")
    except Exception as exc:
        logger.error(f"  FAIL details: {exc}")

    details_item = details_items[0] if details_items else {}

    # --- Call 2: posts for pinned detection ---
    logger.info("[2/2] Запрос posts mode (pinned detection) ...")
    posts_items = []
    try:
        posts_items = run_actor(
            actor_id=ACTOR_ID,
            input_data={
                "directUrls":  [profile_url],
                "resultsType": "posts",
                "resultsLimit": 30,
                "proxy": {"useApifyProxy": True, "apifyProxyGroups": []},
            },
        )
        actual_calls += 1
        logger.info(f"  OK — {len(posts_items)} item(s)")
        raw2_path = raw(username, "stage5a1_posts_for_pinned_raw.json")
        raw2_path.write_text(
            json.dumps([_safe_item(i) for i in posts_items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"  raw saved: {raw2_path}")
    except Exception as exc:
        logger.error(f"  FAIL posts: {exc}")

    run_meta = {"planned": 2, "actual": actual_calls, "run_ids": run_ids}

    # --- Build normalized outputs ---
    profile_summary  = _build_profile_summary(
        details_item, username, profile_url, run_ts, run_meta
    )
    bio_analysis     = _build_bio_analysis(profile_summary, username, run_ts)
    pinned_index     = _build_pinned_posts_index(posts_items, username, run_ts)
    stage5a_summary  = _build_stage5a_summary(
        profile_summary, bio_analysis, pinned_index, username, run_ts, run_meta
    )

    normalized(username, "profile_summary.json").write_text(
        json.dumps(profile_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    normalized(username, "bio_analysis.json").write_text(
        json.dumps(bio_analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    normalized(username, "pinned_posts_index.json").write_text(
        json.dumps(pinned_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    normalized(username, "stage5a_summary.json").write_text(
        json.dumps(stage5a_summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n=== Stage 5A-1: Profile | @{username} ===")
    print(f"Профиль:       {stage5a_summary['profile_status']}")
    print(f"Bio-анализ:    {stage5a_summary['bio_status']}")
    print(f"Закрепы:       {stage5a_summary['pinned_posts_status']} ({pinned_index['pinned_count']} шт.)")
    print(f"Файлы:  normalized/profile_summary.json")
    print(f"        normalized/bio_analysis.json")
    print(f"        normalized/pinned_posts_index.json")
    print(f"        normalized/stage5a_summary.json")

    return {
        "profile_summary": profile_summary,
        "bio_analysis":    bio_analysis,
        "pinned_index":    pinned_index,
        "stage5a_summary": stage5a_summary,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-1: collect profile + pinned index")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать Apify")
    args = parser.parse_args()
    collect(args.account, args.dry_run)
