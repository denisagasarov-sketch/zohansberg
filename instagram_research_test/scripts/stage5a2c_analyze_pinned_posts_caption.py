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
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT  = _args.account
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"
CACHE_DIR = BASE / "analysis" / "stage5a2c_cache"

STAGE5A2B_PATH = NORM_DIR / "stage5a2b_pinned_posts_details.json"

SEMANTIC_OUTPUT_PATH  = NORM_DIR / "stage5a2c_pinned_posts_semantic.json"
GS_ROWS_OUTPUT_PATH   = NORM_DIR / "stage5a2c_pinned_posts_google_sheet_rows.json"
SEMANTIC_FIXED_PATH   = NORM_DIR / "stage5a2c_pinned_posts_semantic_fixed.json"
GS_ROWS_FIXED_PATH    = NORM_DIR / "stage5a2c_pinned_posts_google_sheet_rows_fixed.json"
EXPECTED_POSTS  = 3
PROMPT_VERSION  = "v2"           # bumped for quality fix
DEFAULT_MODEL   = "gpt-4o-mini"

# Conservative cost estimate per call (~1500 input + ~300 output tokens)
COST_PER_CALL: dict[str, float] = {
    "gpt-4o-mini": 0.0004,
    "gpt-4o":      0.008,
}

# ── Field constraints ──────────────────────────────────────────────────────

CELL_LIMITS = {
    "Тема поста":            160,
    "Почему закреплен":      250,
    "Хук / первый экран": 250,
    "Что в тексте поста":    350,
    "Ключевые смыслы":       500,
    "Какой CTA":             180,
    "Куда ведет CTA":        180,
    "Роль в воронке":        80,
}

ALLOWED_FUNNEL_ROLES = {
    "знакомство", "доверие", "прогрев", "продажа", "лидогенерация",
}

# Kept for backward compat; atom-level validation uses ALLOWED_DESTINATION_ATOMS
ALLOWED_CTA_DESTINATIONS = {
    "директ", "комментарии", "био-ссылка", "анкета", "анкета предзаписи",
    "закрытый канал", "консультация", "курс", "сайт", "бот", "unknown",
}

ALLOWED_DESTINATION_ATOMS = ALLOWED_CTA_DESTINATIONS  # same set

# Semantic classification for smart composite-path splitting
_DEST_CHANNELS  = {"директ", "комментарии", "био-ссылка", "бот"}
_DEST_ENDPOINTS = {
    "анкета", "анкета предзаписи", "закрытый канал",
    "консультация", "курс", "сайт", "unknown",
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

# ── CTA detection regexes ──────────────────────────────────────────────────

# Strong imperative action verbs that constitute a real CTA
_STRONG_VERBS_RE = re.compile(
    r"\b(?:"
    r"пишите|напишите|оставьте|переходите|перейдите|заполните|"
    r"регистрируйтесь|зарегистрируйтесь|отправьте|забронируйте|"
    r"подпишитесь|нажмите|жмите|запишитесь|приходите|кликните|"
    r"получите\s+доступ"
    r")\b",
    re.IGNORECASE,
)

# Weak imperative forms that are NOT strong CTA verbs (excluded from general check)
_WEAK_IMPERATIVES = {
    "получите", "узнайте", "читайте", "смотрите", "следите",
    "ждите", "скажите", "думайте", "знайте",
}

# Patterns that indicate the text is a thesis/forecast/teaser, not a CTA
_INVALID_CTA_STARTERS_RE = re.compile(
    r"^(?:спойлер|как\s+|что\s+|почему\s+|когда\s+|зачем\s+|в\s+20\d{2}\s+|\d{4}\s+год)",
    re.IGNORECASE,
)

# ── Prompts ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Ты аналитик конкурентного Instagram-контента.
Тебе дают полный текст (caption) закрепленного поста.
Проанализируй ТОЛЬКО текст. Не домысливай из картинок или видео.
Верни ТОЛЬКО JSON-объект — без markdown, без пояснений, только JSON.
Все текстовые значения — на русском языке.

━━━ ПРАВИЛА CTA ━━━
CTA (призыв к действию) — это только явный призыв к действию, когда текст просит читателя что-то СДЕЛАТЬ.

ВАЛИДНЫЙ CTA содержит глагол-действие: пишите, напишите, оставьте заявку,
переходите, заполните, регистрируйтесь, нажмите, запишитесь и т.п.

Примеры ВАЛИДНОГО CTA:
  - "пишите «АНКЕТА» в директ и комментарии"
  - "оставьте заявку на консультацию"
  - "переходите по ссылке в био"
  - "заполните анкету"
  - "напишите слово «консультация» в комментариях"

НЕ является CTA:
  - тезис, инсайт, прогноз, спойлер, тема, вопрос, обещание
  - "Спойлер: в 2026 году..."
  - "как прогнозировать результаты"
  - "что изменится в маркетинге"
  - "почему большинство это проспит"

Если явного призыва к действию нет — "Какой CTA" и "Куда ведет CTA" = "".

ВАЖНО: CTA может также находиться в первом закреплённом комментарии автора под постом.
Если в тексте нет явного CTA, но есть намёк (например, "подробности в комментариях") —
отметь в evidence.source_notes: "возможно, CTA закреплён в первом комментарии".

━━━ ПРАВИЛА "Ключевые смыслы" ━━━
Раскладывай по структуре: боль → узнавание → причина → оффер → соцдоки → CTA.
Пропускай элементы, которых нет в тексте. Каждый элемент — 1 короткая фраза.
Пример: "боль: нет клиентов; причина: неверный контент; оффер: курс по SMM; CTA: заявка в директ."

━━━ ПРАВИЛА "Хук / первый экран" ━━━
Дословная цитата первой строки или первого абзаца caption — то, что читатель видит до "ещё".
Включай эмодзи, если с них начинается текст. Макс 250 символов.
Пример: "🔥 Как я сделал 500 заявок за месяц без бюджета"

━━━ ПРАВИЛА "Почему закреплен" ━━━
Обязательно начни с "Вероятно". Будь конкретным — ссылайся на содержание
caption. Объясни стратегическую задачу закрепа (прогрев, доверие, вход в воронку и т.п.).

ПЛОХО (общее): "чтобы привлечь внимание", "чтобы рассказать о курсе"
ХОРОШО (конкретное): "Вероятно, закреплен как экспертный прогрев: показывает
метод работы, прогнозирование результата и закрывает возражение про гарантии."

━━━ ПРАВИЛА составных путей ━━━
"Куда ведет CTA" может быть составным. Используй → для шагов, / для параллельных каналов.
Например: "директ / комментарии → анкета предзаписи → закрытый канал"

Допустимые атомы: директ | комментарии | био-ссылка | анкета | анкета предзаписи |
закрытый канал | консультация | курс | сайт | бот | unknown

━━━ ПРАВИЛА "Роль в воронке" ━━━
Допустимые значения: знакомство | доверие | прогрев | продажа | лидогенерация
Составные роли разрешены через /: "доверие / прогрев", "доверие / лидогенерация"
Используй только перечисленные атомы."""


def build_user_prompt(post: dict) -> str:
    caption      = post.get("full_caption") or post.get("caption_for_analysis") or ""
    position     = post.get("position", "?")
    media_type   = post.get("media_type") or "неизвестно"
    caption_len  = post.get("caption_length", len(caption))
    permalink    = post.get("permalink") or ""

    funnel_roles_str = " | ".join(sorted(ALLOWED_FUNNEL_ROLES))
    cta_dest_str     = " | ".join(sorted(ALLOWED_DESTINATION_ATOMS))

    return f"""\
Закрепленный пост Instagram #{position}.
Тип поста: {media_type}. Длина caption: {caption_len} символов.
Permalink: {permalink}

=== CAPTION ===
{caption}
=== END CAPTION ===

Верни JSON по схеме ниже. Пустая строка "" = поле не поддерживается текстом.

{{
  "Тема поста": "<одна строка, макс 160 символов>",
  "Почему закреплен": "<ОБЯЗАТЕЛЬНО начни с 'Вероятно': конкретный инференс со ссылкой на содержание caption, макс 250 символов>",
  "Хук / первый экран": "<дословная цитата первой строки caption до 'ещё', включая эмодзи, макс 250 символов>",
  "Что в тексте поста": "<краткая структура текста поста, макс 350 символов>",
  "Ключевые смыслы": "<структура: боль → узнавание → причина → оффер → соцдоки → CTA; пропусти отсутствующие; макс 500 символов>",
  "Какой CTA": "<ТОЛЬКО явный призыв к действию из текста или '' — НЕ тезис, НЕ спойлер, макс 180 символов>",
  "Куда ведет CTA": "<допустимые атомы: {cta_dest_str}; составной путь: 'директ / комментарии → анкета предзаписи'; '' если CTA нет>",
  "Роль в воронке": "<одно или несколько из: {funnel_roles_str}; несколько через /, напр. 'доверие / прогрев'>",
  "confidence": {{
    "Тема поста": "high | medium | low",
    "Почему закреплен": "high | medium | low",
    "Хук / первый экран": "high | medium | low",
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
  "limitations": ["<что нельзя определить из текста — кратко>"]
}}

ВАЖНО:
- "Почему закреплен" — всегда инференс, не факт. Начни с "Вероятно". Будь конкретным.
- "Хук / первый экран" — точная цитата из caption, не пересказ.
- "Ключевые смыслы" — структура боль→узнавание→причина→оффер→соцдоки→CTA.
- "Роль в воронке" — только из списка: {funnel_roles_str}; составные разрешены
- "Куда ведет CTA" — только из атомов: {cta_dest_str}; или ""
- "Какой CTA" — только если есть явный глагол-действие в тексте; иначе ""
- Если CTA нет — "Куда ведет CTA" тоже ""
- Не придумывай смыслы, которых нет в тексте"""


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


# ── CTA helpers ────────────────────────────────────────────────────────────

def _is_valid_cta(cta: str) -> bool:
    """
    Return True if cta contains an explicit action instruction.
    Empty string is valid (means no CTA was found — acceptable).
    """
    if not cta or not cta.strip():
        return True   # empty = no CTA declared; caller handles empty separately

    text = cta.strip()

    # Thesis/teaser/forecast starters → definitely not a CTA
    if _INVALID_CTA_STARTERS_RE.match(text):
        return False

    # Strong imperative action verb present → valid CTA
    if _STRONG_VERBS_RE.search(text):
        return True

    # Any non-weak imperative form (-те/-ите/-йте) + channel/destination marker → valid
    imperative_re = re.compile(r"\b\w+(?:те|ите|йте)\b", re.IGNORECASE)
    channel_markers_re = re.compile(
        r"\b(?:директ|комментари|ссылку?|био|анкет|форму?|консультаци|канал|боту?|сайт|курс)\b",
        re.IGNORECASE,
    )
    if imperative_re.search(text) and channel_markers_re.search(text):
        all_imps = [m.lower() for m in imperative_re.findall(text)]
        strong_imps = [m for m in all_imps if m not in _WEAK_IMPERATIVES]
        if strong_imps:
            return True

    return False


def _normalize_cta_destination(value: str) -> tuple[str, list[str]]:
    """
    Normalize a CTA destination string, allowing composite paths.

    Parallel channels separated by / (e.g. "директ / комментарии").
    Sequential steps separated by → (e.g. "анкета предзаписи → закрытый канал").
    Mixed input with | or -> is normalized automatically.
    Channels and endpoints in the same chunk are smart-split on → boundary.

    Returns (normalized_string, warnings).
    """
    if not value or not value.strip():
        return "", []

    warns: list[str] = []
    v = value.strip()

    # Normalize explicit arrow variants to sentinel \x00
    v = re.sub(r"\s*→\s*", "\x00", v)       # Unicode arrow
    v = re.sub(r"\s*(?:->|=>)\s*", "\x00", v)  # ASCII arrows
    # Normalize parallel separators to sentinel \x01
    v = re.sub(r"\s*\|\s*", "\x01", v)
    v = re.sub(r"\s*/\s*", "\x01", v)
    v = re.sub(r"\s{2,}", " ", v)

    sequential_chunks = [c for c in v.split("\x00") if c.strip()]
    result_parts: list[str] = []

    for chunk in sequential_chunks:
        raw_atoms = [a.strip().lower() for a in chunk.split("\x01") if a.strip()]
        valid_atoms: list[str] = []
        for atom in raw_atoms:
            if atom in ALLOWED_DESTINATION_ATOMS:
                valid_atoms.append(atom)
            else:
                warns.append(f"Куда ведет CTA: unknown atom '{atom}' removed")

        if not valid_atoms:
            continue

        channels  = [a for a in valid_atoms if a in _DEST_CHANNELS]
        endpoints = [a for a in valid_atoms if a in _DEST_ENDPOINTS]

        if channels and endpoints:
            # Channels lead to endpoints — insert implicit sequential boundary
            result_parts.append(" / ".join(channels))
            result_parts.append(" / ".join(endpoints))
        else:
            result_parts.append(" / ".join(valid_atoms))

    result = " → ".join(result_parts)
    if not result and value.strip():
        warns.append("Куда ведет CTA: all atoms were invalid; cleared")
    return result, warns


def _extract_destination_atoms(value: str) -> list[str]:
    """Split a (possibly composite) destination path into individual atoms."""
    if not value:
        return []
    parts = re.split(r"[→/]", value)
    return [p.strip().lower() for p in parts if p.strip()]


def _normalize_funnel_role(value: str) -> tuple[str, list[str]]:
    """
    Validate and normalize a funnel role string.
    Composite roles (e.g. "доверие / прогрев") are allowed.
    Returns (normalized_string, warnings).
    """
    if not value or not value.strip():
        return "", []

    warns: list[str] = []
    tokens = [t.strip().lower() for t in re.split(r"[/,]", value) if t.strip()]
    valid_tokens: list[str] = []
    for t in tokens:
        if t in ALLOWED_FUNNEL_ROLES:
            valid_tokens.append(t)
        else:
            warns.append(f"Роль в воронке: unexpected value '{t}' removed")

    result = " / ".join(valid_tokens)
    return result, warns


# ── Trust + leadgen detection & rule ─────────────────────────────────────

# Ordered list for role output — preserves canonical funnel order
_FUNNEL_ORDER = ["знакомство", "доверие", "прогрев", "продажа", "лидогенерация"]

# Trust proof signals: distinct evidence categories
_TRUST_CAT_PATTERNS = [
    # 1. Experience (years of work)
    re.compile(r"\b\d+\+?\s*лет\b|\bлет\s+опыта\b", re.IGNORECASE),
    # 2. Scale numbers (N+ projects/clients/cases)
    re.compile(r"\b\d+\+\s*(?:проект|кейс|клиент)\w*", re.IGNORECASE),
    # 3. Entity (agency/team/company)
    re.compile(r"\bагентств\w+\b|\bкоманд[аы]\b|\bкомпани[яи]\b", re.IGNORECASE),
    # 4. Clients mentioned as evidence
    re.compile(r"\b(?:наших?|наши)\s+клиент\w*|\bсреди\s+клиент\w*|\bклиент(?:ов|ы|ам|ах)\b", re.IGNORECASE),
    # 5. Cases / portfolio
    re.compile(r"\bкейс(?:ов|ы)?\b|\bпортфолио\b", re.IGNORECASE),
    # 6. Services list
    re.compile(r"\bуслуг[иа]\b", re.IGNORECASE),
    # 7. Geographic reach / markets
    re.compile(r"\b(?:ЕС|СНГ|Европ\w+)\b|\bрынк(?:и|ов|ах)?\b", re.IGNORECASE),
]

# Leadgen / action signals: explicit conversion path
_LEADGEN_ACTION_RE = re.compile(
    r"\b(?:"
    r"консультаци[яи]|заявк[аи]|анкет[аы]|предзапись|предзаписи|"
    r"пишите|напишите|оставьте|заполните|запишитесь|нажмите|"
    r"директ|комментари\w*|кодовое\s+слово|"
    r"расчет\s+стоимости|получить\s+расчет|"
    r"закрытый\s+канал|закрытый\s+чат"
    r")\b",
    re.IGNORECASE,
)

# Patterns for "Почему закреплен" — prefix-based (no trailing \b; Cyrillic inflected forms)
_PZ_TRUST_RE = re.compile(
    r"\b(?:доверие|доверия|опыт\w*|клиент\w*|проект\w*|кейс\w*|компетент\w*|"
    r"доказательств\w*|эксперт\w*|агентств\w*)",
    re.IGNORECASE,
)
_PZ_LEADGEN_RE = re.compile(
    r"\b(?:лидогенераци\w*|консультаци\w*|заявк\w*|анкет\w*|запис\w+|воронк\w*|лидген\w*)",
    re.IGNORECASE,
)


def _count_trust_categories(caption: str) -> int:
    """Return number of distinct trust proof signal categories present in caption."""
    return sum(1 for pat in _TRUST_CAT_PATTERNS if pat.search(caption))


def _has_trust_proof(caption: str) -> bool:
    """True if caption has 2+ distinct trust proof signal categories."""
    return _count_trust_categories(caption) >= 2


def _has_leadgen_action(caption: str) -> bool:
    """True if caption has at least one explicit leadgen/action signal."""
    return bool(_LEADGEN_ACTION_RE.search(caption))


def _build_trust_leadgen_pz(caption: str, cta_dest: str) -> str:
    """Build a specific 'Почему закреплен' that references trust proof + leadgen task."""
    ev_parts: list[str] = []

    # Experience
    exp_m = re.search(r"\b(\d+\+?\s*лет(?:\s+опыта)?)\b", caption, re.IGNORECASE)
    if exp_m:
        ev_parts.append(exp_m.group(1).strip().lower())

    # Scale (N+ items)
    scale_m = re.search(r"\b(\d+\+\s*(?:проект|кейс|клиент)\w*)\b", caption, re.IGNORECASE)
    if scale_m:
        ev_parts.append(scale_m.group(1).strip().lower())

    # Entity
    if re.search(r"\bагентств\w+\b|\bкоманд[аы]\b", caption, re.IGNORECASE):
        ev_parts.append("агентство/команда")

    # Services
    if re.search(r"\bуслуг[иа]\b", caption, re.IGNORECASE):
        ev_parts.append("список услуг")

    # Clients (if no scale already captured)
    if not scale_m and re.search(r"\bклиент(?:ов|ы|ам)?\b", caption, re.IGNORECASE):
        ev_parts.append("клиентов")

    # CTA destination type
    cta_label = "консультацию"
    if "консультация" in cta_dest or re.search(r"\bконсультаци\w+\b", caption, re.IGNORECASE):
        cta_label = "консультацию"
    elif "анкета" in cta_dest or re.search(r"\bанкет\w+\b", caption, re.IGNORECASE):
        cta_label = "анкету"
    elif re.search(r"\bзаявк\w+\b", caption, re.IGNORECASE):
        cta_label = "заявку"

    ev_str = ", ".join(ev_parts[:3]) if ev_parts else "опыт, клиентов и услуги"
    result = (
        f"Вероятно, закреплен для доверия и лидогенерации: "
        f"показывает {ev_str} и ведет к {cta_label}."
    )
    return result[:250] if len(result) > 250 else result


def _apply_trust_leadgen_rule(
    fixed: dict,
    caption: str,
    pp_notes: list[dict],
    warns: list[str],
) -> None:
    """
    If caption has trust proof signals (2+ categories) AND leadgen/action signals,
    ensure Роль в воронке includes both 'доверие' and 'лидогенерация'.
    Also updates 'Почему закреплен' if it doesn't already mention both.
    Mutates fixed, pp_notes, warns in place.
    """
    if not caption:
        return
    if not (_has_trust_proof(caption) and _has_leadgen_action(caption)):
        return

    # ── 1. Role ──────────────────────────────────────────────────────────
    rv = fixed.get("Роль в воронке", "")
    existing_tokens = {t.strip().lower() for t in re.split(r"[/,]", rv) if t.strip()} if rv else set()
    required = {"доверие", "лидогенерация"}
    missing  = required - existing_tokens

    if missing:
        orig_rv = rv
        merged  = existing_tokens | required
        # Keep only valid atoms; preserve canonical funnel order
        new_rv  = " / ".join(t for t in _FUNNEL_ORDER if t in merged)
        fixed["Роль в воронке"] = new_rv
        warns.append(
            f"Роль в воронке: added {sorted(missing)} — caption has trust proof signals + leadgen CTA"
        )
        pp_notes.append({
            "field": "Роль в воронке",
            "original_value": orig_rv,
            "final_value": new_rv,
            "reason": "Caption contains both trust proof signals and explicit leadgen CTA",
        })

    # ── 2. Почему закреплен ───────────────────────────────────────────────
    pz = fixed.get("Почему закреплен", "")
    pz_has_trust   = bool(_PZ_TRUST_RE.search(pz))
    pz_has_leadgen = bool(_PZ_LEADGEN_RE.search(pz))

    if not (pz_has_trust and pz_has_leadgen):
        orig_pz = pz
        cta_dest = fixed.get("Куда ведет CTA", "") or ""
        new_pz   = _build_trust_leadgen_pz(caption, cta_dest)
        fixed["Почему закреплен"] = new_pz
        warns.append("Почему закреплен: updated to reflect both trust proof and leadgen task")
        pp_notes.append({
            "field": "Почему закреплен",
            "original_value": orig_pz,
            "final_value": new_pz,
            "reason": "Pinned role includes both trust proof and leadgen path",
        })

def _validate_and_fix(
    raw: dict, post: dict
) -> tuple[dict, list[str], list[dict]]:
    """
    Validate OpenAI response, apply cell limits, enforce all constraints.
    Returns (fixed_dict, validation_warnings, postprocessing_notes).
    """
    warns:    list[str]  = []
    pp_notes: list[dict] = []
    fixed = dict(raw)

    # 1. "Почему закреплен" inference prefix
    pz = fixed.get("Почему закреплен", "")
    if pz and not re.match(
        r"^(Вероятно|Возможно|По всей видимости|Скорее всего)", pz, re.IGNORECASE
    ):
        orig = pz
        fixed["Почему закреплен"] = "Вероятно, " + pz
        warns.append("Почему закреплен: prepended 'Вероятно, ' — was missing inference marker")
        pp_notes.append({
            "field": "Почему закреплен",
            "original_value": orig,
            "final_value": fixed["Почему закреплен"],
            "reason": "Missing inference prefix; auto-prepended",
        })

    # 2. CTA validity check
    cta = fixed.get("Какой CTA", "")
    if cta and not _is_valid_cta(cta):
        orig_cta  = cta
        orig_dest = fixed.get("Куда ведет CTA", "")
        fixed["Какой CTA"]    = ""
        fixed["Куда ведет CTA"] = ""
        conf = fixed.setdefault("confidence", {})
        conf["Какой CTA"]    = "low"
        conf["Куда ведет CTA"] = "low"
        warns.append("Какой CTA: explicit CTA not found; cleared")
        if orig_dest:
            warns.append("Куда ведет CTA: cleared because CTA was invalid")
        pp_notes.append({
            "field": "Какой CTA",
            "original_value": orig_cta,
            "final_value": "",
            "reason": "No explicit action instruction (imperative verb) found",
        })
        if orig_dest:
            pp_notes.append({
                "field": "Куда ведет CTA",
                "original_value": orig_dest,
                "final_value": "",
                "reason": "Cleared because CTA was invalid",
            })

    # 3. CTA destination handling
    cta_now = fixed.get("Какой CTA", "")
    if cta_now:
        # CTA is valid and present — normalize destination
        dest = fixed.get("Куда ведет CTA", "")
        normalized_dest, dest_warns = _normalize_cta_destination(dest)
        if dest_warns:
            warns.extend(dest_warns)
        if normalized_dest != dest:
            orig_dest = dest
            fixed["Куда ведет CTA"] = normalized_dest
            pp_notes.append({
                "field": "Куда ведет CTA",
                "original_value": orig_dest,
                "final_value": normalized_dest,
                "reason": "Normalized composite destination path",
            })
    else:
        # No CTA → destination must be empty
        dest_val = fixed.get("Куда ведет CTA", "")
        if dest_val:
            fixed["Куда ведет CTA"] = ""
            warns.append("Куда ведет CTA: cleared because CTA is empty")
            pp_notes.append({
                "field": "Куда ведет CTA",
                "original_value": dest_val,
                "final_value": "",
                "reason": "CTA is empty; destination must also be empty",
            })

    # 4. Funnel role normalization (allow composite)
    rv = fixed.get("Роль в воронке", "")
    if rv:
        normalized_rv, role_warns = _normalize_funnel_role(rv)
        if role_warns:
            warns.extend(role_warns)
        if normalized_rv != rv:
            orig_rv = rv
            fixed["Роль в воронке"] = normalized_rv
            if not normalized_rv:
                pp_notes.append({
                    "field": "Роль в воронке",
                    "original_value": orig_rv,
                    "final_value": "",
                    "reason": "All role atoms were invalid",
                })
            else:
                pp_notes.append({
                    "field": "Роль в воронке",
                    "original_value": orig_rv,
                    "final_value": normalized_rv,
                    "reason": "Normalized composite role",
                })

    # 4.5. Trust + leadgen rule
    _caption = post.get("full_caption") or post.get("caption_for_analysis") or ""
    _apply_trust_leadgen_rule(fixed, _caption, pp_notes, warns)

    # 6. Cell length enforcement
    for field, limit in CELL_LIMITS.items():
        if limit == 0:
            continue
        val = fixed.get(field, "")
        if isinstance(val, str) and len(val) > limit:
            orig_val = val
            fixed[field] = val[:limit]
            warns.append(f"{field}: truncated to {limit} chars")
            pp_notes.append({
                "field": field,
                "original_value": orig_val,
                "final_value": fixed[field],
                "reason": f"Exceeded cell limit ({limit} chars)",
            })

    # 7. Low-confidence note (informational only, no clearing)
    conf = fixed.get("confidence", {})
    for field in ["Ключевые смыслы", "Роль в воронке"]:
        if conf.get(field) == "low" and fixed.get(field):
            warns.append(f"{field}: confidence=low; keeping value but noting uncertainty")

    # 8. Ensure required keys present
    required = list(CELL_LIMITS.keys())
    for k in required:
        if k not in fixed:
            fixed[k] = ""
            warns.append(f"{k}: missing from OpenAI response; set to empty")

    # 9. Ensure confidence dict is complete
    if "confidence" not in fixed:
        fixed["confidence"] = {}
    for field in CELL_LIMITS:
        if field not in fixed["confidence"]:
            fixed["confidence"][field] = "low"
            warns.append(f"confidence[{field}]: missing; set to low")

    # 10. Contradiction check: sale/leadgen role but no CTA
    rv_final  = fixed.get("Роль в воронке", "")
    cta_final = fixed.get("Какой CTA", "")
    role_atoms = {t.strip().lower() for t in re.split(r"[/,]", rv_final) if t.strip()}
    if role_atoms & {"продажа", "лидогенерация"} and not cta_final:
        warns.append(
            "Противоречие: роль продажа/лидогенерация но CTA не найден — проверить вручную"
        )

    return fixed, warns, pp_notes


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
        "status":           None,
        "post_id":          post_id,
        "position":         position,
        "model":            model,
        "prompt_version":   PROMPT_VERSION,
        "tokens_used":      None,
        "from_cache":       False,
        "postprocessing_notes": [],
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
        return {**base_result, "status": "openai_error", "error": str(exc)}

    # Parse JSON
    try:
        analysis = json.loads(raw_content)
    except Exception:
        # Repair retry
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
                "status":      "json_parse_failed",
                "error":       f"JSON parse failed after repair: {exc2}",
                "raw_content": raw_content,
            }

    validated, val_warns, pp_notes = _validate_and_fix(analysis, post)
    result = {
        **base_result,
        "status":               "analyzed",
        "analysis":             validated,
        "validation_warnings":  val_warns,
        "postprocessing_notes": pp_notes,
        "tokens_used":          tokens_used,
        "from_cache":           False,
    }
    save_to_cache(result, post_id, caption, model)
    return result


# ── Semantic output builder ────────────────────────────────────────────────

def build_semantic_post(post: dict, openai_result: dict) -> dict:
    """Merge post metadata with OpenAI analysis into per-post semantic structure."""
    status     = openai_result.get("status")
    analysis   = openai_result.get("analysis") or {}
    from_cache = openai_result.get("from_cache", False)

    cache_status = "hit" if from_cache else ("miss" if status == "analyzed" else "failed")

    gs_fields = {
        "Тема поста":                     analysis.get("Тема поста", ""),
        "Почему закреплен":               analysis.get("Почему закреплен", ""),
        "Хук / первый экран": analysis.get("Хук / первый экран", ""),
        "Что в тексте поста":             analysis.get("Что в тексте поста", ""),
        "Ключевые смыслы":                analysis.get("Ключевые смыслы", ""),
        "Какой CTA":                      analysis.get("Какой CTA", ""),
        "Куда ведет CTA":                 analysis.get("Куда ведет CTA", ""),
        "Роль в воронке":                 analysis.get("Роль в воронке", ""),
    }

    confidence = analysis.get("confidence", {})

    base_limitations = [
        "Caption-only analysis. Cover image, carousel slides, and OCR were not analyzed.",
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

        "google_sheet_fields":  gs_fields,
        "confidence":           confidence,
        "evidence":             analysis.get("evidence") or {
            "caption_quotes": [], "cta_quotes": [], "source_notes": []
        },
        "limitations":          limitations,
        "validation_warnings":  openai_result.get("validation_warnings") or [],
        "postprocessing_notes": openai_result.get("postprocessing_notes") or [],
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
        "Тема поста":                     gf.get("Тема поста") or "",
        "Почему закреплен":               gf.get("Почему закреплен") or "",
        "Хук / первый экран": gf.get("Хук / первый экран") or "",
        "Что в тексте поста":             gf.get("Что в тексте поста") or "",
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
    run_ts       = datetime.now(timezone.utc).isoformat()
    n_cache_hits = sum(1 for p in semantic_posts if p.get("cache_status") == "hit")
    n_new        = sum(1 for p in semantic_posts if p.get("cache_status") == "miss")
    n_failed     = sum(1 for p in semantic_posts if p.get("openai_status") not in ("analyzed",))

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
            "hits":   n_cache_hits,
            "new":    n_new,
            "failed": n_failed,
        },
        "total_tokens_used":  total_tokens,
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
    rows: list[list[str]]  = []
    rows_as_dicts: list[dict] = []
    for sem in semantic_posts:
        pos  = sem.get("position")
        a2b  = posts_by_pos.get(pos, {})
        row  = build_gs_row(sem, a2b, headers)
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
    if len(posts) == 0:
        errors.append("No posts found after empty check (duplicate guard)")
    elif len(posts) != EXPECTED_POSTS:
        pass  # accounts may have fewer than 3 pinned posts — not fatal
    for p in posts:
        if not p.get("full_caption") and not p.get("caption_for_analysis"):
            errors.append(f"Post {p.get('position')}: lacks full_caption")
    return errors


def validate_output(output: dict) -> list[str]:
    errors = []
    posts  = output.get("posts") or []

    if len(posts) == 0:
        errors.append("Output has 0 posts")

    for sem in posts:
        gf  = sem.get("google_sheet_fields") or {}
        pos = sem.get("position")

        # All GS fields must be present
        for key in GS_FIELD_ORDER:
            if key in ("Конкурент", "Ссылка на пост", "Позиция закрепа"):
                continue
            if key not in gf:
                errors.append(f"Post {pos}: missing google_sheet_field '{key}'")

        # No visual/OCR claims
        if sem.get("visual_analyzed") is True:
            errors.append(f"Post {pos}: visual_analyzed=True — this stage is caption-only")
        if sem.get("ocr_analyzed") is True:
            errors.append(f"Post {pos}: ocr_analyzed=True — this stage is caption-only")

        # CTA + destination consistency
        cta  = gf.get("Какой CTA", "")
        dest = gf.get("Куда ведет CTA", "")
        if not cta and dest:
            errors.append(f"Post {pos}: 'Куда ведет CTA' is set but 'Какой CTA' is empty")
        if cta and not _is_valid_cta(cta):
            errors.append(f"Post {pos}: 'Какой CTA' failed validity check: {cta[:60]!r}")

        # Destination atoms
        if dest:
            bad_atoms = [
                a for a in _extract_destination_atoms(dest)
                if a not in ALLOWED_DESTINATION_ATOMS
            ]
            if bad_atoms:
                errors.append(f"Post {pos}: 'Куда ведет CTA' has invalid atoms: {bad_atoms}")

        # Funnel role atoms
        rv = gf.get("Роль в воронке", "")
        if rv:
            tokens = [t.strip().lower() for t in re.split(r"[/,]", rv) if t.strip()]
            bad_tokens = [t for t in tokens if t not in ALLOWED_FUNNEL_ROLES]
            if bad_tokens:
                errors.append(f"Post {pos}: 'Роль в воронке' has invalid atoms: {bad_tokens}")

        # Почему закреплен prefix
        pz = gf.get("Почему закреплен", "")
        if pz and not re.match(r"^(Вероятно|Возможно|По всей видимости|Скорее всего)", pz, re.IGNORECASE):
            errors.append(f"Post {pos}: 'Почему закреплен' must start with inference marker")

        # Cell limits
        for field, limit in CELL_LIMITS.items():
            if limit == 0:
                continue
            val = gf.get(field, "")
            if val and len(val) > limit:
                errors.append(f"Post {pos}: {field} exceeds {limit} chars ({len(val)})")

    return errors


# ── Main run entry points ──────────────────────────────────────────────────

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

    cost_estimate  = COST_PER_CALL.get(model, 0.001)
    total_estimated = cost_estimate * len(posts)
    if total_estimated > budget_usd:
        raise ValueError(
            f"Estimated cost ${total_estimated:.4f} exceeds budget ${budget_usd:.2f}. "
            "Increase --budget-max-usd or reduce scope."
        )

    semantic_posts: list[dict] = []
    total_tokens = 0
    total_cost   = 0.0

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

        status     = result.get("status")
        cache_note = " [cache hit]" if result.get("from_cache") else ""
        pp_count   = len(result.get("postprocessing_notes") or [])
        if status == "analyzed":
            print(f"    OK{cache_note} — {used} tokens, {pp_count} postprocessing fixes")
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

    gs_rows = build_gs_rows_output(semantic_posts, posts)
    GS_ROWS_OUTPUT_PATH.write_text(
        json.dumps(gs_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  GS rows output: {GS_ROWS_OUTPUT_PATH.relative_to(BASE)}")

    return output


# ── Regression checks ──────────────────────────────────────────────────────

def run_regression_checks() -> tuple[int, int, list[str]]:
    """
    Run deterministic regression checks on all validation/normalization logic.
    Returns (passed_count, failed_count, error_messages).
    No external calls. No file I/O.
    """
    passed = 0
    failed = 0
    errors: list[str] = []

    def ok(label: str, cond: bool):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            errors.append(f"FAIL [{label}]")

    def eq(label: str, actual, expected):
        nonlocal passed, failed
        if actual == expected:
            passed += 1
        else:
            failed += 1
            errors.append(f"FAIL [{label}]: expected {expected!r}, got {actual!r}")

    # ── CTA validity ──────────────────────────────────────────────────────
    ok("CTA invalid: спойлер thesis",
       not _is_valid_cta("Спойлер: в 2026 вопрос «а где гарантии?»..."))
    ok("CTA invalid: как прогнозировать",
       not _is_valid_cta("как прогнозировать результаты"))
    ok("CTA invalid: что изменится",
       not _is_valid_cta("что изменится в маркетинге"))
    ok("CTA invalid: почему большинство",
       not _is_valid_cta("почему большинство это проспит"))
    ok("CTA invalid: в 2026 году",
       not _is_valid_cta("в 2026 году этот вопрос станет главным"))
    ok("CTA valid: пишите АНКЕТА в директ",
       _is_valid_cta("пишите «АНКЕТА» в директ и комментарии"))
    ok("CTA valid: Пишите слово консультация",
       _is_valid_cta("Пишите слово «консультация» в комментариях"))
    ok("CTA valid: оставьте заявку",
       _is_valid_cta("оставьте заявку на консультацию"))
    ok("CTA valid: переходите по ссылке в био",
       _is_valid_cta("переходите по ссылке в био"))
    ok("CTA valid: заполните анкету",
       _is_valid_cta("заполните анкету предзаписи"))
    ok("CTA invalid: получите бонусы (no strong verb)",
       not _is_valid_cta("получите бонусы"))
    ok("CTA invalid: получите ссылку на анкету (weak verb only)",
       not _is_valid_cta("получите ссылку на анкету"))
    ok("CTA valid: напишите + получите ссылку (has strong verb)",
       _is_valid_cta("напишите нам в директ и получите ссылку на анкету"))
    ok("CTA empty: always valid",
       _is_valid_cta(""))
    ok("CTA valid: нажмите",
       _is_valid_cta("нажмите кнопку ниже"))
    ok("CTA valid: запишитесь на консультацию",
       _is_valid_cta("запишитесь на бесплатную консультацию"))

    # ── Destination normalization ─────────────────────────────────────────
    n1, _ = _normalize_cta_destination("директ | комментарии | анкета")
    eq("Dest: pipes + mixed → smart split",
       n1, "директ / комментарии → анкета")

    n2, _ = _normalize_cta_destination(
        "директ / комментарии → анкета предзаписи → закрытый канал"
    )
    eq("Dest: explicit multi-step preserved",
       n2, "директ / комментарии → анкета предзаписи → закрытый канал")

    n3, _ = _normalize_cta_destination("комментарии → консультация")
    eq("Dest: simple sequential", n3, "комментарии → консультация")

    n4, warns4 = _normalize_cta_destination("bio-link → site")
    eq("Dest: invalid English atoms cleared", n4, "")
    ok("Dest: invalid atoms produce warnings", len(warns4) > 0)

    n5, _ = _normalize_cta_destination("директ / комментарии → анкета предзаписи")
    eq("Dest: compound atom preserved",
       n5, "директ / комментарии → анкета предзаписи")

    n6, _ = _normalize_cta_destination("директ")
    eq("Dest: single channel atom", n6, "директ")

    n7, _ = _normalize_cta_destination("директ | комментарии")
    eq("Dest: parallel channels only", n7, "директ / комментарии")

    n8, _ = _normalize_cta_destination("анкета предзаписи -> закрытый канал")
    eq("Dest: ASCII arrow normalized",
       n8, "анкета предзаписи → закрытый канал")

    # ── Role normalization ────────────────────────────────────────────────
    r1, _ = _normalize_funnel_role("доверие / прогрев")
    eq("Role: composite доверие/прогрев", r1, "доверие / прогрев")

    r2, _ = _normalize_funnel_role("доверие / лидогенерация")
    eq("Role: composite доверие/лидогенерация", r2, "доверие / лидогенерация")

    r3, _ = _normalize_funnel_role("лидогенерация / продажа")
    eq("Role: composite лидогенерация/продажа", r3, "лидогенерация / продажа")

    r4, rw4 = _normalize_funnel_role("экспертность")
    eq("Role: invalid atom cleared", r4, "")
    ok("Role: invalid atom produces warning", len(rw4) > 0)

    r5, _ = _normalize_funnel_role("доверие / прогрев / лидогенерация")
    eq("Role: triple composite", r5, "доверие / прогрев / лидогенерация")

    r6, _ = _normalize_funnel_role("лидогенерация")
    eq("Role: single valid atom", r6, "лидогенерация")

    r7, _ = _normalize_funnel_role("доверие,прогрев")
    eq("Role: comma separator normalized", r7, "доверие / прогрев")

    # ── Postprocessing (_validate_and_fix) ────────────────────────────────

    # Invalid CTA → cleared, destination cleared
    raw_a = {
        "Какой CTA":    "Спойлер: в 2026 вопрос «а где гарантии?»...",
        "Куда ведет CTA": "директ",
        "Роль в воронке": "доверие / прогрев",
    }
    fa, wa, na = _validate_and_fix(raw_a, {})
    eq("PP: invalid CTA cleared", fa.get("Какой CTA"), "")
    eq("PP: dest cleared when CTA invalid", fa.get("Куда ведет CTA"), "")
    ok("PP: pp_note recorded for invalid CTA",
       any(n["field"] == "Какой CTA" for n in na))
    eq("PP: valid role preserved", fa.get("Роль в воронке"), "доверие / прогрев")

    # Valid CTA with messy destination → normalized
    raw_b = {
        "Какой CTA":    "пишите «АНКЕТА» в директ и комментарии",
        "Куда ведет CTA": "директ | комментарии | анкета предзаписи",
    }
    fb, _, nb = _validate_and_fix(raw_b, {})
    ok("PP: valid CTA preserved", bool(fb.get("Какой CTA")))
    eq("PP: destination normalized",
       fb.get("Куда ведет CTA"),
       "директ / комментарии → анкета предзаписи")

    # Empty CTA → destination must be empty
    raw_c = {"Какой CTA": "", "Куда ведет CTA": "директ"}
    fc, wc, _ = _validate_and_fix(raw_c, {})
    eq("PP: empty CTA → dest cleared", fc.get("Куда ведет CTA"), "")

    # Первый абзац — preserved as provided (not cleared)
    raw_d = {"Хук / первый экран": "🔥 Как я заработал 1 млн за 3 месяца"}
    fd, _, nd = _validate_and_fix(raw_d, {})
    eq("PP: первый абзац preserved",
       fd.get("Хук / первый экран"), "🔥 Как я заработал 1 млн за 3 месяца")

    # Вероятно prefix
    raw_e = {"Почему закреплен": "закреплен чтобы привлечь заявки"}
    fe, _, _ = _validate_and_fix(raw_e, {})
    ok("PP: Вероятно prefix added",
       fe.get("Почему закреплен", "").startswith("Вероятно"))

    # No prefix needed if already present
    raw_f = {"Почему закреплен": "Вероятно, закреплен как вход в воронку"}
    ff, wf, _ = _validate_and_fix(raw_f, {})
    eq("PP: Вероятно prefix not doubled",
       ff.get("Почему закреплен"), "Вероятно, закреплен как вход в воронку")

    # ── Trust + leadgen rule ──────────────────────────────────────────────

    # A. Trust proof signals helper
    ok("Trust: agency+experience detected",
       _has_trust_proof("Агентство работает 6+ лет. Среди клиентов — крупные компании."))
    ok("Trust: N+ projects detected",
       _has_trust_proof("1000+ проектов. Команда из 20 специалистов."))
    ok("Trust: NOT triggered by single weak mention",
       not _has_trust_proof("Хороший контент — это опыт."))  # only 1 category
    ok("Leadgen: consultation CTA detected",
       _has_leadgen_action("Пишите слово «консультация» в комментариях."))
    ok("Leadgen: application form detected",
       _has_leadgen_action("Оставьте заявку через анкету."))
    ok("Leadgen: NOT triggered by pure educational text",
       not _has_leadgen_action("Как создать контент-план за 30 минут."))

    # B. Trust + leadgen: role must include both доверие and лидогенерация
    trust_leadgen_caption = (
        "Агентство работает более 6 лет. Среди клиентов — топовые бренды СНГ. "
        "1000+ проектов в портфолио. Список услуг: SEO, контекст, SMM. "
        "Пишите слово «консультация» в комментариях."
    )
    raw_tl = {
        "Роль в воронке": "лидогенерация",
        "Какой CTA": "Пишите слово «консультация» в комментариях",
        "Куда ведет CTA": "комментарии → консультация",
        "Почему закреплен": "Вероятно, закреплен для лидогенерации",
    }
    post_tl = {"full_caption": trust_leadgen_caption}
    ftl, _, ntl = _validate_and_fix(raw_tl, post_tl)
    ok("TL: доверие added to role",
       "доверие" in ftl.get("Роль в воронке", ""))
    ok("TL: лидогенерация preserved in role",
       "лидогенерация" in ftl.get("Роль в воронке", ""))
    ok("TL: pp_note for role change",
       any(n["field"] == "Роль в воронке" for n in ntl))
    ok("TL: Почему закреплен updated to mention trust",
       bool(_PZ_TRUST_RE.search(ftl.get("Почему закреплен", ""))))
    ok("TL: Почему закреплен updated to mention leadgen",
       bool(_PZ_LEADGEN_RE.search(ftl.get("Почему закреплен", ""))))
    ok("TL: Почему закреплен starts with Вероятно",
       ftl.get("Почему закреплен", "").startswith("Вероятно"))

    # C. Leadgen only (no trust proof) — do NOT add доверие
    leadgen_only_caption = "Пишите «АНКЕТА» в директ и комментарии для предзаписи."
    raw_lo = {"Роль в воронке": "лидогенерация", "Какой CTA": "Пишите «АНКЕТА» в директ"}
    post_lo = {"full_caption": leadgen_only_caption}
    flo, _, _ = _validate_and_fix(raw_lo, post_lo)
    eq("TL: leadgen-only keeps role unchanged",
       flo.get("Роль в воронке"), "лидогенерация")

    # D. Trust only (no leadgen action) — do NOT add лидогенерация
    trust_only_caption = "6 лет опыта, клиенты, кейсы, услуги по SEO и контексту. Агентство."
    raw_to = {"Роль в воронке": "доверие", "Какой CTA": ""}
    post_to = {"full_caption": trust_only_caption}
    fto, _, _ = _validate_and_fix(raw_to, post_to)
    ok("TL: trust-only does NOT add лидогенерация",
       "лидогенерация" not in fto.get("Роль в воронке", ""))

    # E. Trust + leadgen with existing composite role — extends cleanly
    raw_te = {
        "Роль в воронке": "доверие / прогрев",
        "Какой CTA": "Напишите нам в директ",
        "Куда ведет CTA": "директ → консультация",
        "Почему закреплен": "Вероятно, закреплен для прогрева аудитории",
    }
    post_te = {"full_caption": trust_leadgen_caption}
    fte, _, nte = _validate_and_fix(raw_te, post_te)
    rv_te = fte.get("Роль в воронке", "")
    ok("TL: existing composite role extended with лидогенерация",
       "доверие" in rv_te and "лидогенерация" in rv_te and "прогрев" in rv_te)
    ok("TL: extended role atoms are valid",
       all(t.strip() in ALLOWED_FUNNEL_ROLES for t in re.split(r"[/,]", rv_te) if t.strip()))

    # F. Invalid role atom still rejected even with trust+leadgen
    raw_inv = {"Роль в воронке": "экспертность / лидогенерация"}
    post_inv = {"full_caption": trust_leadgen_caption}
    finv, _, _ = _validate_and_fix(raw_inv, post_inv)
    ok("TL: invalid role atom 'экспертность' still cleared",
       "экспертность" not in finv.get("Роль в воронке", ""))
    ok("TL: лидогенерация kept + доверие added after invalid atom fix",
       "лидогенерация" in finv.get("Роль в воронке", "") and
       "доверие" in finv.get("Роль в воронке", ""))

    return passed, failed, errors
