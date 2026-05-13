"""Stage 5D-1: Build Google Sheets-ready row data from normalized pipeline outputs."""

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).parent.parent

ACCOUNT        = "vlada_kliuiko"
SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
START_ROW      = 3

EXPECTED_TOTAL_COLUMNS = 79
EXCEL_TEMPLATE = BASE / "input/competitor_analysis_template.xlsx"

# Fallback headers — used when Excel template is absent
FALLBACK_HEADERS = {
    "Описание профиля": [
        "Конкурент", "Ниша / продукт", "Что вынесено в имя профиля",
        "Описание профиля (bio)", "Для кого", "Обещание результата",
        "Позиционирование", "Социальные доказательства", "Аргументы доверия",
        "Главный CTA в bio", "Куда ведет CTA",
    ],
    "Анализ хайлайтс": [
        "Конкурент", "Название highlight", "Порядок (позиция)",
        "Тема highlight", "Задача highlight", "Что внутри (кратко)",
        "Какая механика подачи хайлайтс", "Куда ведет CTA (если есть)",
    ],
    "Закрепленные посты": [
        "Конкурент", "Ссылка на пост", "Позиция закрепа", "Тема поста",
        "Почему закреплен", "Хук / первый экран", "Что в тексте поста",
        "Ключевые смыслы", "Какой CTA", "Куда ведет CTA", "Роль в воронке",
    ],
    "Воронка": [
        "Конкурент", "Полный путь пользователя", "Точка входа", "Первый шаг",
        "Что обещают за переход", "Куда ведет", "Что происходит дальше",
        "Где собирают контакт", "Какой контакт собирают",
        "Через сколько появляется продажа", "Как устроен прогрев",
        "Какие продукты предлагают", "Есть ли tripwire", "Есть ли основной продукт",
        "Есть ли консультация / диагностика", "Какие боли используют",
        "Какие посылы используют", "Какие возражения снимают", "Финальный CTA",
    ],
    "Лендинг": [
        "Конкурент", "Ссылка на сайт", "Что продают",
        "Структура первых 3х экранов", "Главный заголовок", "Подзаголовок",
        "Для кого", "Обещание результата", "Главный CTA", "Соцдоказательства",
        "Какие боли раскрывают", "Какие аргументы используют", "Какие блоки есть дальше",
    ],
    "Бот  лид-магнит": [
        "Конкурент", "Где нашли лид-магнит", "Название лид-магнита",
        "Обещание лид-магнита", "Формат лид-магнита", "Куда ведет",
        "Что человек получает сразу", "Первое сообщение / первый экран",
        "Есть ли сегментация и что в ней", "Что спрашивают у человека",
        "Какие сообщения идут дальше", "Когда появляется продажа",
        "Какой продукт продают", "Какие боли используют", "Какие посылы используют",
        "Какие возражения снимают", "Финальный CTA",
    ],
}

SOURCE_FILES = {
    "profile_summary":    BASE / "data/normalized/profile_summary.json",
    "bio_analysis":       BASE / "data/normalized/bio_analysis.json",
    "pinned_posts_index": BASE / "data/normalized/pinned_posts_index.json",
    "highlights_index":   BASE / "data/normalized/highlights_index.json",
    "stage5b_index":      BASE / "data/normalized/stage5b_auto_stories_index.json",
    "stage5c_highlights": BASE / "data/normalized/stage5c_highlights_summary.json",
    "stage5c_stories":    BASE / "data/normalized/stage5c_stories_analysis.json",
    "coverage_map":       BASE / "data/normalized/stage5d_coverage_map.json",
    "coverage_summary":   BASE / "data/normalized/stage5d_coverage_summary.json",
    "stage5a2c_fixed_rows": BASE / "data/normalized/stage5a2c_pinned_posts_google_sheet_rows_fixed.json",
    "stage5a2c_rows":       BASE / "data/normalized/stage5a2c_pinned_posts_google_sheet_rows.json",
    "bio_semantic":         BASE / "data/normalized/stage5a2e_bio_semantic.json",
    "highlights_visual":    BASE / "data/normalized/stage5b2v_highlights_visual.json",
}

_SECRET_PATTERNS = [
    "sk-", "apify_api_", "sessionid=", "OPENAI_API_KEY=", "APIFY_TOKEN=",
    "INSTAGRAM_SESSION_COOKIE=", "Authorization:", "Bearer ",
]

_CDN_MARKERS = ("cdninstagram.com", "scontent", "fbcdn.net", "lookaside.fbsbx.com")


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

def load_sources() -> dict:
    result = {}
    for key, path in SOURCE_FILES.items():
        if path.exists():
            try:
                result[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                result[key] = None
        else:
            result[key] = None
    return result


def source_presence() -> dict:
    return {k: v.exists() for k, v in SOURCE_FILES.items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fval(d, *keys):
    """Extract .value from field-wrapper dict, or plain value. Returns None if absent."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        if isinstance(v, dict) and "value" in v:
            val = v["value"]
            if val is not None and val != "" and val != []:
                return val
        elif v is not None and v != "" and v != []:
            return v
    return None


def _fstatus(d, *keys) -> str | None:
    """Get data_status from field-wrapper."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            s = v.get("data_status")
            if s:
                return s
    return None


def _fval_str(d, *keys) -> str:
    """Extract value as string; joins lists with ', '."""
    val = _fval(d, *keys)
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val if x)
    return str(val)


def _redact_url(url, *, payload_mode=False) -> str:
    """Redact CDN/long URLs. Keep normal Instagram post/profile URLs and bio URLs."""
    if not isinstance(url, str) or not url.startswith("http"):
        return str(url) if url else ""
    if any(m in url for m in _CDN_MARKERS):
        return "<instagram_cdn_redacted>"
    if len(url) > 120:
        if payload_mode:
            # In payload keep URL but strip long query params
            try:
                p = urlparse(url)
                return f"{p.scheme}://{p.netloc}{p.path}"
            except Exception:
                return url[:120] + "..."
        try:
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}/..."
        except Exception:
            return url[:120] + "..."
    return url


def _join_list(lst, sep=", ") -> str:
    if not lst or not isinstance(lst, list):
        return ""
    return sep.join(str(x) for x in lst if x)


def _dominant_role(distribution: dict) -> str:
    """Return the key with highest value from a distribution dict."""
    if not isinstance(distribution, dict) or not distribution:
        return ""
    try:
        return str(max(distribution, key=lambda k: (distribution[k] or 0)))
    except Exception:
        return ""


def _make_row(headers: list, field_map: dict) -> list:
    """Build a row (list of str) in header order; missing → empty string."""
    return [str(field_map.get(h, "") or "") for h in headers]


def _scan_secrets(text: str) -> list:
    found = []
    for p in _SECRET_PATTERNS:
        if p in text:
            found.append(p)
    return found


# ---------------------------------------------------------------------------
# Excel header reader
# ---------------------------------------------------------------------------

def read_excel_headers() -> tuple[dict | None, str | None]:
    """
    Returns (headers_dict, warning_or_None).
    headers_dict: {sheet_name: [col_names]} — None if unavailable.
    """
    if not EXCEL_TEMPLATE.exists():
        return None, f"Excel template not found at {EXCEL_TEMPLATE.relative_to(BASE)}; using hardcoded fallback"
    try:
        import openpyxl
    except ImportError:
        return None, "openpyxl not installed (pip install openpyxl); using hardcoded fallback"
    try:
        wb = openpyxl.load_workbook(str(EXCEL_TEMPLATE), read_only=True, data_only=True)
        headers = {}
        for sname in wb.sheetnames:
            ws = wb[sname]
            best_row, best_count = None, 0
            for row in ws.iter_rows(max_row=5, values_only=True):
                non_null = [c for c in row if c is not None]
                if len(non_null) > best_count:
                    best_count, best_row = len(non_null), non_null
            headers[sname] = [str(c) for c in (best_row or [])]
        wb.close()
        total = sum(len(v) for v in headers.values())
        if total != EXPECTED_TOTAL_COLUMNS:
            return None, f"Excel total columns={total} != expected {EXPECTED_TOTAL_COLUMNS}; using hardcoded fallback"
        return headers, None
    except Exception as e:
        return None, f"Excel read error: {e}; using hardcoded fallback"


# ---------------------------------------------------------------------------
# Index helpers
# ---------------------------------------------------------------------------

def _highlights_list(sources) -> list:
    raw = sources.get("highlights_index")
    if isinstance(raw, dict):
        return raw.get("highlights") or []
    if isinstance(raw, list):
        return raw
    return []


def _pinned_list(sources) -> list:
    raw = sources.get("pinned_posts_index")
    if isinstance(raw, dict):
        return raw.get("pinned_posts") or []
    if isinstance(raw, list):
        return raw
    return []


def _stage5c_index(sources) -> dict:
    """Return {bare_highlight_id: summary_dict} from stage5c_highlights_summary."""
    sc = sources.get("stage5c_highlights")
    if not isinstance(sc, dict):
        return {}
    raw = sc.get("highlights") or {}
    result = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            bare = str(k).replace("highlight:", "").strip()
            result[bare] = v
    elif isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            hid = item.get("highlight_id") or item.get("id") or ""
            bare = str(hid).replace("highlight:", "").strip()
            if bare:
                result[bare] = item
    return result


def _stage5b2v_index(sources: dict) -> dict:
    """Return {highlight_id: fields_dict} from stage5b2v_highlights_visual.json."""
    raw = sources.get("highlights_visual")
    if not raw or not isinstance(raw, dict):
        return {}
    result = {}
    for h in raw.get("analyzed_highlights", []):
        hid = str(h.get("highlight_id", "")).strip()
        if hid and not h.get("skipped") and not h.get("parse_error"):
            result[hid] = h.get("fields", {})
    return result


_CONTENT_TYPE_RU = {
    "student_review":  "отзывы",
    "educational":     "обучение",
    "case_study":      "кейсы",
    "introduction":    "знакомство",
    "product":         "продукт",
    "breakdown":       "разборы",
    "tools":           "инструменты",
    "geo_promotion":   "гео-продвижение",
}

_COMMERCIAL_ROLE_RU = {
    "trust":      "доверие",
    "education":  "обучение",
    "proof":      "социальное доказательство",
    "lead_gen":   "лидогенерация",
    "warm_up":    "прогрев",
    "sales":      "продажа",
}


def _vv_val(fields: dict, field: str) -> str:
    """Extract value from a stage5b2v field dict if data_status==ok."""
    f = fields.get(field, {})
    if isinstance(f, dict) and f.get("data_status") == "ok":
        return f.get("value", "")
    return ""


def _bio_url(sources) -> str | None:
    """Extract bio external URL from profile_summary or bio_analysis."""
    ps  = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    url = _fval(ps,  "external_url", "externalUrl") if ps  else None
    if not url:
        url = _fval(bio, "cta_destination", "destination") if bio else None
    return str(url) if url else None


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------

def build_profile_rows(sources, headers) -> tuple[list, list]:
    """1 row from profile_summary + bio_analysis."""
    ps  = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    warnings = []

    if ps is None and bio is None:
        return [], ["profile_summary.json and bio_analysis.json both missing"]

    # bio_text — с защитой от объектной структуры
    _raw_bio = ps.get("bio_text", {}) if ps else {}
    _bio_text = (_raw_bio.get("value") if isinstance(_raw_bio, dict) else _raw_bio) or ""
    _bio_lines = [l.strip() for l in _bio_text.splitlines() if l.strip()]

    # profile_url — с защитой от объектной структуры
    _raw_url = ps.get("profile_url", {}) if ps else {}
    _profile_url_val = (_raw_url.get("value") if isinstance(_raw_url, dict) else _raw_url) or ""

    row = {}
    _username = _fval(ps, "username", "userName") or ACCOUNT
    _profile_url = _profile_url_val or f"https://www.instagram.com/{_username}/"
    row["Конкурент"] = f"@{_username} {_profile_url}"

    _product_keywords = ["курс", "наставничество", "клуб", "консультац", "обучени"]
    _niche_line = next(
        (l for l in _bio_lines if any(kw in l.lower() for kw in _product_keywords)),
        None
    )
    row["Ниша / продукт"]             = _niche_line or _fval_str(bio, "niche") or ""
    row["Что вынесено в имя профиля"] = _fval_str(ps,  "full_name", "fullName", "name")
    row["Описание профиля (bio)"]     = _fval_str(ps,  "bio_text", "biography", "bio")

    sem = sources.get("bio_semantic")
    _sem_fields = sem.get("fields", {}) if isinstance(sem, dict) else {}

    # Для кого — bio_semantic P1, bio_analysis fallback
    _ta = _sem_fields.get("target_audience", {})
    if isinstance(_ta, dict) and _ta.get("data_status") == "ok":
        row["Для кого"] = _ta.get("value", "")
    elif _fstatus(bio, "target_audience") == "ok":
        row["Для кого"] = _fval_str(bio, "target_audience")
    else:
        row["Для кого"] = ""

    # Weak rule-based fields — leave empty
    row["Обещание результата"] = ""
    row["Позиционирование"]    = _bio_lines[0] if _bio_lines else _fval_str(bio, "positioning") or ""

    # Аргументы доверия — bio_semantic P1
    _trust = _sem_fields.get("trust_arguments", {})
    if isinstance(_trust, dict) and _trust.get("data_status") == "ok":
        row["Аргументы доверия"] = _trust.get("value", "")
    else:
        row["Аргументы доверия"] = ""

    # Социальные доказательства — bio_semantic P1
    _sp = _sem_fields.get("social_proof", {})
    if isinstance(_sp, dict) and _sp.get("data_status") == "ok":
        row["Социальные доказательства"] = _sp.get("value", "")
    else:
        row["Социальные доказательства"] = ""

    # Главный CTA в bio
    row["Главный CTA в bio"] = _fval_str(bio, "cta_text", "cta", "main_cta")

    # Куда ведет CTA
    url = _bio_url(sources)
    row["Куда ведет CTA"] = _redact_url(url) if url else ""

    if not row.get("Описание профиля (bio)"):
        warnings.append("bio_text not found in profile_summary; 'Описание профиля (bio)' is empty")

    return [_make_row(headers, row)], warnings


def build_highlights_rows(sources, headers) -> tuple[list, list]:
    """32 rows from highlights_index; semantic fill from stage5c for analyzed highlights."""
    hi_list  = _highlights_list(sources)
    sc_index = _stage5c_index(sources)
    vv_index = _stage5b2v_index(sources)
    warnings = []

    if not hi_list:
        return [], ["highlights_index.json missing or empty; no rows created"]

    analyzed_count = 0
    rows = []
    for item in hi_list:
        bare_id  = str(_fval(item, "highlight_id") or "").replace("highlight:", "").strip()
        title    = _fval_str(item, "title", "name")
        position = item.get("position")

        row = {
            "Конкурент":                      ACCOUNT,
            "Название highlight":             title,
            "Порядок (позиция)":             str(position) if position is not None else "",
            "Тема highlight":                 "",
            "Задача highlight":               "",
            "Что внутри (кратко)":           "",
            "Какая механика подачи хайлайтс": "",   # requires synthesis; always empty
            "Куда ведет CTA (если есть)":    "",
        }

        if bare_id and bare_id in vv_index:
            vv = vv_index[bare_id]
            row["Тема highlight"]                 = _vv_val(vv, "tema")
            row["Задача highlight"]               = _vv_val(vv, "zadacha")
            row["Что внутри (кратко)"]           = _vv_val(vv, "chto_vnutri")
            row["Какая механика подачи хайлайтс"] = _vv_val(vv, "mekhanika")
            row["Куда ведет CTA (если есть)"]    = _vv_val(vv, "cta")
            analyzed_count += 1
        elif bare_id and bare_id in sc_index:
            sc = sc_index[bare_id]
            raw_type = str(sc.get("dominant_content_type") or "")
            raw_role = _dominant_role(sc.get("commercial_role_distribution") or {})
            ru_type  = _CONTENT_TYPE_RU.get(raw_type, raw_type)
            ru_role  = _COMMERCIAL_ROLE_RU.get(raw_role, raw_role)
            if ru_type == raw_type and raw_type:
                warnings.append(
                    f"[WARN] Unknown content_type '{raw_type}' for highlight {bare_id} — used as-is"
                )
            row["Тема highlight"]                 = ru_type
            row["Задача highlight"]               = ru_role
            row["Что внутри (кратко)"]           = _join_list(sc.get("common_tags") or [])
            row["Куда ведет CTA (если есть)"]    = _join_list(sc.get("extracted_ctas") or [])
            # Механика подачи — не заполнять из Stage 5C, только из Stage 5B-2V
            analyzed_count += 1
        elif not bare_id:
            warnings.append(f"Highlight has no ID at position {position}; semantic fill skipped")

        rows.append(_make_row(headers, row))

    not_analyzed = len(hi_list) - analyzed_count
    if not_analyzed > 0:
        warnings.append(
            f"{not_analyzed}/{len(hi_list)} highlights not analyzed by Stage 5C; "
            "semantic cells (Тема, Задача, Что внутри, CTA) left empty for those rows"
        )
    return rows, warnings


_ALLOWED_ROLE_ATOMS = {"знакомство", "доверие", "прогрев", "продажа", "лидогенерация"}
_TRUST_KEYWORDS = (
    "доверие", "опыт", "клиент", "проект", "агентств",
    "кейс", "команд", "компани", "услуг", "эксперт",
)


def _validate_semantic_pinned(label: str, src_headers: list, src_rows: list,
                               expected_headers: list, warnings: list) -> bool:
    """Validate structure of a semantic pinned rows source. Returns True if valid."""
    if src_headers != expected_headers:
        warnings.append(
            f"{label}: headers mismatch — "
            f"expected {expected_headers}, got {src_headers}. Skipping this source."
        )
        return False

    if len(src_rows) != 3:
        warnings.append(
            f"{label}: expected 3 rows, got {len(src_rows)}. Skipping this source."
        )
        return False

    for i, row in enumerate(src_rows):
        if len(row) != 11:
            warnings.append(
                f"{label}: row {i + 1} has {len(row)} cells, expected 11. Skipping this source."
            )
            return False

    return True


def _warn_semantic_consistency(label: str, src_headers: list, src_rows: list,
                                warnings: list) -> tuple[bool, bool]:
    """Emit semantic consistency warnings. Returns (hook_field_empty, semantic_fields_filled)."""
    hook_idx = src_headers.index("Хук / первый экран") if "Хук / первый экран" in src_headers else None
    role_idx = src_headers.index("Роль в воронке")     if "Роль в воронке"     in src_headers else None
    why_idx  = src_headers.index("Почему закреплен")   if "Почему закреплен"   in src_headers else None

    hook_field_empty = True
    # Semantic fields = columns 3..10 (Тема поста … Роль в воронке)
    semantic_cols = list(range(3, 11))
    semantic_fields_filled = any(
        str(row[c]).strip() for row in src_rows for c in semantic_cols if c < len(row)
    )

    for i, row in enumerate(src_rows):
        pos = i + 1

        if hook_idx is not None:
            hook_val = str(row[hook_idx] or "")
            if hook_val.strip():
                warnings.append(
                    f"{label} post {pos}: 'Хук / первый экран' is non-empty "
                    f"('{hook_val[:60]}'). Expected empty after Stage 5A-2C."
                )
                hook_field_empty = False

        if role_idx is not None:
            role_val = str(row[role_idx] or "")
            if role_val.strip():
                atoms = [a.strip().lower() for a in re.split(r"[/,;]", role_val) if a.strip()]
                unknown = [a for a in atoms if a not in _ALLOWED_ROLE_ATOMS]
                if unknown:
                    warnings.append(
                        f"{label} post {pos}: 'Роль в воронке' contains unknown atoms: {unknown}. "
                        "Allowed: знакомство, доверие, прогрев, продажа, лидогенерация."
                    )

                if "доверие" in atoms and why_idx is not None:
                    why_val = str(row[why_idx] or "").lower()
                    if not any(kw in why_val for kw in _TRUST_KEYWORDS):
                        warnings.append(
                            f"{label} post {pos}: role contains 'доверие', but 'Почему закреплен' "
                            "may understate trust rationale. Source row used as-is."
                        )

    return hook_field_empty, semantic_fields_filled


def build_pinned_rows(sources, headers) -> tuple[list, list, dict]:
    """Build rows for 'Закрепленные посты' with priority-based source selection.

    Priority 1: stage5a2c_fixed_rows  (semantic, use as-is)
    Priority 2: stage5a2c_rows        (semantic, use as-is)
    Priority 3: pinned_posts_index    (fallback, semantic fields empty)

    Returns (rows, warnings, pinned_meta).
    pinned_meta keys: source, rows_count, semantic_fields_filled, hook_field_empty, warnings_count.
    """
    warnings = []
    pinned_meta: dict = {
        "source": None,
        "rows_count": 0,
        "semantic_fields_filled": False,
        "hook_field_empty": True,
        "warnings_count": 0,
    }

    # P1 → P2: semantic sources — use rows exactly as-is
    for label in ("stage5a2c_fixed_rows", "stage5a2c_rows"):
        data = sources.get(label)
        if data is None:
            continue

        src_headers = data.get("headers") or []
        src_rows    = data.get("rows")    or []

        if not _validate_semantic_pinned(label, src_headers, src_rows, headers, warnings):
            continue

        # Valid — validate and warn only; do NOT rewrite, infer, enrich, repair or improve values
        hook_empty, sem_filled = _warn_semantic_consistency(label, src_headers, src_rows, warnings)

        pinned_meta.update({
            "source":                label,
            "rows_count":            len(src_rows),
            "semantic_fields_filled": sem_filled,
            "hook_field_empty":      hook_empty,
            "warnings_count":        len(warnings),
        })
        return src_rows, warnings, pinned_meta

    # P3: fallback from pinned_posts_index
    pi_list = _pinned_list(sources)
    pi_raw  = sources.get("pinned_posts_index")

    if not pi_list:
        msg = "pinned_posts_index.json missing or empty; no rows created"
        if isinstance(pi_raw, dict) and pi_raw.get("manual_needed"):
            msg += "; isPinned field absent in actor output — fill pinned_posts_manual.json manually"
        warnings.append(msg)
        pinned_meta.update({
            "source": "pinned_posts_index_fallback",
            "rows_count": 0,
            "warnings_count": len(warnings),
        })
        return [], warnings, pinned_meta

    rows = []
    for item in pi_list:
        url      = _fval(item, "url", "postUrl", "link")
        url_str  = _redact_url(str(url)) if url else ""
        caption  = _fval_str(item, "caption_preview", "caption", "text")
        position = item.get("position")

        row = {
            "Конкурент":           ACCOUNT,
            "Ссылка на пост":      url_str,
            "Позиция закрепа":     str(position) if position is not None else "",
            "Тема поста":          "",
            "Почему закреплен":    "",
            "Хук / первый экран":  "",
            "Что в тексте поста":  caption,
            "Ключевые смыслы":     "",
            "Какой CTA":           "",
            "Куда ведет CTA":      "",
            "Роль в воронке":      "",
        }
        rows.append(_make_row(headers, row))

    warnings.append(
        "Semantic fields (Тема, Почему закреплен, Хук, CTA, Роль) left empty — "
        "pinned_posts_index fallback used; stage5a2c semantic rows not found"
    )
    pinned_meta.update({
        "source":                "pinned_posts_index_fallback",
        "rows_count":            len(rows),
        "semantic_fields_filled": False,
        "hook_field_empty":      True,
        "warnings_count":        len(warnings),
    })
    return rows, warnings, pinned_meta


def build_funnel_rows(sources, headers) -> tuple[list, list]:
    """0 or 1 provisional row if external_url is known."""
    bio      = sources.get("bio_analysis")
    url      = _bio_url(sources)
    warnings = []

    if not url:
        return [], ["No external_url/cta_destination found; no funnel row created"]

    cta_text   = _fval_str(bio, "cta_text", "cta") if bio else ""
    first_step = cta_text if cta_text else "Переход по ссылке в bio"

    row = {h: "" for h in headers}
    row["Конкурент"]    = ACCOUNT
    row["Точка входа"]  = "Instagram-профиль"
    row["Первый шаг"]   = first_step
    row["Куда ведет"]   = _redact_url(url)

    warnings.append(
        "PROVISIONAL: funnel row uses bio URL only. "
        "Destination type not classified (landing/bot/lead_magnet/taplink). "
        "Do not treat as final until link destination classifier runs."
    )
    return [_make_row(headers, row)], warnings


def build_landing_rows(sources, headers) -> tuple[list, list]:
    """0 or 1 provisional row if external_url is known."""
    url      = _bio_url(sources)
    warnings = []

    if not url:
        return [], ["No external_url/cta_destination found; no landing row created"]

    row = {h: "" for h in headers}
    row["Конкурент"]     = ACCOUNT
    row["Ссылка на сайт"] = _redact_url(url)

    warnings.append(
        "PROVISIONAL: bio URL may be Taplink, multilink, bot link, or consultation form — "
        "not confirmed as landing page. "
        "Run link destination classifier before treating this as landing data."
    )
    return [_make_row(headers, row)], warnings


def build_bot_rows(sources, headers) -> tuple[list, list]:
    """No bot data — headers only."""
    return [], ["No bot/lead-magnet source; headers-only CSV created"]


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

_SHEET_BUILDERS = [
    ("Описание профиля",  build_profile_rows),
    ("Анализ хайлайтс",   build_highlights_rows),
    ("Закрепленные посты", build_pinned_rows),
    ("Воронка",            build_funnel_rows),
    ("Лендинг",            build_landing_rows),
    ("Бот  лид-магнит",    build_bot_rows),
]


def build_all_rows(sources, all_headers) -> dict:
    """Returns {sheet_name: {headers, rows, warnings[, pinned_meta]}}."""
    result = {}
    for sheet_name, builder_fn in _SHEET_BUILDERS:
        headers = all_headers.get(sheet_name)
        if not headers:
            result[sheet_name] = {
                "headers": [], "rows": [],
                "warnings": [f"No headers found for sheet '{sheet_name}'"],
            }
            continue
        ret = builder_fn(sources, headers)
        if len(ret) == 3:
            rows, warnings, pinned_meta = ret
            result[sheet_name] = {
                "headers": headers, "rows": rows,
                "warnings": warnings, "pinned_meta": pinned_meta,
            }
        else:
            rows, warnings = ret
            result[sheet_name] = {"headers": headers, "rows": rows, "warnings": warnings}
    return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_sheet_data(sheet_data, sources, all_headers):
    """Raises AssertionError on critical failures."""
    total_cols = sum(len(v) for v in all_headers.values())
    assert total_cols == EXPECTED_TOTAL_COLUMNS, (
        f"Total columns={total_cols} != expected {EXPECTED_TOTAL_COLUMNS}"
    )

    for sname, data in sheet_data.items():
        expected_hdrs = all_headers.get(sname, [])
        if expected_hdrs:
            assert data["headers"] == expected_hdrs, (
                f"Headers mismatch for '{sname}': got {data['headers'][:3]}... "
                f"expected {expected_hdrs[:3]}..."
            )
        for i, row in enumerate(data["rows"]):
            assert len(row) == len(data["headers"]), (
                f"Row {i} in '{sname}' has {len(row)} cells, expected {len(data['headers'])}"
            )

    ps = sources.get("profile_summary")
    if ps is not None:
        n = len(sheet_data["Описание профиля"]["rows"])
        assert n == 1, f"Profile: expected 1 row, got {n}"

    hi_list = _highlights_list(sources)
    if len(hi_list) == 32:
        n = len(sheet_data["Анализ хайлайтс"]["rows"])
        assert n == 32, f"Highlights: expected 32 rows, got {n}"

    pi_raw  = sources.get("pinned_posts_index")
    pi_list = _pinned_list(sources)
    if isinstance(pi_raw, dict) and pi_raw.get("pinned_count") == 3 and len(pi_list) == 3:
        n = len(sheet_data["Закрепленные посты"]["rows"])
        assert n == 3, f"Pinned posts: expected 3 rows, got {n}"


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_payload(sheet_data) -> dict:
    payload = {
        "spreadsheet_id": SPREADSHEET_ID,
        "start_row":      START_ROW,
        "mode":           "preview_only",
        "source":         "stage5d1_local_preview",
        "generated_at":   datetime.utcnow().isoformat() + "Z",
        "notes": [
            "rows 1-2 in Google Sheets = headers/comments; do NOT touch",
            "data writes start at row 3",
            "mode=preview_only: this payload has NOT been sent to Google Sheets",
            "REQUIRED before real write: run Apps Script validate-only step to confirm header match",
        ],
        "sheets": {},
    }
    for sname, data in sheet_data.items():
        # Redact any long URLs in row values for payload
        clean_rows = []
        for row in data["rows"]:
            clean_rows.append([_redact_url(cell, payload_mode=True) for cell in row])
        payload["sheets"][sname] = {
            "headers": data["headers"],
            "rows":    clean_rows,
        }

    payload_str = json.dumps(payload, ensure_ascii=False)
    secrets = _scan_secrets(payload_str)
    if secrets:
        raise ValueError(f"Secrets detected in payload: {secrets}")

    return payload
