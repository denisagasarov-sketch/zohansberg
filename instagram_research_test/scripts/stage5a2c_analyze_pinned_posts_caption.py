"""Stage 5A-2C: Caption-only semantic analyzer for 3 pinned posts.

Reads data/normalized/stage5a2b_pinned_posts_details.json.
Sends ONLY full caption text to OpenAI (no images, no CDN URLs).
Produces per-post semantic JSON and Google Sheets-ready rows.

Does NOT: analyze images, do OCR, call Apify, write to Google Sheets.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data" / "normalized"
CACHE_DIR = BASE / "analysis" / "stage5a2c_cache"

STAGE5A2B_PATH = NORM_DIR / "stage5a2b_pinned_posts_details.json"

SEMANTIC_OUTPUT_PATH  = NORM_DIR / "stage5a2c_pinned_posts_semantic.json"
GS_ROWS_OUTPUT_PATH   = NORM_DIR / "stage5a2c_pinned_posts_google_sheet_rows.json"

ACCOUNT         = "vlada_kliuiko"
EXPECTED_POSTS  = 3
PROMPT_VERSION  = "v1"
DEFAULT_MODEL   = "gpt-4o-mini"  # same as Stage 5C; text-only here

# Conservative cost estimate for text-only gpt-4o-mini
# ~1500 input tokens + ~300 output per call
# $0.15/1M input + $0.60/1M output ≈ $0.0004 per call
COST_PER_CALL: dict[str, float] = {
    "gpt-4o-mini": 0.0004,
    "gpt-4o":      0.008,
}

# ── Field constraints ──────────────────────────────────────────────────────

CELL_LIMITS = {
    "Тема поста":            160,
    "Почему закреплен":      250,
    "Хук / первый экран":    0,    # always empty in this stage
    "Что в тексте поста":    350,
    "Ключевые смыслы":       500,
    "Какой CTA":             180,
    "Куда ведет CTA":        180,
    "Роль в воронке":        80,
}

ALLOWED_FUNNEL_ROLES = {
    "знакомство", "доверие", "прогрев", "продажа", "лидогенерация",
}

ALLOWED_CTA_DESTINATIONS = {
    "директ", "комментарии", "био-ссылка", "анкета",
    "закрытый канал", "консультация", "курс", "сайт", "unknown",
}

GS_FIELD_ORDER = [
    "Конкурент",
    "Ссылка на пост",
    "Позиция закрепа",
    "Тема поста",
    "Почему закреплен",
    "Хук / первый экран",
    "Что в тексте поста",
    "Ключевые смыслы",
    "Какой CTA",
    "Куда ведет CTA",
    "Роль в воронке",
]

# ── Prompts ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Ты аналитик конкурентного Instagram-контента.
Тебе дают полный текст (caption) закрепленного поста.
Проанализируй ТОЛЬКО текст. Не домысливай из картинок или видео.
Верни ТОЛЬКО JSON-объект — без markdown, без пояснений, только JSON.
Все текстовые значения — на русском языке."""


def build_user_prompt(post: dict) -> str:
    caption      = post.get("full_caption") or post.get("caption_for_analysis") or ""
    position     = post.get("position", "?")
    media_type   = post.get("media_type") or "неизвестно"
    caption_len  = post.get("caption_length", len(caption))
    permalink    = post.get("permalink") or ""

    funnel_roles_str = " | ".join(sorted(ALLOWED_FUNNEL_ROLES))
    cta_dest_str     = " | ".join(sorted(ALLOWED_CTA_DESTINATIONS))

    return f"""\
Закрепленный пост Instagram #{position}.
Тип поста: {media_type}. Длина caption: {caption_len} символов.
Permalink: {permalink}

=== CAPTION ===
{caption}
=== END CAPTION ===

Верни JSON по схеме ниже. Если поле не поддерживается текстом — верни пустую строку "".

{{
  "Тема поста": "<одна строка, макс 160 символов>",
  "Почему закреплен": "<ОБЯЗАТЕЛЬНО начни с Вероятно: инференс почему автор закрепил этот пост, макс 250 символов>",
  "Что в тексте поста": "<краткая структура текста поста, макс 350 символов>",
  "Ключевые смыслы": "<только смыслы из текста, не придумывать, макс 500 символов>",
  "Какой CTA": "<точный CTA из текста или пустая строка, макс 180 символов>",
  "Куда ведет CTA": "<одно из: {cta_dest_str}; или пустая строка если CTA нет>",
  "Роль в воронке": "<одно или два из: {funnel_roles_str}; несколько через / >",
  "confidence": {{
    "Тема поста": "high | medium | low",
    "Почему закреплен": "high | medium | low",
    "Что в тексте поста": "high | medium | low",
    "Ключевые смыслы": "high | medium | low",
    "Какой CTA": "high | medium | low",
    "Куда ведет CTA": "high | medium | low",
    "Роль в воронке": "high | medium | low"
  }},
  "evidence": {{
    "caption_quotes": ["<макс 2 коротких цитаты, которые поддерживают твои выводы>"],
    "cta_quotes": ["<точная CTA фраза из текста, если есть>"],
    "source_notes": []
  }},
  "limitations": ["<что нельзя определить из текста>"]
}}

ВАЖНО:
- Поле "Почему закреплен" — всегда инференс, не факт. Начни с "Вероятно".
- "Роль в воронке" — используй только из списка: {funnel_roles_str}
- "Куда ведет CTA" — используй только из списка или пустую строку
- Не придумывай позиционирование, не добавляй то, чего нет в тексте
- Не используй общие формулировки "экспертный контент" без доказательств из текста"""


# ── Cache ──────────────────────────────────────────────────────────────────

def _cache_key(post_id: str, caption: str, model: str) -> str:
    cap_hash = hashlib.sha256(caption.encode("utf-8", errors="replace")).hexdigest()[:16]
    safe_id  = re.sub(r"[^\w-]", "_", str(post_id))[:40]
    safe_mod = re.sub(r"[^\w-]", "_", model)
    return f"{safe_id}__{safe_mod}__pv{PROMPT_VERSION}__{cap_hash}.json"


def cache_path(post_id: str, caption: str, model: str) -> Path:
    return CACHE_DIR / _cache_key(post_id, caption, model)


def load_from_cache(post_id: str, caption: str, model: str) -> dict | None:
    p = cache_path(post_id, caption, model)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("status") == "analyzed":
            return data
    except Exception:
        pass
    return None


def save_to_cache(result: dict, post_id: str, caption: str, model: str):
    if result.get("status") != "analyzed":
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path(post_id, caption, model).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── Response parser & validator ────────────────────────────────────────────

def _validate_and_fix(raw: dict, post: dict) -> tuple[dict, list[str]]:
    """
    Validate OpenAI response, apply cell limits, enforce constraints.
    Returns (fixed_dict, validation_warnings).
    """
    warns = []
    fixed = dict(raw)

    # "Почему закреплен" must start with inference marker
    pz = fixed.get("Почему закреплен", "")
    if pz and not re.match(r"^(Вероятно|Возможно|По всей видимости|Скорее всего)", pz, re.I):
        fixed["Почему закреплен"] = "Вероятно, " + pz
        warns.append("Почему закреплен: prepended 'Вероятно, ' — was missing inference marker")

    # "Роль в воронке" — validate tokens
    rv = fixed.get("Роль в воронке", "")
    if rv:
        tokens = [t.strip() for t in rv.replace(",", "/").split("/") if t.strip()]
        bad_tokens = [t for t in tokens if t not in ALLOWED_FUNNEL_ROLES]
        if bad_tokens:
            warns.append(f"Роль в воронке: unexpected values {bad_tokens}; cleared")
            fixed["Роль в воронке"] = ""

    # "Куда ведет CTA" — validate
    kv = fixed.get("Куда ведет CTA", "")
    if kv and kv not in ALLOWED_CTA_DESTINATIONS and kv != "":
        warns.append(f"Куда ведет CTA: '{kv}' not in allowed list; cleared")
        fixed["Куда ведет CTA"] = ""

    # Cell length enforcement
    for field, limit in CELL_LIMITS.items():
        if limit == 0:
            continue
        val = fixed.get(field, "")
        if isinstance(val, str) and len(val) > limit:
            fixed[field] = val[:limit]
            warns.append(f"{field}: truncated to {limit} chars")

    # Low confidence → prefer empty
    conf = fixed.get("confidence", {})
    for field in ["Ключевые смыслы", "Роль в воронке"]:
        if conf.get(field) == "low" and fixed.get(field):
            warns.append(f"{field}: confidence=low; keeping value but noting uncertainty")

    # Validate required keys
    required = list(CELL_LIMITS.keys())
    required.remove("Хук / первый экран")
    for k in required:
        if k not in fixed:
            fixed[k] = ""
            warns.append(f"{k}: missing from OpenAI response; set to empty")

    # Ensure confidence dict has all semantic fields
    if "confidence" not in fixed:
        fixed["confidence"] = {}
    for field in CELL_LIMITS:
        if field == "Хук / первый экран":
            fixed["confidence"][field] = "low"
        elif field not in fixed.get("confidence", {}):
            fixed["confidence"][field] = "low"
            warns.append(f"confidence[{field}]: missing; set to low")

    return fixed, warns


# ── OpenAI caller ──────────────────────────────────────────────────────────

def analyze_post_caption(
    client,
    post: dict,
    model: str = DEFAULT_MODEL,
    force: bool = False,
) -> dict:
    """
    Analyze one post's caption. Uses cache unless force=True.
    Sends ONLY text to OpenAI — no image URLs.
    """
    caption  = post.get("full_caption") or post.get("caption_for_analysis") or ""
    post_id  = str(post.get("post_id") or post.get("shortcode") or f"pos{post.get('position', 0)}")
    position = post.get("position", 0)

    base_result = {
        "status":    None,
        "post_id":   post_id,
        "position":  position,
        "model":     model,
        "prompt_version": PROMPT_VERSION,
        "tokens_used":    None,
        "from_cache":     False,
    }

    if not caption:
        return {**base_result, "status": "skipped_no_caption", "error": "full_caption is empty"}

    # Cache check
    if not force:
        cached = load_from_cache(post_id, caption, model)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    user_prompt = build_user_prompt(post)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_prompt},
    ]

    raw_content = None
    tokens_used = None

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=900,
        )
        raw_content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else None
    except Exception as exc:
        return {**base_result, "status": "openai_error", "error": str(exc), "from_cache": False}

    # Parse JSON
    try:
        analysis = json.loads(raw_content)
    except Exception:
        # Retry with repair prompt
        repair_messages = messages + [
            {"role": "assistant", "content": raw_content},
            {"role": "user",      "content": "Ответ выше не является валидным JSON. Верни ТОЛЬКО JSON без markdown."},
        ]
        try:
            repair_resp = client.chat.completions.create(
                model=model,
                messages=repair_messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=900,
            )
            raw_content2 = repair_resp.choices[0].message.content
            analysis = json.loads(raw_content2)
            if repair_resp.usage:
                tokens_used = (tokens_used or 0) + repair_resp.usage.total_tokens
        except Exception as exc2:
            return {
                **base_result,
                "status": "json_parse_failed",
                "error":  f"JSON parse failed after repair: {exc2}",
                "raw_content": raw_content,
                "from_cache": False,
            }

    validated, val_warns = _validate_and_fix(analysis, post)
    result = {
        **base_result,
        "status":              "analyzed",
        "analysis":            validated,
        "validation_warnings": val_warns,
        "tokens_used":         tokens_used,
        "from_cache":          False,
    }
    save_to_cache(result, post_id, caption, model)
    return result


# ── Semantic output builder ────────────────────────────────────────────────

def build_semantic_post(post: dict, openai_result: dict) -> dict:
    """Merge post metadata with OpenAI analysis into per-post semantic structure."""
    status    = openai_result.get("status")
    analysis  = openai_result.get("analysis") or {}
    from_cache = openai_result.get("from_cache", False)

    cache_status = "hit" if from_cache else ("miss" if status == "analyzed" else "failed")

    gs_fields = {
        "Тема поста":            analysis.get("Тема поста", ""),
        "Почему закреплен":      analysis.get("Почему закреплен", ""),
        "Хук / первый экран":    "",   # always empty — visual/OCR not done
        "Что в тексте поста":    analysis.get("Что в тексте поста", ""),
        "Ключевые смыслы":       analysis.get("Ключевые смыслы", ""),
        "Какой CTA":             analysis.get("Какой CTA", ""),
        "Куда ведет CTA":        analysis.get("Куда ведет CTA", ""),
        "Роль в воронке":        analysis.get("Роль в воронке", ""),
    }

    confidence = analysis.get("confidence", {})
    confidence["Хук / первый экран"] = "low"

    base_limitations = [
        "Caption-only analysis. Cover image, carousel slides, and OCR were not analyzed.",
        "Хук / первый экран intentionally left empty until Stage 5A-2D visual/OCR stage.",
    ]
    if status != "analyzed":
        base_limitations.append(f"OpenAI call failed: {openai_result.get('error', 'unknown error')}")
    limitations = base_limitations + list(analysis.get("limitations") or [])

    return {
        "position":     post.get("position"),
        "permalink":    post.get("permalink"),
        "shortcode":    post.get("shortcode"),
        "post_id":      post.get("post_id"),
        "caption_length": post.get("caption_length", 0),
        "media_type":   post.get("media_type"),
        "source":       "caption_only",
        "visual_analyzed": False,
        "ocr_analyzed":    False,
        "cache_status":    cache_status,
        "tokens_used":     openai_result.get("tokens_used"),
        "openai_status":   status,

        "google_sheet_fields": gs_fields,
        "confidence":          confidence,
        "evidence":            analysis.get("evidence") or {"caption_quotes": [], "cta_quotes": [], "source_notes": []},
        "limitations":         limitations,
        "validation_warnings": openai_result.get("validation_warnings") or [],
    }


# ── Google Sheets row builder ──────────────────────────────────────────────

def build_gs_row(
    semantic: dict,
    stage5a2b_post: dict,
    headers: list[str],
) -> list[str]:
    """Build a Google Sheets row (list of str) in header order."""
    gf = semantic.get("google_sheet_fields") or {}
    field_map = {
        "Конкурент":          ACCOUNT,
        "Ссылка на пост":     stage5a2b_post.get("permalink") or "",
        "Позиция закрепа":    str(stage5a2b_post.get("position") or ""),
        "Тема поста":         gf.get("Тема поста") or "",
        "Почему закреплен":   gf.get("Почему закреплен") or "",
        "Хук / первый экран": "",   # never filled in this stage
        "Что в тексте поста": gf.get("Что в тексте поста") or "",
        "Ключевые смыслы":    gf.get("Ключевые смыслы") or "",
        "Какой CTA":          gf.get("Какой CTA") or "",
        "Куда ведет CTA":     gf.get("Куда ведет CTA") or "",
        "Роль в воронке":     gf.get("Роль в воронке") or "",
    }
    return [str(field_map.get(h, "") or "") for h in headers]


# ── Full output builder ────────────────────────────────────────────────────

def build_full_output(
    semantic_posts: list[dict],
    stage5a2b_posts: list[dict],
    model: str,
    total_tokens: int,
    total_cost: float,
) -> dict:
    run_ts = datetime.now(timezone.utc).isoformat()
    n_cache_hits = sum(1 for p in semantic_posts if p.get("cache_status") == "hit")
    n_new        = sum(1 for p in semantic_posts if p.get("cache_status") == "miss")
    n_failed     = sum(1 for p in semantic_posts if p.get("openai_status") not in ("analyzed", None))

    return {
        "account":        ACCOUNT,
        "stage":          "stage5a2c",
        "run_timestamp":  run_ts,
        "model":          model,
        "prompt_version": PROMPT_VERSION,
        "total_posts":    len(semantic_posts),
        "source":         "caption_only",
        "visual_analyzed": False,
        "ocr_analyzed":    False,
        "cache_summary": {
            "hits":     n_cache_hits,
            "new":      n_new,
            "failed":   n_failed,
        },
        "total_tokens_used": total_tokens,
        "estimated_cost_usd": round(total_cost, 4),
        "posts": semantic_posts,
    }


def build_gs_rows_output(
    semantic_posts: list[dict],
    stage5a2b_posts: list[dict],
    headers: list[str] = None,
) -> dict:
    if headers is None:
        headers = GS_FIELD_ORDER

    posts_by_pos = {p.get("position"): p for p in stage5a2b_posts}
    rows = []
    rows_as_dicts = []
    for sem in semantic_posts:
        pos   = sem.get("position")
        a2b   = posts_by_pos.get(pos, {})
        row   = build_gs_row(sem, a2b, headers)
        rows.append(row)
        rows_as_dicts.append(dict(zip(headers, row)))

    return {
        "sheet":         "Закрепленные посты",
        "stage":         "stage5a2c",
        "generated_at":  datetime.now(timezone.utc).isoformat(),
        "headers":       headers,
        "rows":          rows,
        "rows_as_dicts": rows_as_dicts,
        "integration_note": (
            "Next integration step: Stage 5D-1.1 — update Stage 5D-1 exporter to prefer "
            "stage5a2c_pinned_posts_google_sheet_rows.json for semantic fields in "
            "'Закрепленные посты'. After that, Stage 5D-3 can rewrite only that sheet."
        ),
    }


# ── Validation ─────────────────────────────────────────────────────────────

def validate_inputs(stage5a2b: dict) -> list[str]:
    errors = []
    posts  = stage5a2b.get("posts") or []
    if len(posts) == 0:
        errors.append("No posts in stage5a2b output")
        return errors
    if len(posts) != EXPECTED_POSTS:
        errors.append(f"Expected {EXPECTED_POSTS} posts, got {len(posts)}")
    for p in posts:
        if not p.get("full_caption") and not p.get("caption_for_analysis"):
            errors.append(f"Post {p.get('position')}: lacks full_caption")
    return errors


def validate_output(output: dict) -> list[str]:
    errors = []
    posts  = output.get("posts") or []

    if len(posts) < EXPECTED_POSTS:
        errors.append(f"Output has only {len(posts)} posts, expected {EXPECTED_POSTS}")

    for sem in posts:
        gf = sem.get("google_sheet_fields") or {}
        for key in GS_FIELD_ORDER:
            if key in ("Конкурент", "Ссылка на пост", "Позиция закрепа"):
                continue
            if key not in gf:
                errors.append(f"Post {sem.get('position')}: missing google_sheet_field '{key}'")

        if gf.get("Хук / первый экран", "") != "":
            errors.append(f"Post {sem.get('position')}: 'Хук / первый экран' must be empty")

        if sem.get("visual_analyzed") is True:
            errors.append(f"Post {sem.get('position')}: visual_analyzed=True — this stage is caption-only")
        if sem.get("ocr_analyzed") is True:
            errors.append(f"Post {sem.get('position')}: ocr_analyzed=True — this stage is caption-only")

        rv = gf.get("Роль в воронке", "")
        if rv:
            tokens = [t.strip() for t in rv.replace(",", "/").split("/") if t.strip()]
            for t in tokens:
                if t not in ALLOWED_FUNNEL_ROLES:
                    errors.append(f"Post {sem.get('position')}: Роль в воронке has invalid value '{t}'")

        for field, limit in CELL_LIMITS.items():
            if limit == 0:
                continue
            val = gf.get(field, "")
            if val and len(val) > limit:
                errors.append(f"Post {sem.get('position')}: {field} exceeds {limit} chars ({len(val)})")

    return errors


# ── Main run entry points ─────────────────────────────────────────────────

def load_stage5a2b() -> tuple[dict, list[str]]:
    errors = []
    if not STAGE5A2B_PATH.exists():
        errors.append(f"stage5a2b_pinned_posts_details.json not found at {STAGE5A2B_PATH}")
        return {}, errors
    try:
        data = json.loads(STAGE5A2B_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse stage5a2b output: {e}")
        return {}, errors
    return data, errors


def run_analysis(
    client,
    stage5a2b: dict,
    model: str = DEFAULT_MODEL,
    budget_usd: float = 1.0,
    force: bool = False,
) -> dict:
    """Run OpenAI caption analysis on 3 posts. Returns full semantic output."""
    posts = stage5a2b.get("posts") or []
    errs  = validate_inputs(stage5a2b)
    if errs:
        raise ValueError("\n".join(errs))

    cost_estimate = COST_PER_CALL.get(model, 0.001)
    total_estimated = cost_estimate * len(posts)
    if total_estimated > budget_usd:
        raise ValueError(
            f"Estimated cost ${total_estimated:.4f} exceeds budget ${budget_usd:.2f}. "
            "Increase --budget-max-usd or reduce scope."
        )

    semantic_posts = []
    total_tokens   = 0
    total_cost     = 0.0

    for post in posts:
        pos = post.get("position")
        print(f"  Analyzing post {pos} (caption {post.get('caption_length', 0)} chars) ...")

        result = analyze_post_caption(client, post, model=model, force=force)
        sem    = build_semantic_post(post, result)
        semantic_posts.append(sem)

        used = result.get("tokens_used") or 0
        total_tokens += used
        if not result.get("from_cache"):
            total_cost += cost_estimate

        status = result.get("status")
        cache_note = " [cache hit]" if result.get("from_cache") else ""
        if status == "analyzed":
            print(f"    OK{cache_note} — {used} tokens")
        else:
            print(f"    FAILED: {result.get('error', status)}")

    output = build_full_output(semantic_posts, posts, model, total_tokens, total_cost)

    # Validate
    val_errors = validate_output(output)
    if val_errors:
        raise ValueError("Output validation failed:\n" + "\n".join(val_errors))

    # Save
    NORM_DIR.mkdir(parents=True, exist_ok=True)
    SEMANTIC_OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Semantic output: {SEMANTIC_OUTPUT_PATH.relative_to(BASE)}")

    # Google Sheets rows
    gs_rows = build_gs_rows_output(semantic_posts, posts)
    GS_ROWS_OUTPUT_PATH.write_text(
        json.dumps(gs_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  GS rows output: {GS_ROWS_OUTPUT_PATH.relative_to(BASE)}")

    return output
