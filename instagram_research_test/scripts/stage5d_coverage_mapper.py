"""Coverage mapper for all 79 Excel fields across 6 sheets."""

import json
import re
from datetime import datetime
from pathlib import Path

EXPECTED_TOTAL_COLUMNS = 79
ACCOUNT = "vlada_kliuiko"

STATUS_READY   = "ready"
STATUS_PARTIAL = "partial"
STATUS_MISSING = "missing"

FILL_AUTO      = "automatic"
FILL_SEMI      = "semi_automatic"
FILL_MANUAL    = "manual"
FILL_NOT_BUILT = "not_built_yet"

CONF_HIGH   = "high"
CONF_MEDIUM = "medium"
CONF_LOW    = "low"

VALID_STATUSES   = {STATUS_READY, STATUS_PARTIAL, STATUS_MISSING}
VALID_FILL_MODES = {FILL_AUTO, FILL_SEMI, FILL_MANUAL, FILL_NOT_BUILT}

BASE = Path(__file__).parent.parent


def _fid(sheet_id, col):
    slug = re.sub(r"[\s/()\-]+", "_", col.lower()).strip("_")
    return f"{sheet_id}__{slug}"


def _sheet(sheet_name, sheet_id, row_grain, columns):
    return [
        {"sheet_name": sheet_name, "sheet_id": sheet_id,
         "column_name": col, "field_id": _fid(sheet_id, col),
         "row_grain": row_grain}
        for col in columns
    ]


FIELD_DEFINITIONS = (
    _sheet("Описание профиля", "profile_description", "competitor", [
        "Конкурент",
        "Ниша / продукт",
        "Что вынесено в имя профиля",
        "Описание профиля (bio)",
        "Для кого",
        "Обещание результата",
        "Позиционирование",
        "Социальные доказательства",
        "Аргументы доверия",
        "Главный CTA в bio",
        "Куда ведет CTA",
    ]) +
    _sheet("Анализ хайлайтс", "highlights_analysis", "highlight", [
        "Конкурент",
        "Название highlight",
        "Порядок (позиция)",
        "Тема highlight",
        "Задача highlight",
        "Что внутри (кратко)",
        "Какая механика подачи хайлайтс",
        "Куда ведет CTA (если есть)",
    ]) +
    _sheet("Закрепленные посты", "pinned_posts", "pinned_post", [
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
    ]) +
    _sheet("Воронка", "funnel", "funnel", [
        "Конкурент",
        "Полный путь пользователя",
        "Точка входа",
        "Первый шаг",
        "Что обещают за переход",
        "Куда ведет",
        "Что происходит дальше",
        "Где собирают контакт",
        "Какой контакт собирают",
        "Через сколько появляется продажа",
        "Как устроен прогрев",
        "Какие продукты предлагают",
        "Есть ли tripwire",
        "Есть ли основной продукт",
        "Есть ли консультация / диагностика",
        "Какие боли используют",
        "Какие посылы используют",
        "Какие возражения снимают",
        "Финальный CTA",
    ]) +
    _sheet("Лендинг", "landing", "landing", [
        "Конкурент",
        "Ссылка на сайт",
        "Что продают",
        "Структура первых 3х экранов",
        "Главный заголовок",
        "Подзаголовок",
        "Для кого",
        "Обещание результата",
        "Главный CTA",
        "Соцдоказательства",
        "Какие боли раскрывают",
        "Какие аргументы используют",
        "Какие блоки есть дальше",
    ]) +
    _sheet("Бот  лид-магнит", "bot_lead_magnet", "bot_or_lead_magnet", [
        "Конкурент",
        "Где нашли лид-магнит",
        "Название лид-магнита",
        "Обещание лид-магнита",
        "Формат лид-магнита",
        "Куда ведет",
        "Что человек получает сразу",
        "Первое сообщение / первый экран",
        "Есть ли сегментация и что в ней",
        "Что спрашивают у человека",
        "Какие сообщения идут дальше",
        "Когда появляется продажа",
        "Какой продукт продают",
        "Какие боли используют",
        "Какие посылы используют",
        "Какие возражения снимают",
        "Финальный CTA",
    ])
)

assert len(FIELD_DEFINITIONS) == 79, (
    f"FIELD_DEFINITIONS has {len(FIELD_DEFINITIONS)} entries, expected 79"
)

SOURCE_FILE_MAP = {
    "profile_summary":    BASE / "data/normalized/profile_summary.json",
    "bio_analysis":       BASE / "data/normalized/bio_analysis.json",
    "pinned_posts_index": BASE / "data/normalized/pinned_posts_index.json",
    "highlights_index":   BASE / "data/normalized/highlights_index.json",
    "stage5b_summary":    BASE / "data/normalized/stage5b_auto_stories_summary.json",
    "stage5b_index":      BASE / "data/normalized/stage5b_auto_stories_index.json",
    "stage5c_highlights": BASE / "data/normalized/stage5c_highlights_summary.json",
    "stage5c_stories":    BASE / "data/normalized/stage5c_stories_analysis.json",
}


def load_sources() -> dict:
    result = {}
    for key, path in SOURCE_FILE_MAP.items():
        if not path.exists():
            result[key] = None
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                result[key] = json.load(f)
        except Exception:
            result[key] = None
    return result


def source_presence() -> dict:
    return {k: v.exists() for k, v in SOURCE_FILE_MAP.items()}


def _redact_url(url):
    if not isinstance(url, str):
        return url
    if len(url) > 60 and url.startswith("http"):
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            prefix = parsed.path[:20] if parsed.path else ""
            return f"<url:{parsed.netloc}{prefix}...redacted>"
        except Exception:
            return "<url:...redacted>"
    return url


def _pval(d, *keys):
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v is not None and v != "" and v != []:
            return v
    return None


def _bio_field(bio, *keys):
    if not isinstance(bio, dict):
        return (None, "missing", None)
    for k in keys:
        v = bio.get(k)
        if v is None:
            continue
        if isinstance(v, dict):
            val = v.get("value")
            ds = v.get("data_status", "ok")
            conf = v.get("confidence", CONF_MEDIUM)
            if val is not None and val != "":
                return (val, ds, conf)
        elif v != "" and v != []:
            return (v, "ok", CONF_MEDIUM)
    return (None, "missing", None)


def _preview(v):
    if v is None:
        return None
    if isinstance(v, list):
        items = v[:3]
        parts = []
        for item in items:
            s = str(item)
            if len(s) > 60:
                s = s[:60] + "..."
            parts.append(_redact_url(s))
        result = str(parts)
        return result[:200]
    if isinstance(v, str):
        v = _redact_url(v)
        return v[:200] if len(v) > 200 else v
    return str(v)[:200]


def _rec(fdef, status_cur, status_pipe, fill_mode, confidence,
         source_files, source_fields, source_logic,
         preview=None, blocker=None, next_stage=None):
    return {
        "sheet_name": fdef["sheet_name"],
        "sheet_id": fdef["sheet_id"],
        "column_name": fdef["column_name"],
        "field_id": fdef["field_id"],
        "row_grain": fdef["row_grain"],
        "status_current_data": status_cur,
        "status_pipeline_capability": status_pipe,
        "fill_mode": fill_mode,
        "confidence": confidence,
        "source_files": source_files,
        "source_fields": source_fields,
        "source_logic": source_logic,
        "preview": preview,
        "blocker": blocker,
        "next_stage_needed": next_stage,
    }


_RESOLVERS: dict = {}


def _resolve_competitor_always_ready(fdef, sources):
    ps = sources.get("profile_summary")
    account = _pval(ps, "username", "userName") if ps else ACCOUNT
    if not account:
        account = ACCOUNT
    return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                ["profile_summary"], ["username"],
                "Use profile_summary.username or fallback to ACCOUNT constant",
                preview=account)


# --- Profile description resolvers ---

def _r_pd_konkurent(fdef, sources):
    ps = sources.get("profile_summary")
    account = ACCOUNT
    if ps:
        account = _pval(ps, "username", "userName") or ACCOUNT
    return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                ["profile_summary"], ["username", "userName"],
                "Use profile_summary.username or fallback to ACCOUNT constant",
                preview=account)

_RESOLVERS[_fid("profile_description", "Конкурент")] = _r_pd_konkurent


def _r_pd_niche(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, conf = _bio_field(bio, "niche", "ниша", "ниша_продукт", "product_niche")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_SEMI, None,
                    ["bio_analysis"], ["niche", "ниша", "product_niche"],
                    "bio_analysis not available",
                    blocker="bio_analysis.json not found")
    if val is not None and ds in ("ok", "partial"):
        cur_conf = CONF_HIGH if ds == "ok" else CONF_MEDIUM
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_SEMI, cur_conf,
                    ["bio_analysis"], ["niche", "ниша", "product_niche"],
                    f"bio_analysis field; data_status={ds}",
                    preview=_preview(val))
    if ds == "manual_needed" or val is None:
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_SEMI, CONF_LOW,
                    ["bio_analysis"], ["niche", "ниша", "product_niche"],
                    f"bio_analysis field; data_status={ds}; value not found or manual_needed")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_SEMI, None,
                ["bio_analysis"], ["niche", "ниша", "product_niche"],
                "bio_analysis present but field not found")

_RESOLVERS[_fid("profile_description", "Ниша / продукт")] = _r_pd_niche


def _r_pd_name_in_profile(fdef, sources):
    ps = sources.get("profile_summary")
    if ps is None:
        return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                    ["profile_summary"], ["fullName", "full_name", "name"],
                    "profile_summary not available")
    val = _pval(ps, "fullName", "full_name", "name")
    if val:
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                    ["profile_summary"], ["fullName", "full_name", "name"],
                    "profile_summary.fullName",
                    preview=_preview(val))
    return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_AUTO, CONF_LOW,
                ["profile_summary"], ["fullName", "full_name", "name"],
                "profile_summary present but fullName/name field missing")

_RESOLVERS[_fid("profile_description", "Что вынесено в имя профиля")] = _r_pd_name_in_profile


def _r_pd_bio_text(fdef, sources):
    ps = sources.get("profile_summary")
    if ps is None:
        return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                    ["profile_summary"], ["biography", "bio"],
                    "profile_summary not available")
    val = _pval(ps, "biography", "bio")
    if val:
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                    ["profile_summary"], ["biography", "bio"],
                    "profile_summary.biography",
                    preview=_preview(val))
    return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_AUTO, CONF_HIGH,
                ["profile_summary"], ["biography", "bio"],
                "profile_summary present but biography field missing or empty")

_RESOLVERS[_fid("profile_description", "Описание профиля (bio)")] = _r_pd_bio_text


def _r_pd_for_whom(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, _ = _bio_field(bio, "target_audience", "для_кого", "audience")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, None,
                    ["bio_analysis"], ["target_audience", "для_кого", "audience"],
                    "bio_analysis not available")
    if val is not None and ds in ("ok", "partial"):
        return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                    ["bio_analysis"], ["target_audience", "для_кого", "audience"],
                    f"rule-based field from bio_analysis; data_status={ds}; max conf=medium",
                    preview=_preview(val))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["bio_analysis"], ["target_audience", "для_кого", "audience"],
                "bio_analysis present but target_audience not found")

_RESOLVERS[_fid("profile_description", "Для кого")] = _r_pd_for_whom


def _r_pd_result_promise(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, _ = _bio_field(bio, "result_promise", "обещание_результата", "promise", "result")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, None,
                    ["bio_analysis"], ["result_promise", "обещание_результата", "promise"],
                    "bio_analysis not available")
    if val is not None and ds in ("ok", "partial"):
        return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                    ["bio_analysis"], ["result_promise", "обещание_результата", "promise"],
                    f"rule-based field; data_status={ds}; max conf=medium",
                    preview=_preview(val))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["bio_analysis"], ["result_promise", "обещание_результата", "promise"],
                "bio_analysis present but result_promise not found")

_RESOLVERS[_fid("profile_description", "Обещание результата")] = _r_pd_result_promise


def _r_pd_positioning(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, _ = _bio_field(bio, "positioning", "позиционирование")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, None,
                    ["bio_analysis"], ["positioning", "позиционирование"],
                    "bio_analysis not available")
    if val is not None and ds in ("ok", "partial"):
        return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                    ["bio_analysis"], ["positioning", "позиционирование"],
                    f"rule-based field; data_status={ds}; max conf=medium",
                    preview=_preview(val))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["bio_analysis"], ["positioning", "позиционирование"],
                "bio_analysis present but positioning not found")

_RESOLVERS[_fid("profile_description", "Позиционирование")] = _r_pd_positioning


def _r_pd_social_proof(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, _ = _bio_field(bio, "social_proof", "социальные_доказательства", "social_proofs")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, None,
                    ["bio_analysis"], ["social_proof", "социальные_доказательства"],
                    "bio_analysis not available")
    if val is not None:
        return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                    ["bio_analysis"], ["social_proof", "социальные_доказательства"],
                    "rule-based field; social proof harder to infer from bio; max conf=low",
                    preview=_preview(val))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["bio_analysis"], ["social_proof", "социальные_доказательства"],
                "bio_analysis present but social_proof not found")

_RESOLVERS[_fid("profile_description", "Социальные доказательства")] = _r_pd_social_proof


def _r_pd_trust_args(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, _ = _bio_field(bio, "trust_arguments", "аргументы_доверия", "trust")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, None,
                    ["bio_analysis"], ["trust_arguments", "аргументы_доверия"],
                    "bio_analysis not available")
    if val is not None:
        return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                    ["bio_analysis"], ["trust_arguments", "аргументы_доверия"],
                    "rule-based field; max conf=low",
                    preview=_preview(val))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["bio_analysis"], ["trust_arguments", "аргументы_доверия"],
                "bio_analysis present but trust_arguments not found")

_RESOLVERS[_fid("profile_description", "Аргументы доверия")] = _r_pd_trust_args


def _r_pd_main_cta(fdef, sources):
    bio = sources.get("bio_analysis")
    val, ds, conf = _bio_field(bio, "cta", "main_cta", "bio_cta", "call_to_action", "главный_cta")
    if bio is None:
        return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_SEMI, None,
                    ["bio_analysis"], ["cta", "main_cta", "bio_cta"],
                    "bio_analysis not available")
    if val is not None and ds == "ok":
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_SEMI, CONF_HIGH,
                    ["bio_analysis"], ["cta", "main_cta", "bio_cta"],
                    f"bio_analysis CTA field; data_status={ds}",
                    preview=_preview(val))
    if val is not None and ds == "partial":
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_SEMI, CONF_MEDIUM,
                    ["bio_analysis"], ["cta", "main_cta", "bio_cta"],
                    f"bio_analysis CTA field; data_status={ds}",
                    preview=_preview(val))
    if bio is not None:
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_SEMI, None,
                    ["bio_analysis"], ["cta", "main_cta", "bio_cta"],
                    "bio_analysis present but CTA field not found or missing")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_SEMI, None,
                ["bio_analysis"], ["cta", "main_cta", "bio_cta"],
                "bio_analysis not available")

_RESOLVERS[_fid("profile_description", "Главный CTA в bio")] = _r_pd_main_cta


def _r_pd_cta_destination(fdef, sources):
    ps = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    url = None
    if ps:
        url = _pval(ps, "externalUrl", "external_url", "bioUrl", "bio_url", "url", "website")
    if not url and bio and isinstance(bio, dict):
        url = _pval(bio, "destination", "destination_url", "куда_ведет")
    if url:
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                    ["profile_summary", "bio_analysis"],
                    ["externalUrl", "external_url", "destination"],
                    "profile_summary.externalUrl or bio_analysis.destination",
                    preview=_redact_url(str(url)))
    if ps is not None or bio is not None:
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_AUTO, CONF_LOW,
                    ["profile_summary", "bio_analysis"],
                    ["externalUrl", "external_url", "destination"],
                    "sources present but no external URL found; bio may have no external link")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                ["profile_summary", "bio_analysis"],
                ["externalUrl", "external_url"],
                "both profile_summary and bio_analysis not available")

_RESOLVERS[_fid("profile_description", "Куда ведет CTA")] = _r_pd_cta_destination


# --- Highlights analysis resolvers ---

_RESOLVERS[_fid("highlights_analysis", "Конкурент")] = _resolve_competitor_always_ready


def _r_ha_title(fdef, sources):
    hi = sources.get("highlights_index")
    if isinstance(hi, list) and len(hi) > 0:
        titles = [item.get("title") or item.get("name") or item.get("id", "") for item in hi[:3]]
        titles = [t for t in titles if t]
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                    ["highlights_index"], ["title", "name"],
                    f"highlights_index list; {len(hi)} highlights available",
                    preview=_preview(titles))
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                ["highlights_index"], ["title", "name"],
                "highlights_index not available or empty")

_RESOLVERS[_fid("highlights_analysis", "Название highlight")] = _r_ha_title


def _r_ha_position(fdef, sources):
    hi = sources.get("highlights_index")
    if isinstance(hi, list) and len(hi) > 0:
        positions = [item.get("position") or item.get("order") or item.get("index") for item in hi[:3]]
        positions = [p for p in positions if p is not None]
        return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                    ["highlights_index"], ["position", "order", "index"],
                    f"highlights_index position field; {len(hi)} highlights",
                    preview=_preview(positions) if positions else f"{len(hi)} items, position field present")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                ["highlights_index"], ["position"],
                "highlights_index not available or empty")

_RESOLVERS[_fid("highlights_analysis", "Порядок (позиция)")] = _r_ha_position


def _r_ha_theme(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["stage5c_highlights", "highlights_index"],
                ["dominant_content_type", "tags"],
                "stage5c_highlights_summary: dominant_content_type / tags for 3 highlights; 29 highlights not analyzed",
                blocker="Only 3 of 32 highlights collected and analyzed by OpenAI. Need Stage 5B-auto maxHighlights=32 + Stage 5C re-run.",
                next_stage="Stage 5B-auto full collection (maxHighlights=32) + Stage 5C re-run")

_RESOLVERS[_fid("highlights_analysis", "Тема highlight")] = _r_ha_theme


def _r_ha_task(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["stage5c_highlights"],
                ["commercial_role_distribution"],
                "stage5c_highlights: commercial_role_distribution per highlight; 3/32 analyzed",
                blocker="Only 3 of 32 highlights collected and analyzed by OpenAI. Need Stage 5B-auto maxHighlights=32 + Stage 5C re-run.",
                next_stage="Stage 5B-auto full collection (maxHighlights=32) + Stage 5C re-run")

_RESOLVERS[_fid("highlights_analysis", "Задача highlight")] = _r_ha_task


def _r_ha_inside(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["stage5c_highlights"],
                ["common_tags", "content_type_distribution"],
                "stage5c_highlights: common_tags, content_type_distribution; 3/32 analyzed",
                blocker="Only 3 of 32 highlights collected and analyzed by OpenAI. Need Stage 5B-auto maxHighlights=32 + Stage 5C re-run.",
                next_stage="Stage 5B-auto full collection (maxHighlights=32) + Stage 5C re-run")

_RESOLVERS[_fid("highlights_analysis", "Что внутри (кратко)")] = _r_ha_inside


def _r_ha_mechanic(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["stage5c_highlights"],
                ["dominant_content_type", "extracted_ctas", "cta_rate"],
                "stage5c_highlights: dominant_content_type, extracted_ctas, cta_rate; 3/32; requires synthesis across all highlights",
                blocker="Only 3/32 analyzed. Also: this field needs human synthesis across all highlights — not a per-story field.",
                next_stage="Stage 5B-auto full + Stage 5C + manual synthesis")

_RESOLVERS[_fid("highlights_analysis", "Какая механика подачи хайлайтс")] = _r_ha_mechanic


def _r_ha_cta_dest(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["stage5c_highlights", "stage5b_index"],
                ["extracted_ctas", "linkUrl"],
                "stage5c_highlights: extracted_ctas; stage5b_index: linkUrl per story; 3/32 analyzed",
                blocker="Only 3 of 32 highlights analyzed. Need full collection + Stage 5C re-run.",
                next_stage="Stage 5B-auto full + Stage 5C re-run")

_RESOLVERS[_fid("highlights_analysis", "Куда ведет CTA (если есть)")] = _r_ha_cta_dest


# --- Pinned posts resolvers ---

_RESOLVERS[_fid("pinned_posts", "Конкурент")] = _resolve_competitor_always_ready


def _r_pp_url(fdef, sources):
    pi = sources.get("pinned_posts_index")
    if isinstance(pi, list) and len(pi) >= 1:
        urls = []
        for item in pi:
            u = _pval(item, "url", "postUrl", "link", "shortCode")
            if u:
                urls.append(_redact_url(str(u)))
        if urls:
            return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                        ["pinned_posts_index"], ["url", "postUrl", "link", "shortCode"],
                        "pinned_posts_index list; url field per item",
                        preview=_preview(urls))
    if isinstance(pi, list) and len(pi) >= 1:
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_AUTO, CONF_MEDIUM,
                    ["pinned_posts_index"], ["url", "postUrl"],
                    "pinned_posts_index present but url/postUrl field not found in items")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                ["pinned_posts_index"], ["url", "postUrl"],
                "pinned_posts_index not available")

_RESOLVERS[_fid("pinned_posts", "Ссылка на пост")] = _r_pp_url


def _r_pp_position(fdef, sources):
    pi = sources.get("pinned_posts_index")
    if isinstance(pi, list) and len(pi) >= 1:
        positions = [item.get("position") or item.get("order") or item.get("pinnedPosition") for item in pi]
        positions = [p for p in positions if p is not None]
        if positions:
            return _rec(fdef, STATUS_READY, STATUS_READY, FILL_AUTO, CONF_HIGH,
                        ["pinned_posts_index"], ["position", "order", "pinnedPosition"],
                        "pinned_posts_index position field",
                        preview=_preview(positions))
        return _rec(fdef, STATUS_PARTIAL, STATUS_READY, FILL_AUTO, CONF_MEDIUM,
                    ["pinned_posts_index"], ["position"],
                    "pinned_posts_index present but position field not found")
    return _rec(fdef, STATUS_MISSING, STATUS_READY, FILL_AUTO, None,
                ["pinned_posts_index"], ["position"],
                "pinned_posts_index not available")

_RESOLVERS[_fid("pinned_posts", "Позиция закрепа")] = _r_pp_position


def _r_pp_theme(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No AI semantic analysis of pinned posts built",
                blocker="No AI semantic analysis of pinned posts. Requires new stage: pinned post content analyzer.",
                next_stage="Stage 5A-2 or dedicated pinned post semantic analyzer")

_RESOLVERS[_fid("pinned_posts", "Тема поста")] = _r_pp_theme


def _r_pp_why_pinned(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No semantic analysis of pinned post context",
                blocker="Requires semantic analysis of pinned post content + context. No such stage built.",
                next_stage="Pinned post semantic analyzer (new stage)")

_RESOLVERS[_fid("pinned_posts", "Почему закреплен")] = _r_pp_why_pinned


def _r_pp_hook(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No media/visual analysis of pinned post first frame",
                blocker="Requires visual/text analysis of first post frame. No media analysis stage for pinned posts.",
                next_stage="Pinned post media + semantic analyzer")

_RESOLVERS[_fid("pinned_posts", "Хук / первый экран")] = _r_pp_hook


def _r_pp_caption(fdef, sources):
    pi = sources.get("pinned_posts_index")
    if isinstance(pi, list) and len(pi) >= 1:
        captions = [_pval(item, "caption", "text", "description") for item in pi]
        captions = [c for c in captions if c]
        if captions:
            return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                        ["pinned_posts_index"], ["caption", "text", "description"],
                        "Raw caption from pinned_posts_index; semantic extraction not yet built",
                        preview=_preview(captions[0]))
        return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                    ["pinned_posts_index"], ["caption", "text"],
                    "pinned_posts_index present but caption field not found in items")
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_MEDIUM,
                ["pinned_posts_index"], ["caption"],
                "pinned_posts_index not available")

_RESOLVERS[_fid("pinned_posts", "Что в тексте поста")] = _r_pp_caption


def _r_pp_key_meanings(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No AI semantic analysis of post text",
                blocker="Requires AI semantic analysis of post text. No such stage built.",
                next_stage="Pinned post semantic analyzer")

_RESOLVERS[_fid("pinned_posts", "Ключевые смыслы")] = _r_pp_key_meanings


def _r_pp_cta_type(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No AI analysis of post text + visual CTA detection",
                blocker="Requires AI analysis of post text + visual CTA detection.",
                next_stage="Pinned post semantic analyzer")

_RESOLVERS[_fid("pinned_posts", "Какой CTA")] = _r_pp_cta_type


def _r_pp_cta_dest(fdef, sources):
    pi = sources.get("pinned_posts_index")
    if isinstance(pi, list) and len(pi) >= 1:
        links = [_pval(item, "linkUrl", "externalUrl", "link") for item in pi]
        links = [l for l in links if l]
        if links:
            return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                        ["pinned_posts_index"], ["linkUrl", "externalUrl", "link"],
                        "CTA URL from pinned_posts_index link sticker data; destination content not analyzed",
                        preview=_preview([_redact_url(str(l)) for l in links]))
    return _rec(fdef, STATUS_MISSING, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["pinned_posts_index"], ["linkUrl", "externalUrl"],
                "CTA URL only available if post has explicit link sticker data in normalized index")

_RESOLVERS[_fid("pinned_posts", "Куда ведет CTA")] = _r_pp_cta_dest


def _r_pp_funnel_role(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No funnel context or semantic analysis of post role",
                blocker="Requires funnel context + semantic analysis of post role. No funnel stage built.",
                next_stage="Funnel mapper + pinned post semantic analyzer")

_RESOLVERS[_fid("pinned_posts", "Роль в воронке")] = _r_pp_funnel_role


# --- Funnel resolvers ---

_RESOLVERS[_fid("funnel", "Конкурент")] = _resolve_competitor_always_ready


def _r_fn_full_path(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No funnel traversal data",
                blocker="No funnel traversal data. Requires manual or automated landing/bot analysis.",
                next_stage="Stage 5E: funnel mapper")

_RESOLVERS[_fid("funnel", "Полный путь пользователя")] = _r_fn_full_path


def _r_fn_entry_point(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["bio_analysis", "profile_summary"],
                ["cta", "externalUrl"],
                "Entry point is Instagram profile. First touchpoint known from bio analysis. Traversal beyond bio not built.",
                next_stage="Stage 5E: funnel mapper")

_RESOLVERS[_fid("funnel", "Точка входа")] = _r_fn_entry_point


def _r_fn_first_step(fdef, sources):
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["bio_analysis"],
                ["cta", "destination"],
                "Bio CTA direction known; first step not confirmed by traversal",
                next_stage="Stage 5E: funnel mapper")

_RESOLVERS[_fid("funnel", "Первый шаг")] = _r_fn_first_step


def _r_fn_promise_transition(fdef, sources):
    return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [],
                "No funnel traversal",
                blocker="No funnel traversal data. Requires manual or automated landing/bot analysis.",
                next_stage="Stage 5E: funnel mapper")

_RESOLVERS[_fid("funnel", "Что обещают за переход")] = _r_fn_promise_transition


def _r_fn_leads_to(fdef, sources):
    ps = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    url = None
    if ps:
        url = _pval(ps, "externalUrl", "external_url", "bioUrl", "bio_url", "url", "website")
    if not url and bio and isinstance(bio, dict):
        url = _pval(bio, "destination", "destination_url", "куда_ведет")
    preview = _redact_url(str(url)) if url else None
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["profile_summary", "bio_analysis"],
                ["externalUrl", "destination"],
                "URL known from profile_summary/bio_analysis; destination content not analyzed",
                preview=preview,
                next_stage="Stage 5E: landing/funnel analyzer")

_RESOLVERS[_fid("funnel", "Куда ведет")] = _r_fn_leads_to


_FUNNEL_REMAINING_BLOCKER = "Requires funnel traversal: landing page, bot/lead-magnet sequence, checkout path. No such stage built."
_FUNNEL_REMAINING_NEXT = "Stage 5E: funnel mapper + landing analyzer + bot traversal"

for _col in [
    "Что происходит дальше",
    "Где собирают контакт",
    "Какой контакт собирают",
    "Через сколько появляется продажа",
    "Как устроен прогрев",
    "Какие продукты предлагают",
    "Есть ли tripwire",
    "Есть ли основной продукт",
    "Есть ли консультация / диагностика",
    "Какие боли используют",
    "Какие посылы используют",
    "Какие возражения снимают",
    "Финальный CTA",
]:
    def _make_funnel_resolver(col):
        def _resolver(fdef, sources):
            return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                        [], [],
                        f"No funnel traversal data for: {col}",
                        blocker=_FUNNEL_REMAINING_BLOCKER,
                        next_stage=_FUNNEL_REMAINING_NEXT)
        return _resolver
    _RESOLVERS[_fid("funnel", _col)] = _make_funnel_resolver(_col)


# --- Landing resolvers ---

_RESOLVERS[_fid("landing", "Конкурент")] = _resolve_competitor_always_ready


def _r_la_site_url(fdef, sources):
    ps = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    url = None
    if ps:
        url = _pval(ps, "externalUrl", "external_url", "bioUrl", "bio_url", "url", "website")
    if not url and bio and isinstance(bio, dict):
        url = _pval(bio, "destination", "destination_url", "куда_ведет")
    preview = _redact_url(str(url)) if url else None
    return _rec(fdef, STATUS_PARTIAL, STATUS_PARTIAL, FILL_SEMI, CONF_LOW,
                ["profile_summary", "bio_analysis"],
                ["externalUrl", "destination"],
                "Bio URL available but may not be landing; could be Taplink/Linktree; landing confirmation not built",
                preview=preview,
                next_stage="Stage 5E: landing analyzer")

_RESOLVERS[_fid("landing", "Ссылка на сайт")] = _r_la_site_url


_LANDING_BLOCKER = "No landing page analysis. Requires web crawling and content analysis of the destination URL."
_LANDING_NEXT = "Stage 5E: landing analyzer"

for _col in [
    "Что продают",
    "Структура первых 3х экранов",
    "Главный заголовок",
    "Подзаголовок",
    "Для кого",
    "Обещание результата",
    "Главный CTA",
    "Соцдоказательства",
    "Какие боли раскрывают",
    "Какие аргументы используют",
    "Какие блоки есть дальше",
]:
    def _make_landing_resolver(col):
        def _resolver(fdef, sources):
            return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                        [], [],
                        f"No landing page analysis for: {col}",
                        blocker=_LANDING_BLOCKER,
                        next_stage=_LANDING_NEXT)
        return _resolver
    _RESOLVERS[_fid("landing", _col)] = _make_landing_resolver(_col)


# --- Bot / lead-magnet resolvers ---

_RESOLVERS[_fid("bot_lead_magnet", "Конкурент")] = _resolve_competitor_always_ready


_BOT_BLOCKER = "No bot/lead-magnet traversal data. Requires manual or automated bot interaction sequence."
_BOT_NEXT = "Stage 5F: bot/lead-magnet traversal"

for _col in [
    "Где нашли лид-магнит",
    "Название лид-магнита",
    "Обещание лид-магнита",
    "Формат лид-магнита",
    "Куда ведет",
    "Что человек получает сразу",
    "Первое сообщение / первый экран",
    "Есть ли сегментация и что в ней",
    "Что спрашивают у человека",
    "Какие сообщения идут дальше",
    "Когда появляется продажа",
    "Какой продукт продают",
    "Какие боли используют",
    "Какие посылы используют",
    "Какие возражения снимают",
    "Финальный CTA",
]:
    def _make_bot_resolver(col):
        def _resolver(fdef, sources):
            return _rec(fdef, STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                        [], [],
                        f"No bot/lead-magnet traversal for: {col}",
                        blocker=_BOT_BLOCKER,
                        next_stage=_BOT_NEXT)
        return _resolver
    _RESOLVERS[_fid("bot_lead_magnet", _col)] = _make_bot_resolver(_col)


def build_sheet_summaries(coverage_map, sources):
    """Compute per-sheet metadata."""
    SHEET_META = {
        "profile_description": {
            "row_grain": "competitor",
            "row_source_file": "profile_summary.json",
            "expected_rows_now_fn": lambda s: 1 if s.get("profile_summary") is not None else 0,
            "expected_rows_pipeline": 1,
            "notes": "1 row per competitor. Profile summary already collected.",
        },
        "highlights_analysis": {
            "row_grain": "highlight",
            "row_source_file": "highlights_index.json",
            "expected_rows_now_fn": lambda s: len(s["highlights_index"]) if isinstance(s.get("highlights_index"), list) else 0,
            "expected_rows_pipeline": 32,
            "notes": "32 highlights in index. 3 analyzed by Stage 5C so far.",
        },
        "pinned_posts": {
            "row_grain": "pinned_post",
            "row_source_file": "pinned_posts_index.json",
            "expected_rows_now_fn": lambda s: len(s["pinned_posts_index"]) if isinstance(s.get("pinned_posts_index"), list) else 0,
            "expected_rows_pipeline": 3,
            "notes": "3 pinned posts in index. Structural fields ready; semantic fields missing.",
        },
        "funnel": {
            "row_grain": "funnel",
            "row_source_file": None,
            "expected_rows_now_fn": lambda s: 0,
            "expected_rows_pipeline": 0,
            "notes": "0 rows. Requires funnel traversal stage (not built).",
        },
        "landing": {
            "row_grain": "landing",
            "row_source_file": None,
            "expected_rows_now_fn": lambda s: 0,
            "expected_rows_pipeline": 0,
            "notes": "0 rows. Requires landing page analysis (not built).",
        },
        "bot_lead_magnet": {
            "row_grain": "bot_or_lead_magnet",
            "row_source_file": None,
            "expected_rows_now_fn": lambda s: 0,
            "expected_rows_pipeline": 0,
            "notes": "0 rows. Requires bot/lead-magnet traversal (not built).",
        },
    }

    sheet_names = {}
    for fdef in FIELD_DEFINITIONS:
        sid = fdef["sheet_id"]
        if sid not in sheet_names:
            sheet_names[sid] = fdef["sheet_name"]

    summaries = []
    for sheet_id, meta in SHEET_META.items():
        fields = [r for r in coverage_map if r["sheet_id"] == sheet_id]
        ready_cur = sum(1 for r in fields if r["status_current_data"] == STATUS_READY)
        partial_cur = sum(1 for r in fields if r["status_current_data"] == STATUS_PARTIAL)
        missing_cur = sum(1 for r in fields if r["status_current_data"] == STATUS_MISSING)
        ready_pipe = sum(1 for r in fields if r["status_pipeline_capability"] == STATUS_READY)
        partial_pipe = sum(1 for r in fields if r["status_pipeline_capability"] == STATUS_PARTIAL)
        missing_pipe = sum(1 for r in fields if r["status_pipeline_capability"] == STATUS_MISSING)

        rows_now = meta["expected_rows_now_fn"](sources)
        can_create_now = rows_now > 0

        summaries.append({
            "sheet_id": sheet_id,
            "sheet_name": sheet_names.get(sheet_id, sheet_id),
            "row_grain": meta["row_grain"],
            "row_source_file": meta["row_source_file"],
            "total_fields": len(fields),
            "current_data": {"ready": ready_cur, "partial": partial_cur, "missing": missing_cur},
            "pipeline_capability": {"ready": ready_pipe, "partial": partial_pipe, "missing": missing_pipe},
            "can_create_rows_now": can_create_now,
            "expected_rows_now": rows_now,
            "expected_rows_pipeline": meta["expected_rows_pipeline"],
            "notes": meta["notes"],
        })

    return summaries


def validate_coverage_map(coverage_map):
    assert len(coverage_map) == EXPECTED_TOTAL_COLUMNS, (
        f"coverage_map has {len(coverage_map)} entries, expected {EXPECTED_TOTAL_COLUMNS}"
    )
    required_fields = ["sheet_name", "sheet_id", "column_name", "field_id",
                       "status_current_data", "status_pipeline_capability", "fill_mode"]
    for r in coverage_map:
        assert r.get("sheet_name"), f"Missing sheet_name: {r}"
        assert r.get("sheet_id"), f"Missing sheet_id: {r}"
        assert r.get("column_name"), f"Missing column_name: {r}"
        assert r.get("field_id"), f"Missing field_id: {r}"
        assert r["status_current_data"] in VALID_STATUSES, (
            f"Invalid status_current_data '{r['status_current_data']}' for {r['field_id']}"
        )
        assert r["status_pipeline_capability"] in VALID_STATUSES, (
            f"Invalid status_pipeline_capability '{r['status_pipeline_capability']}' for {r['field_id']}"
        )
        assert r["fill_mode"] in VALID_FILL_MODES, (
            f"Invalid fill_mode '{r['fill_mode']}' for {r['field_id']}"
        )

    sheets_seen = set(r["sheet_id"] for r in coverage_map)
    expected_sheets = {
        "profile_description", "highlights_analysis", "pinned_posts",
        "funnel", "landing", "bot_lead_magnet"
    }
    for s in expected_sheets:
        assert s in sheets_seen, f"Sheet {s} has 0 mapped fields"


def run_coverage_map(sources=None) -> tuple:
    """Returns (coverage_map, sheet_summaries, meta)."""
    if sources is None:
        sources = load_sources()

    coverage_map = []
    for fdef in FIELD_DEFINITIONS:
        resolver = _RESOLVERS.get(fdef["field_id"])
        if resolver:
            record = resolver(fdef, sources)
        else:
            record = _rec(fdef,
                STATUS_MISSING, STATUS_MISSING, FILL_NOT_BUILT, None,
                [], [], "No resolver defined",
                blocker=f"Resolver not implemented for field_id={fdef['field_id']}",
                next_stage=None)
        coverage_map.append(record)

    validate_coverage_map(coverage_map)
    sheet_summaries = build_sheet_summaries(coverage_map, sources)

    meta = {
        "total_columns": len(coverage_map),
        "account": ACCOUNT,
        "run_timestamp": datetime.utcnow().isoformat() + "Z",
        "source_presence": source_presence(),
    }
    return coverage_map, sheet_summaries, meta
