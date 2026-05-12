#!/usr/bin/env python3
"""
Stage 5C: OpenAI Vision analysis of highlight stories.

Reads data/normalized/stage5b_auto_stories_index.json (Stage 5B-auto).
Classifies each story image using OpenAI Vision (gpt-4o-mini by default).
No Apify calls. No media downloads. Videos use thumbnailUrl.

Cache keyed by story_id + model + detail + prompt_version.
Budget guard stops the run (not errors) when --budget-max-usd is reached.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE     = Path(__file__).parent.parent
NORM_DIR = BASE / "data/normalized"
CACHE_DIR = BASE / "data/raw/stage5c_cache"

STORIES_INDEX_PATH  = NORM_DIR / "stage5b_auto_stories_index.json"
HIGHLIGHTS_IDX_PATH = NORM_DIR / "highlights_index.json"
ANALYSIS_PATH       = NORM_DIR / "stage5c_stories_analysis.json"
HL_SUMMARY_PATH     = NORM_DIR / "stage5c_highlights_summary.json"

PROMPT_VERSION = "v1"
DEFAULT_MODEL  = "gpt-4o-mini"
DEFAULT_DETAIL = "low"

# Conservative per-call cost estimates (input image + prompt + output)
COST_PER_CALL: dict[tuple[str, str], float] = {
    ("gpt-4o-mini", "low"):  0.0015,
    ("gpt-4o-mini", "high"): 0.006,
    ("gpt-4o",      "low"):  0.018,
    ("gpt-4o",      "high"): 0.055,
}

CONTENT_TYPES = [
    "student_review",
    "case_result",
    "sales_offer",
    "webinar_event",
    "lead_magnet",
    "objection_handling",
    "authority_proof",
    "process_demo",
    "educational",
    "personal_positioning",
    "community_social_proof",
    "lifestyle",
    "cta_only",
    "other",
]

COMMERCIAL_ROLES = [
    "proof",
    "offer",
    "trust",
    "objection",
    "education",
    "activation",
    "navigation",
    "identity",
    "none",
]

SYSTEM_PROMPT = """\
Ты аналитик конкурентного Instagram-контента.
Тебе показывают одну story из архива highlights конкурента.
Верни ТОЛЬКО JSON-объект в указанной схеме. Никаких пояснений, только JSON.
Текст внутри JSON пиши на русском языке."""


def _build_user_prompt(highlight_id: str, canonical_title: str, media_type: str) -> str:
    types_str = " | ".join(CONTENT_TYPES)
    roles_str = " | ".join(COMMERCIAL_ROLES)
    return f"""\
Story из highlight "{canonical_title}" (id: {highlight_id}).
Тип медиа: {media_type}.

Верни JSON с полями:
{{
  "content_type": "{types_str}",
  "commercial_role": "{roles_str}",
  "has_visible_text": true/false,
  "extracted_text": "<текст со story или null>",
  "has_cta": true/false,
  "cta_text": "<текст призыва к действию или null>",
  "main_subject": "<кратко: кто или что изображено>",
  "visual_style": "<кратко: стиль, оформление, цвета>",
  "sentiment": "positive | neutral | negative",
  "tags": ["<до 5 тегов>"],
  "confidence": "high | medium | low",
  "notes": "<необязательно: нестандартное наблюдение или null>"
}}"""


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_stories_index() -> dict:
    if not STORIES_INDEX_PATH.exists():
        print(f"[ERROR] {STORIES_INDEX_PATH.relative_to(BASE)} not found.", file=sys.stderr)
        print("  Run Stage 5B-auto first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(STORIES_INDEX_PATH.read_text(encoding="utf-8"))


def build_canonical_map() -> dict:
    """
    Returns {bare_highlight_id: {canonical_title, position, canonical_cover}}
    from highlights_index.json (singhera07 source of truth).
    """
    if not HIGHLIGHTS_IDX_PATH.exists():
        return {}
    data = json.loads(HIGHLIGHTS_IDX_PATH.read_text(encoding="utf-8"))
    result = {}
    for i, h in enumerate(data.get("highlights", []), start=1):
        raw_id = h.get("highlight_id", {})
        if isinstance(raw_id, dict):
            raw_id = raw_id.get("value", "")
        bare = str(raw_id or "").removeprefix("highlight:").strip()
        if not bare:
            continue
        title_f = h.get("title", {})
        title = title_f.get("value", "") if isinstance(title_f, dict) else str(title_f or "")
        cover_f = h.get("cover_image_url", {})
        cover = cover_f.get("value", "") if isinstance(cover_f, dict) else str(cover_f or "")
        result[bare] = {
            "position": i,
            "canonical_title": title or None,
            "canonical_cover": cover or None,
        }
    return result


# ---------------------------------------------------------------------------
# Story selection
# ---------------------------------------------------------------------------

def select_stories(stories: list[dict], n: int, mode: str) -> list[dict]:
    """
    Select up to n stories from a highlight's story list.
    mode: "first" | "last" | "spread" (evenly distributed)
    """
    m = len(stories)
    if n <= 0 or m == 0:
        return []
    if n >= m:
        return list(stories)
    if mode == "first":
        return stories[:n]
    if mode == "last":
        return stories[-n:]
    # spread: evenly distributed indices
    indices = [int(i * m / n) for i in range(n)]
    return [stories[idx] for idx in indices]


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_key(story_id: str, model: str, detail: str) -> str:
    safe_id    = re.sub(r"[^\w-]", "_", str(story_id))
    safe_model = re.sub(r"[^\w-]", "_", model)
    return f"{safe_id}__{safe_model}__{detail}__pv{PROMPT_VERSION}.json"


def cache_path(story_id: str, model: str, detail: str) -> Path:
    return CACHE_DIR / _cache_key(story_id, model, detail)


def load_from_cache(story_id: str, model: str, detail: str) -> dict | None:
    p = cache_path(story_id, model, detail)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_to_cache(result: dict, story_id: str, model: str, detail: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(story_id, model, detail).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# URL accessibility check
# ---------------------------------------------------------------------------

def check_url(url: str | None) -> tuple[bool, str]:
    """Returns (accessible, reason). Reason 'ok' when accessible."""
    if not url:
        return False, "no_url"
    try:
        import requests as _requests
        r = _requests.head(url, timeout=6, allow_redirects=True)
        if r.status_code == 200:
            return True, "ok"
        return False, f"http_{r.status_code}"
    except ImportError:
        # requests not installed: skip check and assume accessible
        return True, "check_skipped_no_requests"
    except Exception as e:
        return False, f"error_{type(e).__name__}"


# ---------------------------------------------------------------------------
# OpenAI analysis
# ---------------------------------------------------------------------------

def _resolve_image_url(story: dict) -> tuple[str | None, str]:
    """
    Returns (url, field_name_used).
    Videos use thumbnailUrl. Images use imageUrl, fallback to mediaUrl.
    """
    media_type = story.get("mediaType") or ""
    if media_type == "Video":
        return story.get("thumbnailUrl"), "thumbnailUrl"
    url = story.get("imageUrl") or story.get("mediaUrl")
    return url, "imageUrl"


def analyze_one(
    client,
    story: dict,
    highlight_meta: dict,
    model: str,
    detail: str,
) -> dict:
    """
    Analyze a single story. Returns result dict with status='analyzed' or 'skipped'.
    Saves result to cache immediately after successful analysis.
    """
    story_id       = story.get("id") or story.get("storyId") or "unknown"
    highlight_id   = (story.get("highlightId") or "").removeprefix("highlight:")
    canonical_title = highlight_meta.get("canonical_title") or highlight_id
    media_type     = story.get("mediaType") or "Unknown"

    base_result = {
        "story_id":            story_id,
        "highlight_id":        highlight_id,
        "canonical_title":     canonical_title,
        "position_in_highlight": story.get("_selection_index"),
        "mediaType":           media_type,
        "model":               model,
        "detail":              detail,
        "prompt_version":      PROMPT_VERSION,
        "analysis_timestamp":  datetime.now(timezone.utc).isoformat(),
    }

    # Check cache first
    cached = load_from_cache(story_id, model, detail)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    # Resolve image URL
    img_url, url_field = _resolve_image_url(story)
    base_result["url_used_field"] = url_field

    # Check URL accessibility
    accessible, reason = check_url(img_url)
    if not accessible:
        result = {
            **base_result,
            "status":      "skipped",
            "skip_reason": f"url_unavailable: {reason}",
            "from_cache":  False,
        }
        return result

    # Build messages
    user_prompt = _build_user_prompt(highlight_id, canonical_title, media_type)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text",      "text": user_prompt},
                {"type": "image_url", "image_url": {"url": img_url, "detail": detail}},
            ],
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=600,
        )
        raw_content = response.choices[0].message.content
        analysis    = json.loads(raw_content)
        tokens_used = response.usage.total_tokens if response.usage else None
    except Exception as e:
        result = {
            **base_result,
            "status":      "error",
            "error":       str(e),
            "from_cache":  False,
        }
        return result

    result = {
        **base_result,
        "status":      "analyzed",
        "url_used_field": url_field,
        "analysis":    analysis,
        "tokens_used": tokens_used,
        "from_cache":  False,
    }
    save_to_cache(result, story_id, model, detail)
    return result


# ---------------------------------------------------------------------------
# Per-highlight aggregate
# ---------------------------------------------------------------------------

def _aggregate_highlight(
    highlight_id: str,
    canonical_meta: dict,
    stories_total: int,
    results: list[dict],
) -> dict:
    analyzed  = [r for r in results if r.get("status") == "analyzed"]
    skipped   = [r for r in results if r.get("status") == "skipped"]
    errors    = [r for r in results if r.get("status") == "error"]
    from_cache = sum(1 for r in results if r.get("from_cache"))

    def _count(key: str, items: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in items:
            v = (r.get("analysis") or {}).get(key)
            if v:
                counts[v] = counts.get(v, 0) + 1
        return counts

    def _dominant(counts: dict[str, int]) -> str | None:
        return max(counts, key=counts.get) if counts else None

    ctype_dist  = _count("content_type", analyzed)
    crole_dist  = _count("commercial_role", analyzed)
    sentiment_d = _count("sentiment", analyzed)

    n = len(analyzed)
    cta_rate   = sum(1 for r in analyzed if (r.get("analysis") or {}).get("has_cta")) / n if n else 0
    text_rate  = sum(1 for r in analyzed if (r.get("analysis") or {}).get("has_visible_text")) / n if n else 0

    all_tags: list[str] = []
    for r in analyzed:
        all_tags.extend((r.get("analysis") or {}).get("tags") or [])
    tag_counts: dict[str, int] = {}
    for t in all_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1
    common_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:8]

    ctas = [
        (r.get("analysis") or {}).get("cta_text")
        for r in analyzed
        if (r.get("analysis") or {}).get("has_cta")
    ]
    ctas = [c for c in ctas if c]

    return {
        "highlight_id":                  highlight_id,
        "canonical_title":               canonical_meta.get("canonical_title"),
        "position":                      canonical_meta.get("position"),
        "stories_total":                 stories_total,
        "stories_selected":              len(results),
        "stories_analyzed":              len(analyzed),
        "stories_skipped":               len(skipped),
        "stories_error":                 len(errors),
        "stories_from_cache":            from_cache,
        "content_type_distribution":     ctype_dist,
        "commercial_role_distribution":  crole_dist,
        "sentiment_distribution":        sentiment_d,
        "dominant_content_type":         _dominant(ctype_dist),
        "dominant_commercial_role":      _dominant(crole_dist),
        "cta_rate":                      round(cta_rate, 3),
        "has_visible_text_rate":         round(text_rate, 3),
        "common_tags":                   common_tags,
        "extracted_ctas":                ctas,
    }


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(
    max_stories_per_hl: int,
    selection_mode: str,
    highlight_ids_filter: list[str] | None,
    model: str,
    detail: str,
    budget_max_usd: float,
) -> None:
    idx = load_stories_index()
    canonical_map = build_canonical_map()
    highlights = idx.get("highlights", [])

    if highlight_ids_filter:
        highlights = [h for h in highlights if h.get("highlight_id") in highlight_ids_filter]

    cost_per = COST_PER_CALL.get((model, detail), 0.02)
    total_planned = 0

    print("=== Stage 5C: DRY RUN ===")
    print(f"Model:          {model}")
    print(f"Detail:         {detail}")
    print(f"Selection mode: {selection_mode}")
    print(f"Max stories/hl: {max_stories_per_hl}")
    print(f"Budget max:     ${budget_max_usd:.2f}")
    print(f"Cost/call est:  ${cost_per:.4f}")
    print()

    for h in highlights:
        hid     = h.get("highlight_id") or "?"
        stories = h.get("stories", [])
        meta    = canonical_map.get(hid, {})
        title   = meta.get("canonical_title") or h.get("automation_lab_title") or "?"
        selected = select_stories(stories, max_stories_per_hl, selection_mode)

        cached_count = sum(
            1 for s in selected
            if load_from_cache(s.get("id") or "?", model, detail) is not None
        )
        new_calls = len(selected) - cached_count

        print(f"  highlight_id: {hid}")
        print(f"    canonical_title: \"{title}\"")
        print(f"    stories total:    {len(stories)}")
        print(f"    stories selected: {len(selected)}  ({selection_mode})")
        print(f"    from cache:       {cached_count}")
        print(f"    new OpenAI calls: {new_calls}")
        print(f"    est. cost:        ${new_calls * cost_per:.4f}")
        print()
        total_planned += new_calls

    total_cost = total_planned * cost_per
    print(f"Total planned calls: {total_planned}")
    print(f"Total estimated cost: ${total_cost:.4f}")
    if total_cost > budget_max_usd:
        print(f"[WARN] Estimated cost ${total_cost:.4f} exceeds --budget-max-usd ${budget_max_usd:.2f}.")
        print("  Run will stop when budget is reached.")
    else:
        print(f"[OK] Estimated cost ${total_cost:.4f} is within budget ${budget_max_usd:.2f}.")
    print()
    print("[DRY RUN] No OpenAI call made. No files written.")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main analyze loop
# ---------------------------------------------------------------------------

def analyze(
    client,
    max_stories_per_hl: int,
    selection_mode: str,
    highlight_ids_filter: list[str] | None,
    model: str,
    detail: str,
    budget_max_usd: float,
    force: bool = False,
) -> dict:
    idx = load_stories_index()
    canonical_map = build_canonical_map()
    highlights = idx.get("highlights", [])

    if highlight_ids_filter:
        highlights = [h for h in highlights if h.get("highlight_id") in highlight_ids_filter]
    if not highlights:
        print("[ERROR] No highlights to process (check --highlight-ids or stage5b_auto_stories_index).",
              file=sys.stderr)
        sys.exit(1)

    cost_per = COST_PER_CALL.get((model, detail), 0.02)
    cumulative_cost = 0.0
    budget_reached  = False

    all_results:    list[dict]  = []
    hl_summaries:   list[dict]  = []
    total_analyzed  = 0
    total_skipped   = 0
    total_from_cache = 0
    total_errors    = 0

    for h in highlights:
        hid     = h.get("highlight_id") or "?"
        stories = h.get("stories", [])
        meta    = canonical_map.get(hid, {})
        title   = meta.get("canonical_title") or h.get("automation_lab_title") or hid
        selected = select_stories(stories, max_stories_per_hl, selection_mode)

        print(f"\n[HL] {hid}  \"{title}\"  ({len(selected)}/{len(stories)} selected)")

        hl_results: list[dict] = []

        for pos, story in enumerate(selected):
            if budget_reached:
                break

            story["_selection_index"] = pos
            story_id = story.get("id") or story.get("storyId") or f"unknown_{pos}"

            # Cache check (skip OpenAI if cached and not forced)
            if not force:
                cached = load_from_cache(story_id, model, detail)
                if cached is not None:
                    cached["from_cache"] = True
                    hl_results.append(cached)
                    all_results.append(cached)
                    total_from_cache += 1
                    print(f"  [{pos:>3}] {story_id}  [cache]")
                    continue

            # Budget check before calling OpenAI
            if cumulative_cost + cost_per > budget_max_usd:
                print(f"\n[BUDGET] Reached ${budget_max_usd:.2f} limit "
                      f"(spent ${cumulative_cost:.4f}). Stopping.")
                budget_reached = True
                break

            result = analyze_one(client, story, meta, model, detail)
            hl_results.append(result)
            all_results.append(result)

            if result["status"] == "analyzed":
                cumulative_cost += cost_per
                total_analyzed  += 1
                print(f"  [{pos:>3}] {story_id}  {result['status']}"
                      f"  (cumulative: ${cumulative_cost:.4f})")
            elif result["status"] == "skipped":
                total_skipped += 1
                print(f"  [{pos:>3}] {story_id}  SKIP: {result.get('skip_reason', '?')}")
            else:
                total_errors += 1
                print(f"  [{pos:>3}] {story_id}  ERROR: {result.get('error', '?')}")

        hl_sum = _aggregate_highlight(hid, meta, len(stories), hl_results)
        hl_summaries.append(hl_sum)

    # Save outputs
    NORM_DIR.mkdir(parents=True, exist_ok=True)

    ANALYSIS_PATH.write_text(
        json.dumps({"results": all_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    HL_SUMMARY_PATH.write_text(
        json.dumps({"highlights": hl_summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n[INFO] Analysis:    {ANALYSIS_PATH.relative_to(BASE)}")
    print(f"[INFO] HL summary:  {HL_SUMMARY_PATH.relative_to(BASE)}")

    run_summary = {
        "model":             model,
        "detail":            detail,
        "selection_mode":    selection_mode,
        "max_stories_per_hl": max_stories_per_hl,
        "budget_max_usd":    budget_max_usd,
        "cumulative_cost_usd": round(cumulative_cost, 4),
        "budget_reached":    budget_reached,
        "total_analyzed":    total_analyzed,
        "total_from_cache":  total_from_cache,
        "total_skipped":     total_skipped,
        "total_errors":      total_errors,
        "highlights_processed": len(hl_summaries),
        "run_timestamp":     datetime.now(timezone.utc).isoformat(),
    }
    return run_summary
