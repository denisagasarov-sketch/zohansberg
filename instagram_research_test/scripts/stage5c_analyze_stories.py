#!/usr/bin/env python3
"""
Stage 5C: OpenAI Vision analysis of highlight stories.

Reads data/normalized/stage5b_auto_stories_index.json (Stage 5B-auto).
Classifies each story image using OpenAI Vision (gpt-4o-mini by default).

Media input: base64 by default (fetched in-memory, never written to disk).
Direct CDN URLs are NOT passed to OpenAI — Instagram CDN URLs fail OpenAI fetch.
Videos use thumbnailUrl only. No mp4 fetched.

Cache key: story_id + model + detail + prompt_version + image_input_mode.
Only "analyzed" results are stored in cache; errors/skips are not cached.
"""

import base64
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data/normalized"
CACHE_DIR = BASE / "data/raw/stage5c_cache"

STORIES_INDEX_PATH  = NORM_DIR / "stage5b_auto_stories_index.json"
HIGHLIGHTS_IDX_PATH = NORM_DIR / "highlights_index.json"
ANALYSIS_PATH       = NORM_DIR / "stage5c_stories_analysis.json"
HL_SUMMARY_PATH     = NORM_DIR / "stage5c_highlights_summary.json"

PROMPT_VERSION     = "v1"
DEFAULT_MODEL      = "gpt-4o-mini"
DEFAULT_DETAIL     = "low"
DEFAULT_INPUT_MODE = "base64"
MAX_IMAGE_BYTES    = 8 * 1024 * 1024  # 8 MB

# Conservative per-call cost estimates (image + prompt + output tokens)
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

# Status values
STATUS_ANALYZED         = "analyzed"
STATUS_SKIP_NO_URL      = "skipped_no_url"
STATUS_SKIP_FETCH       = "skipped_media_fetch_failed"
STATUS_SKIP_CONTENT     = "skipped_invalid_content_type"
STATUS_SKIP_SIZE        = "skipped_media_too_large"
STATUS_OPENAI_ERROR     = "openai_error"

CACHEABLE_STATUSES = {STATUS_ANALYZED}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

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
# Browser-like headers for media fetch
# ---------------------------------------------------------------------------

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.instagram.com/",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}


class FetchError(Exception):
    """Raised by fetch helpers. reason is a short code, never contains secret URLs."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _fetch_once(url: str, headers: dict) -> tuple[bytes, str]:
    """
    Single fetch attempt. Returns (image_bytes, content_type).
    Raises FetchError — reason codes never include the URL itself.
    """
    try:
        import requests as _req
    except ImportError:
        raise FetchError("requests_not_installed")

    try:
        r = _req.get(url, headers=headers, timeout=15, stream=True)
    except Exception as exc:
        raise FetchError(f"network_{type(exc).__name__}")

    if r.status_code != 200:
        raise FetchError(f"http_{r.status_code}")

    ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
    if not ct.startswith("image/"):
        raise FetchError(f"invalid_content_type:{ct or 'missing'}")

    chunks: list[bytes] = []
    size = 0
    for chunk in r.iter_content(65536):
        chunks.append(chunk)
        size += len(chunk)
        if size > MAX_IMAGE_BYTES:
            raise FetchError("media_too_large")

    return b"".join(chunks), ct


def fetch_image_for_vision(url: str, cookie: str | None = None) -> tuple[bytes, str]:
    """
    Fetch image bytes with browser-like headers.
    On 401 or 403, retries once with the session cookie if provided.
    Returns (bytes, content_type). Raises FetchError on failure.
    NEVER logs or embeds the URL in error messages.
    """
    headers = dict(_BROWSER_HEADERS)
    try:
        return _fetch_once(url, headers)
    except FetchError as exc:
        if cookie and ("_401" in exc.reason or "_403" in exc.reason):
            headers_with_cookie = {**headers, "Cookie": cookie}
            return _fetch_once(url, headers_with_cookie)
        raise


def _skip_status(reason: str) -> str:
    """Map a FetchError reason to a skip status string."""
    if reason.startswith("invalid_content_type"):
        return STATUS_SKIP_CONTENT
    if reason == "media_too_large":
        return STATUS_SKIP_SIZE
    return STATUS_SKIP_FETCH


def bytes_to_data_url(image_bytes: bytes, content_type: str) -> str:
    """Convert raw image bytes to data:image/...;base64,... URL for OpenAI."""
    ct = content_type.lower().split(";")[0].strip()
    if ct not in ("image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"):
        ct = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{ct};base64,{b64}"


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
    """Returns {bare_highlight_id: {canonical_title, position, canonical_cover}}."""
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
            "position":        i,
            "canonical_title": title or None,
            "canonical_cover": cover or None,
        }
    return result


# ---------------------------------------------------------------------------
# Story selection
# ---------------------------------------------------------------------------

def select_stories(stories: list[dict], n: int, mode: str) -> list[dict]:
    """Select up to n stories. mode: first | last | spread."""
    m = len(stories)
    if n <= 0 or m == 0:
        return []
    if n >= m:
        return list(stories)
    if mode == "first":
        return stories[:n]
    if mode == "last":
        return stories[-n:]
    indices = [int(i * m / n) for i in range(n)]
    return [stories[idx] for idx in indices]


# ---------------------------------------------------------------------------
# Cache (keyed by story_id + model + detail + image_input_mode + prompt_version)
# ---------------------------------------------------------------------------

def _cache_key(story_id: str, model: str, detail: str, image_input_mode: str) -> str:
    safe_id    = re.sub(r"[^\w-]", "_", str(story_id))
    safe_model = re.sub(r"[^\w-]", "_", model)
    return f"{safe_id}__{safe_model}__{detail}__{image_input_mode}__pv{PROMPT_VERSION}.json"


def cache_path(story_id: str, model: str, detail: str, image_input_mode: str) -> Path:
    return CACHE_DIR / _cache_key(story_id, model, detail, image_input_mode)


def load_from_cache(
    story_id: str, model: str, detail: str, image_input_mode: str
) -> dict | None:
    """Return cached result only if status is in CACHEABLE_STATUSES. Errors/skips are ignored."""
    p = cache_path(story_id, model, detail, image_input_mode)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("status") in CACHEABLE_STATUSES:
                return data
        except Exception:
            pass
    return None


def save_to_cache(
    result: dict, story_id: str, model: str, detail: str, image_input_mode: str
) -> None:
    """Save only successfully analyzed results to cache."""
    if result.get("status") not in CACHEABLE_STATUSES:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(story_id, model, detail, image_input_mode).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Resolve media URL for Vision (no logging of URL value)
# ---------------------------------------------------------------------------

def _resolve_media_url(story: dict) -> tuple[str | None, str]:
    """
    Returns (url, field_name). Videos use thumbnailUrl only (no mp4).
    Image field: imageUrl → mediaUrl fallback.
    """
    if story.get("mediaType") == "Video":
        return story.get("thumbnailUrl"), "thumbnailUrl"
    return story.get("imageUrl") or story.get("mediaUrl"), "imageUrl"


# ---------------------------------------------------------------------------
# Single story analysis
# ---------------------------------------------------------------------------

def analyze_one(
    client,
    story: dict,
    highlight_meta: dict,
    model: str,
    detail: str,
    image_input_mode: str,
    cookie: str | None,
) -> dict:
    """
    Analyze one story. Returns result dict. Saves to cache on success.
    Secrets (cookie, URLs) are never logged.
    """
    story_id        = story.get("id") or story.get("storyId") or "unknown"
    highlight_id    = (story.get("highlightId") or "").removeprefix("highlight:")
    canonical_title = highlight_meta.get("canonical_title") or highlight_id
    media_type      = story.get("mediaType") or "Unknown"

    base_result = {
        "story_id":              story_id,
        "highlight_id":          highlight_id,
        "canonical_title":       canonical_title,
        "position_in_highlight": story.get("_selection_index"),
        "mediaType":             media_type,
        "model":                 model,
        "detail":                detail,
        "image_input_mode":      image_input_mode,
        "prompt_version":        PROMPT_VERSION,
        "analysis_timestamp":    datetime.now(timezone.utc).isoformat(),
    }

    # Check cache (only previously analyzed results count)
    cached = load_from_cache(story_id, model, detail, image_input_mode)
    if cached is not None:
        cached["from_cache"] = True
        return cached

    # Resolve URL (never logged)
    media_url, url_field = _resolve_media_url(story)
    base_result["url_used_field"] = url_field

    if not media_url:
        return {**base_result, "status": STATUS_SKIP_NO_URL, "from_cache": False}

    # ------------------------------------------------------------------
    # Base64 mode: fetch bytes in memory, never written to disk
    # ------------------------------------------------------------------
    if image_input_mode == "base64":
        try:
            img_bytes, content_type = fetch_image_for_vision(media_url, cookie)
        except FetchError as exc:
            return {
                **base_result,
                "status":      _skip_status(exc.reason),
                "skip_reason": exc.reason,
                "from_cache":  False,
            }
        data_url  = bytes_to_data_url(img_bytes, content_type)
        image_input = {"url": data_url, "detail": detail}
        base_result["fetch_bytes"] = len(img_bytes)
        base_result["fetch_content_type"] = content_type

    # ------------------------------------------------------------------
    # Direct URL mode (not recommended; Instagram CDN URLs fail OpenAI)
    # ------------------------------------------------------------------
    else:
        image_input = {"url": media_url, "detail": detail}

    # ------------------------------------------------------------------
    # OpenAI Vision call
    # ------------------------------------------------------------------
    user_prompt = _build_user_prompt(highlight_id, canonical_title, media_type)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text",      "text": user_prompt},
                {"type": "image_url", "image_url": image_input},
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
    except Exception as exc:
        return {
            **base_result,
            "status":    STATUS_OPENAI_ERROR,
            "error":     str(exc),
            "from_cache": False,
        }

    result = {
        **base_result,
        "status":      STATUS_ANALYZED,
        "analysis":    analysis,
        "tokens_used": tokens_used,
        "from_cache":  False,
    }
    save_to_cache(result, story_id, model, detail, image_input_mode)
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
    analyzed   = [r for r in results if r.get("status") == STATUS_ANALYZED]
    from_cache = sum(1 for r in results if r.get("from_cache"))
    skipped    = [r for r in results if r.get("status", "").startswith("skipped_")]
    errors     = [r for r in results if r.get("status") == STATUS_OPENAI_ERROR]

    def _count(key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in analyzed:
            v = (r.get("analysis") or {}).get(key)
            if v:
                counts[v] = counts.get(v, 0) + 1
        return counts

    ctype_d    = _count("content_type")
    crole_d    = _count("commercial_role")
    sentiment_d = _count("sentiment")
    n = len(analyzed)

    cta_rate  = sum(1 for r in analyzed if (r.get("analysis") or {}).get("has_cta")) / n if n else 0
    text_rate = sum(1 for r in analyzed if (r.get("analysis") or {}).get("has_visible_text")) / n if n else 0

    tag_counts: dict[str, int] = {}
    for r in analyzed:
        for t in (r.get("analysis") or {}).get("tags") or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    common_tags = sorted(tag_counts, key=tag_counts.get, reverse=True)[:8]

    ctas = [
        (r.get("analysis") or {}).get("cta_text")
        for r in analyzed
        if (r.get("analysis") or {}).get("has_cta")
    ]
    ctas = [c for c in ctas if c]

    skip_reasons: dict[str, int] = {}
    for r in skipped:
        reason = r.get("skip_reason") or r.get("status", "unknown")
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1

    return {
        "highlight_id":                 highlight_id,
        "canonical_title":              canonical_meta.get("canonical_title"),
        "position":                     canonical_meta.get("position"),
        "stories_total":                stories_total,
        "stories_selected":             len(results),
        "stories_analyzed":             n,
        "stories_from_cache":           from_cache,
        "stories_skipped":              len(skipped),
        "stories_openai_error":         len(errors),
        "skip_reason_counts":           skip_reasons,
        "content_type_distribution":    ctype_d,
        "commercial_role_distribution": crole_d,
        "sentiment_distribution":       sentiment_d,
        "dominant_content_type":        max(ctype_d, key=ctype_d.get) if ctype_d else None,
        "dominant_commercial_role":     max(crole_d, key=crole_d.get) if crole_d else None,
        "cta_rate":                     round(cta_rate, 3),
        "has_visible_text_rate":        round(text_rate, 3),
        "common_tags":                  common_tags,
        "extracted_ctas":               ctas,
    }


# ---------------------------------------------------------------------------
# Test media fetch (no OpenAI)
# ---------------------------------------------------------------------------

def test_media_fetch(
    max_stories_per_hl: int,
    selection_mode: str,
    cookie: str | None,
) -> None:
    """
    Fetch one image story and one video-thumbnail story in memory.
    No OpenAI call. No files written. No URLs printed.
    """
    idx = load_stories_index()
    image_story: tuple[dict, str] | None = None
    video_story: tuple[dict, str] | None = None

    for h in idx.get("highlights", []):
        hid     = h.get("highlight_id") or "?"
        stories = select_stories(h.get("stories", []), max_stories_per_hl, selection_mode)
        for s in stories:
            if image_story is None and s.get("mediaType") == "Image":
                image_story = (s, hid)
            if video_story is None and s.get("mediaType") == "Video":
                video_story = (s, hid)
            if image_story and video_story:
                break
        if image_story and video_story:
            break

    print("=== Stage 5C: TEST MEDIA FETCH ===")
    print("No OpenAI call. No files written. URLs not printed.")
    print(f"cookie_present: {'yes' if cookie else 'no'}")
    print()

    def _test_one(label: str, story: dict, hid: str) -> None:
        story_id   = story.get("id") or "?"
        media_type = story.get("mediaType", "?")
        url, url_field = _resolve_media_url(story)
        print(f"  [{label}]")
        print(f"    story_id={story_id}  highlight_id={hid}  mediaType={media_type}")
        print(f"    url_field={url_field}  url_present={'yes' if url else 'no'}")
        if not url:
            print(f"    RESULT: SKIP  reason=no_url")
            return
        try:
            img_bytes, ct = fetch_image_for_vision(url, cookie)
            data_url = bytes_to_data_url(img_bytes, ct)
            print(f"    RESULT: OK")
            print(f"    bytes={len(img_bytes)}  content_type={ct}")
            print(f"    data_url_prefix={data_url[:40]}...")
        except FetchError as exc:
            print(f"    RESULT: FAIL  reason={exc.reason}")

    if image_story:
        _test_one("Image story", image_story[0], image_story[1])
    else:
        print("  [Image story] none found in selection")

    print()

    if video_story:
        _test_one("Video thumbnail", video_story[0], video_story[1])
    else:
        print("  [Video thumbnail] none found in selection")

    print()
    print("[TEST MEDIA FETCH] Done. No OpenAI called. No files written.")
    sys.exit(0)


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
    image_input_mode: str,
) -> None:
    idx           = load_stories_index()
    canonical_map = build_canonical_map()
    highlights    = idx.get("highlights", [])

    if highlight_ids_filter:
        highlights = [h for h in highlights if h.get("highlight_id") in highlight_ids_filter]

    cost_per    = COST_PER_CALL.get((model, detail), 0.02)
    total_planned = 0

    print("=== Stage 5C: DRY RUN ===")
    print(f"Model:            {model}")
    print(f"Detail:           {detail}")
    print(f"Image input mode: {image_input_mode}")
    print(f"  (base64 = fetched in-memory, NOT written to disk, NOT sent as CDN URL)")
    print(f"  (video stories use thumbnailUrl only — no mp4 fetched)")
    print(f"Selection mode:   {selection_mode}")
    print(f"Max stories/hl:   {max_stories_per_hl}")
    print(f"Budget max:       ${budget_max_usd:.2f}")
    print(f"Cost/call est:    ${cost_per:.4f}")
    print()

    for h in highlights:
        hid      = h.get("highlight_id") or "?"
        stories  = h.get("stories", [])
        meta     = canonical_map.get(hid, {})
        title    = meta.get("canonical_title") or h.get("automation_lab_title") or "?"
        selected = select_stories(stories, max_stories_per_hl, selection_mode)

        cached_count = sum(
            1 for s in selected
            if load_from_cache(s.get("id") or "?", model, detail, image_input_mode) is not None
        )
        new_calls = len(selected) - cached_count

        print(f"  {hid}  \"{title}\"")
        print(f"    stories total:    {len(stories)}")
        print(f"    stories selected: {len(selected)}  ({selection_mode})")
        print(f"    from cache:       {cached_count}")
        print(f"    new OpenAI calls: {new_calls}")
        print(f"    est. cost:        ${new_calls * cost_per:.4f}")
        print()
        total_planned += new_calls

    total_cost = total_planned * cost_per
    print(f"Total planned calls: {total_planned}")
    print(f"Total est. cost:     ${total_cost:.4f}")
    if total_cost > budget_max_usd:
        print(f"[WARN] Estimated ${total_cost:.4f} exceeds budget ${budget_max_usd:.2f}.")
        print("  Run will stop softly when budget is reached.")
    else:
        print(f"[OK] Estimated ${total_cost:.4f} within budget ${budget_max_usd:.2f}.")
    print()
    print("[DRY RUN] No OpenAI call. No media fetch. No files written.")
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
    image_input_mode: str,
    cookie: str | None,
    force: bool = False,
) -> dict:
    idx           = load_stories_index()
    canonical_map = build_canonical_map()
    highlights    = idx.get("highlights", [])

    if highlight_ids_filter:
        highlights = [h for h in highlights if h.get("highlight_id") in highlight_ids_filter]
    if not highlights:
        print("[ERROR] No highlights to process.", file=sys.stderr)
        sys.exit(1)

    cost_per        = COST_PER_CALL.get((model, detail), 0.02)
    cumulative_cost = 0.0
    budget_reached  = False

    all_results:      list[dict] = []
    hl_summaries:     list[dict] = []
    total_analyzed    = 0
    total_from_cache  = 0
    total_skipped     = 0
    total_errors      = 0

    for h in highlights:
        hid      = h.get("highlight_id") or "?"
        stories  = h.get("stories", [])
        meta     = canonical_map.get(hid, {})
        title    = meta.get("canonical_title") or hid
        selected = select_stories(stories, max_stories_per_hl, selection_mode)

        print(f"\n[HL] {hid}  \"{title}\"  ({len(selected)}/{len(stories)} selected)")

        hl_results: list[dict] = []

        for pos, story in enumerate(selected):
            if budget_reached:
                break

            story["_selection_index"] = pos
            story_id   = story.get("id") or story.get("storyId") or f"unknown_{pos}"
            media_type = story.get("mediaType", "?")
            url, url_field = _resolve_media_url(story)

            # Cache check (only valid analyzed results count; errors/skips do not)
            if not force:
                cached = load_from_cache(story_id, model, detail, image_input_mode)
                if cached is not None:
                    cached["from_cache"] = True
                    hl_results.append(cached)
                    all_results.append(cached)
                    total_from_cache += 1
                    print(f"  [{pos:>3}] id={story_id}  hl={hid}  type={media_type}  [cache]")
                    continue

            if cumulative_cost + cost_per > budget_max_usd:
                print(f"\n[BUDGET] Reached ${budget_max_usd:.2f} "
                      f"(spent ${cumulative_cost:.4f}). Stopping.")
                budget_reached = True
                break

            result = analyze_one(
                client, story, meta, model, detail, image_input_mode, cookie
            )
            hl_results.append(result)
            all_results.append(result)

            status = result["status"]
            if status == STATUS_ANALYZED:
                cumulative_cost += cost_per
                total_analyzed  += 1
                print(f"  [{pos:>3}] id={story_id}  hl={hid}  type={media_type}  "
                      f"url_field={url_field}  OK  (${cumulative_cost:.4f})")
            elif status.startswith("skipped_"):
                total_skipped += 1
                reason = result.get("skip_reason") or status
                print(f"  [{pos:>3}] id={story_id}  hl={hid}  type={media_type}  "
                      f"SKIP  reason={reason}")
            else:
                total_errors += 1
                err = str(result.get("error") or "")[:80]
                print(f"  [{pos:>3}] id={story_id}  hl={hid}  type={media_type}  "
                      f"ERROR  {err}")

        hl_sum = _aggregate_highlight(hid, meta, len(stories), hl_results)
        hl_summaries.append(hl_sum)

    NORM_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_PATH.write_text(
        json.dumps({"results": all_results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    HL_SUMMARY_PATH.write_text(
        json.dumps({"highlights": hl_summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[INFO] Analysis:   {ANALYSIS_PATH.relative_to(BASE)}")
    print(f"[INFO] HL summary: {HL_SUMMARY_PATH.relative_to(BASE)}")

    return {
        "model":               model,
        "detail":              detail,
        "image_input_mode":    image_input_mode,
        "selection_mode":      selection_mode,
        "max_stories_per_hl":  max_stories_per_hl,
        "budget_max_usd":      budget_max_usd,
        "cumulative_cost_usd": round(cumulative_cost, 4),
        "budget_reached":      budget_reached,
        "total_analyzed":      total_analyzed,
        "total_from_cache":    total_from_cache,
        "total_skipped":       total_skipped,
        "total_errors":        total_errors,
        "highlights_processed": len(hl_summaries),
        "run_timestamp":       datetime.now(timezone.utc).isoformat(),
    }
