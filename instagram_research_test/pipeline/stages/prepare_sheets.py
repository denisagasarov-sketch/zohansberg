"""Stage 15b: собирает sheets_payload.json из normalized/*.json.

Формирует структуру payload["sheets"] для всех листов Google Sheets.
Логика маппинга полей адаптирована из scripts/stage5d1_prepare_sheet_rows.py.
"""

import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from pipeline.core.config import get_account
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_CDN_MARKERS = ("cdninstagram.com", "scontent", "fbcdn.net", "lookaside.fbsbx.com")

# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

PROFILE_HEADERS = [
    "Дата записи", "Конкурент", "Ниша", "Описание bio", "Для кого",
    "Обещание результата", "Позиционирование",
    "Соцдоказательства", "Аргументы доверия",
    "Главный CTA", "Куда ведет CTA",
    "Частота постинга", "Последний пост",
]

PINNED_HEADERS = [
    "Дата записи", "Конкурент", "Ссылка на пост", "Позиция закрепа", "Тема поста",
    "Почему закреплен", "Хук / первый экран", "Что в тексте поста",
    "Ключевые смыслы", "Какой CTA", "Куда ведет CTA", "Роль в воронке",
]

FUNNEL_HEADERS = [
    "Дата записи", "Конкурент", "Полный путь пользователя", "Точка входа", "Первый шаг",
    "Что обещают за переход", "Куда ведет", "Что происходит дальше",
    "Где собирают контакт", "Какой контакт собирают",
    "Через сколько появляется продажа", "Как устроен прогрев",
    "Какие продукты предлагают", "Есть ли tripwire", "Есть ли основной продукт",
    "Есть ли консультация / диагностика", "Какие боли используют",
    "Какие посылы используют", "Какие возражения снимают", "Финальный CTA",
]

LANDING_HEADERS = [
    "Дата записи", "Конкурент", "Ссылка на сайт",
    "Главный заголовок", "Подзаголовок", "Визуальный образ", "Главный CTA",
    "Есть дедлайн", "Как себя называют", "Для кого", "Core Job", "Big Job",
    "Уникальность", "Цифры", "Формат отзывов", "Кейсы", "СМИ", "Сертификаты",
    "Боли", "Возражения", "Есть FAQ", "Название продукта", "Формат продукта",
    "Длительность", "Что входит", "Есть тарифы", "Есть рассрочка", "Есть гарантия",
    "Способ продажи", "Есть ограничение", "Есть бонусы", "Финальный CTA",
    "Нестандартные решения",
]

HIGHLIGHTS_HEADERS = [
    "Дата записи", "Конкурент", "Название highlight", "Порядок",
    "Тема highlight", "Задача highlight", "Что внутри",
    "Механика подачи", "Хук обложки",
    "CTA финальных кадров", "Количество кадров", "Куда ведет CTA",
]

REELS_HEADERS = [
    "Дата записи", "Конкурент", "Ссылка", "Тема", "Хук визуальный", "Формат подачи",
    "Просмотры", "Лайки", "Комментарии", "CTA", "Роль в воронке", "Боль", "Решение",
    "Крючок", "Структура", "Тип хука",
    "Вовлечённость", "Виральность",
    "Закреплён", "Дата", "Длительность", "Хэштеги", "День недели",
]

POSTS_HEADERS = [
    "Дата записи", "Конкурент", "Ссылка на пост", "Заголовок поста",
    "Тема поста", "Рубрика", "Механика подачи", "Кратко о чем пост",
    "Тип хука", "Хук / первый абзац", "Структура поста",
    "Продающая вставка", "Какой CTA", "Куда ведет CTA",
    "Есть лид-магнит", "Какой лид-магнит", "Как получить?",
    "Просмотры", "Лайки", "Комментарии", "Репосты",
    "ERR", "Средний ERR", "ERR выше среднего?",
    "Что могло сработать", "Что можно протестировать у себя",
]

_V2_LANDING_FIELD_MAP = [
    ("glavnyy_zagolovok",   "Главный заголовок"),
    ("podzagolovok",        "Подзаголовок"),
    ("vizualnyy_obraz",     "Визуальный образ"),
    ("glavnyy_cta",         "Главный CTA"),
    ("est_dedlayn",         "Есть дедлайн"),
    ("kak_sebya_nazyvayut", "Как себя называют"),
    ("dlya_kogo",           "Для кого"),
    ("core_job",            "Core Job"),
    ("big_job",             "Big Job"),
    ("unikalnost",          "Уникальность"),
    ("cifry",               "Цифры"),
    ("otzyvy_format",       "Формат отзывов"),
    ("keysy",               "Кейсы"),
    ("media",               "СМИ"),
    ("sertifikaty",         "Сертификаты"),
    ("boli",                "Боли"),
    ("vozrazheniya",        "Возражения"),
    ("est_faq",             "Есть FAQ"),
    ("nazvanie_produkta",   "Название продукта"),
    ("format",              "Формат продукта"),
    ("dlitelnost",          "Длительность"),
    ("chto_vkhodit",        "Что входит"),
    ("est_tarify",          "Есть тарифы"),
    ("est_rassrochka",      "Есть рассрочка"),
    ("est_garantiya",       "Есть гарантия"),
    ("sposob_prodazhi",     "Способ продажи"),
    ("est_ogranichenie",    "Есть ограничение"),
    ("est_bonusy",          "Есть бонусы"),
    ("finalnyy_cta",        "Финальный CTA"),
    ("neobychnye_resheniya","Нестандартные решения"),
]

_RU_DAYS_ACCUSATIVE = [
    "понедельник", "вторник", "среду", "четверг",
    "пятницу", "субботу", "воскресенье",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(headers: list, field_map: dict) -> list:
    return [str(field_map.get(h, "") or "") for h in headers]


def _fval(d, *keys):
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


def _fval_str(d, *keys) -> str:
    val = _fval(d, *keys)
    if val is None:
        return ""
    if isinstance(val, list):
        return ", ".join(str(x) for x in val if x)
    return str(val)


def _redact_url(url) -> str:
    if not isinstance(url, str) or not url.startswith("http"):
        return str(url) if url else ""
    if any(m in url for m in _CDN_MARKERS):
        return "<instagram_cdn_redacted>"
    if len(url) > 120:
        try:
            p = urlparse(url)
            return f"{p.scheme}://{p.netloc}{p.path}"
        except Exception:
            return url[:120] + "..."
    return url


def _join_list(lst, sep=", ") -> str:
    if not lst or not isinstance(lst, list):
        return ""
    return sep.join(str(x) for x in lst if x)


def _field_ok(f) -> str:
    if isinstance(f, dict) and f.get("data_status") == "ok":
        return str(f.get("value") or "").strip()
    return ""


def _fmt_date(raw_ts) -> str:
    if not raw_ts:
        return ""
    try:
        s = str(raw_ts).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return str(raw_ts)[:10]


def _vv_val(fields: dict, field: str) -> str:
    f = fields.get(field, {})
    if isinstance(f, dict) and f.get("data_status") == "ok":
        return f.get("value", "")
    return ""


def _nf(val: str) -> str:
    return val.strip() if val and val.strip() else "не найдено"


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------

_SOURCE_MAP = {
    "profile_summary":    "profile_summary.json",
    "bio_analysis":       "bio_analysis.json",
    "bio_semantic":       "stage5a2e_bio_semantic.json",
    "pinned_posts_index": "pinned_posts_index.json",
    "pinned_sheet_rows":  "stage5a2c_pinned_posts_google_sheet_rows.json",
    "pinned_hooks":       "stage5a2d_pinned_hooks.json",
    "link_destination":   "stage5a2f_link_destination.json",
    "landing_analysis":   "stage5a2g_landing_analysis.json",
    "highlights_index":   "highlights_index.json",
    "highlights_visual":  "stage5b2v_highlights_visual.json",
    "stage5c1_reels":     "stage5c1_reels_index.json",
    "stage5c2_reels":     "stage5c2_reels_analysis.json",
    "stage5e1_posts":     "stage5e1_posts_analysis.json",
}


def _load_sources(username: str) -> dict:
    result = {}
    for key, filename in _SOURCE_MAP.items():
        path = normalized(username, filename)
        if path.exists():
            try:
                result[key] = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning("Не удалось прочитать %s: %s", filename, e)
                result[key] = None
        else:
            result[key] = None
    return result


# ---------------------------------------------------------------------------
# Source extractors
# ---------------------------------------------------------------------------

def _bio_url(sources: dict):
    ld = sources.get("link_destination")
    if isinstance(ld, dict):
        url = (ld.get("url_final") or "").strip()
        if url:
            return url
    ps  = sources.get("profile_summary")
    bio = sources.get("bio_analysis")
    url = _fval(ps, "external_url", "externalUrl") if ps else None
    if not url:
        url = _fval(bio, "cta_destination", "destination") if bio else None
    return str(url) if url else None


def _landing_fields(sources: dict) -> dict:
    raw = sources.get("landing_analysis")
    if not raw or not isinstance(raw, dict):
        return {}
    fields = raw.get("fields", {})
    result = {}
    for key, val in fields.items():
        if isinstance(val, dict) and val.get("data_status") == "ok":
            result[key] = val.get("value", "").strip()
        else:
            result[key] = ""
    return result


def _destination_type(sources: dict) -> str:
    raw = sources.get("link_destination")
    if not raw or not isinstance(raw, dict):
        return ""
    return raw.get("result", {}).get("destination_type", "") or ""


def _followers_count(sources: dict):
    ps = sources.get("profile_summary") or {}
    fc = ps.get("followers_count")
    if isinstance(fc, dict):
        v = fc.get("value")
        return int(v) if v is not None else None
    if isinstance(fc, (int, float)):
        return int(fc)
    return None


def _compute_posting_frequency(username: str) -> str:
    from collections import Counter
    raw_path = raw(username, "stage5a1_posts_for_pinned_raw.json")
    if not raw_path.exists():
        return "не найдено"
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
    except Exception:
        return "не найдено"
    posts = data if isinstance(data, list) else (data.get("posts") or data.get("items") or [])
    dates = []
    for post in posts:
        ts = post.get("timestamp") or post.get("taken_at")
        if not ts:
            continue
        try:
            if isinstance(ts, (int, float)):
                dt = datetime.utcfromtimestamp(float(ts))
            else:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                dt = dt.replace(tzinfo=None)
            dates.append(dt)
        except Exception:
            continue
    if not dates:
        return "не найдено"
    dates.sort()
    first, last = dates[0], dates[-1]
    span_days = max((last - first).days, 1)
    per_week = round(len(dates) / (span_days / 7), 1)
    top_day = _RU_DAYS_ACCUSATIVE[Counter(d.weekday() for d in dates).most_common(1)[0][0]]
    days_ago = (datetime.utcnow() - last).days
    period = f"{first.strftime('%d.%m.%Y')}–{last.strftime('%d.%m.%Y')}"
    return (
        f"{per_week} пост/нед, активнее в {top_day}, "
        f"последний {days_ago} дн. назад "
        f"(выборка: {len(dates)} постов, {period})"
    )


def _last_post_date(username: str) -> str:
    raw_path = raw(username, "stage5a1_posts_for_pinned_raw.json")
    if not raw_path.exists():
        return "не найдено"
    try:
        data = json.loads(raw_path.read_text(encoding="utf-8"))
        posts = data if isinstance(data, list) else (data.get("posts") or data.get("items") or [])
        dts = []
        for p in posts:
            ts = p.get("timestamp") or p.get("taken_at")
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        dt = datetime.utcfromtimestamp(float(ts))
                    else:
                        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                        dt = dt.replace(tzinfo=None)
                    dts.append(dt)
                except Exception:
                    pass
        if dts:
            return max(dts).strftime("%d.%m.%Y")
    except Exception:
        pass
    return "не найдено"


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _build_profile(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    _competitor = username
    ps  = sources.get("profile_summary") or {}
    bio = sources.get("bio_analysis")    or {}

    # Bio-семантика: приоритет стейдж 05 (stage5a2e_bio_semantic.json → fields.<key>.value),
    # fallback на rule-based стейдж 01 (bio_analysis.json), если 05 нет или поле пустое.
    bio_sem    = sources.get("bio_semantic") or {}
    sem_fields = bio_sem.get("fields") if isinstance(bio_sem, dict) else {}
    sem_fields = sem_fields if isinstance(sem_fields, dict) else {}

    _raw_bio = ps.get("bio_text") or {}
    bio_text = str(_raw_bio.get("value") if isinstance(_raw_bio, dict) else _raw_bio).strip()

    def _sem_or_bio(bio_key: str) -> str:
        f = sem_fields.get(bio_key)
        if isinstance(f, dict):
            v = f.get("value")
            if v not in (None, "", []):
                return _join_list(v) if isinstance(v, list) else str(v)
        return _fval_str(bio, bio_key) or ""

    url = _bio_url(sources)
    cta_dest = _sem_or_bio("cta_destination")
    if not cta_dest:
        cta_dest = _redact_url(url) if url else ""

    row = {
        "Дата записи":         datetime.now().strftime("%d.%m.%Y"),
        "Конкурент":           _competitor,
        "Ниша":                _sem_or_bio("niche"),
        "Описание bio":        _nf(bio_text),
        "Для кого":            _sem_or_bio("target_audience"),
        "Обещание результата": _sem_or_bio("result_promise"),
        "Позиционирование":    _sem_or_bio("positioning"),
        "Соцдоказательства":   _sem_or_bio("social_proof"),
        "Аргументы доверия":   _sem_or_bio("trust_arguments"),
        "Главный CTA":         _fval_str(bio, "cta_text", "cta", "main_cta"),
        "Куда ведет CTA":      _nf(cta_dest),
        "Частота постинга":    _compute_posting_frequency(username),
        "Последний пост":      _last_post_date(username),
    }
    return [_make_row(PROFILE_HEADERS, row)], warnings


def _ig_shortcode(url) -> str:
    """Достаёт shortcode из ссылки на пост (.../p/<code>/, .../reel/<code>/) для матчинга."""
    if not isinstance(url, str):
        return ""
    m = re.search(r"/(?:p|reel|tv)/([^/?#]+)", url)
    return m.group(1) if m else ""


def _build_pinned(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    _competitor = username
    pi_raw = sources.get("pinned_posts_index")
    pi_list = []
    if isinstance(pi_raw, dict):
        pi_list = pi_raw.get("pinned_posts") or []
    elif isinstance(pi_raw, list):
        pi_list = pi_raw

    if not pi_list:
        warnings.append("pinned_posts_index.json пусто или отсутствует; нет строк")
        return [], warnings

    # Аналитика закрепов (стейдж 03): rows_as_dicts уже размечен под колонки листа.
    # Матчим по «Позиция закрепа», запасной матч — по shortcode ссылки (число закрепов может меняться).
    sheet_rows    = sources.get("pinned_sheet_rows")
    analysis_rows = sheet_rows.get("rows_as_dicts", []) if isinstance(sheet_rows, dict) else []
    analysis_by_pos, analysis_by_code = {}, {}
    for r in analysis_rows:
        if not isinstance(r, dict):
            continue
        pos = str(r.get("Позиция закрепа", "")).strip()
        if pos:
            analysis_by_pos[pos] = r
        code = _ig_shortcode(r.get("Ссылка на пост"))
        if code:
            analysis_by_code[code] = r
    if not analysis_rows:
        warnings.append("stage5a2c_pinned_posts_google_sheet_rows.json нет; аналитика закрепов пуста")

    # Визуальный анализ карусели (стейдж 04): запасной источник CTA — carousel_cta.
    hooks_raw   = sources.get("pinned_hooks")
    hooks_posts = hooks_raw.get("posts", []) if isinstance(hooks_raw, dict) else []
    hooks_by_pos = {
        str(h.get("position")).strip(): h
        for h in hooks_posts
        if isinstance(h, dict) and h.get("position") is not None
    }

    rows = []
    for item in pi_list:
        url      = _fval(item, "url", "postUrl", "link")
        caption  = _fval_str(item, "caption_preview", "caption", "text")
        position = item.get("position")
        pos_key  = str(position).strip() if position is not None else ""
        code_key = _ig_shortcode(str(url) if url else "")

        a = analysis_by_pos.get(pos_key) or analysis_by_code.get(code_key) or {}
        h = hooks_by_pos.get(pos_key) or {}

        # «Какой CTA»: основной файл часто пуст (CTA фильтруется постобработкой) →
        # запасной carousel_cta из визуального анализа (стейдж 04).
        cta = str(a.get("Какой CTA") or "").strip() or str(h.get("carousel_cta") or "").strip()

        row = {
            "Дата записи":         datetime.now().strftime("%d.%m.%Y"),
            "Конкурент":           _competitor,
            "Ссылка на пост":      _redact_url(str(url)) if url else "",
            "Позиция закрепа":     str(position) if position is not None else "",
            "Тема поста":          str(a.get("Тема поста") or ""),
            "Почему закреплен":    str(a.get("Почему закреплен") or ""),
            "Хук / первый экран":  str(a.get("Хук / первый экран") or ""),
            "Что в тексте поста":  caption,
            "Ключевые смыслы":     str(a.get("Ключевые смыслы") or ""),
            "Какой CTA":           cta,
            "Куда ведет CTA":      "",
            "Роль в воронке":      str(a.get("Роль в воронке") or ""),
        }
        rows.append(_make_row(PINNED_HEADERS, row))

    return rows, warnings


def _build_funnel(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    url = _bio_url(sources)
    if not url:
        return [], ["Нет external_url; строка воронки не создана"]

    lf    = _landing_fields(sources)
    dtype = _destination_type(sources)
    _dest = dtype if dtype else "назначение неизвестно"
    _path_parts = ["Instagram-профиль", "bio-ссылка", _dest]
    _cta = lf.get("glavnyy_cta", "")
    if _cta:
        _path_parts.append(_cta)

    bio       = sources.get("bio_analysis") or {}
    cta_text  = _fval_str(bio, "cta_text", "cta")
    first_step = cta_text if cta_text else "Переход по ссылке в bio"

    row = {h: "" for h in FUNNEL_HEADERS}
    row["Дата записи"]               = datetime.now().strftime("%d.%m.%Y")
    row["Конкурент"]                 = username
    row["Точка входа"]               = "Instagram-профиль"
    row["Первый шаг"]                = first_step
    row["Куда ведет"]                = _redact_url(url)
    row["Полный путь пользователя"]  = " → ".join(_path_parts)
    row["Что обещают за переход"]    = lf.get("obeshchanie_rezultata", "")
    row["Какие продукты предлагают"] = lf.get("chto_prodayut", "")
    row["Какие боли используют"]     = lf.get("boli", "")
    row["Какие посылы используют"]   = lf.get("argumenty", "")
    row["Финальный CTA"]             = lf.get("glavnyy_cta", "")

    return [_make_row(FUNNEL_HEADERS, row)], warnings


def _build_landing(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    _competitor = username
    url = _bio_url(sources)
    if not url:
        return [], ["Нет external_url; строка лендинга не создана"]

    landing_raw = sources.get("landing_analysis")
    if not landing_raw or not isinstance(landing_raw, dict):
        return [], ["stage5a2g_landing_analysis.json отсутствует; лист Лендинг пропущен"]

    fields_new = landing_raw.get("fields_new") or {}

    def gv(key: str) -> str:
        f = fields_new.get(key) or {}
        status = f.get("data_status", "not_found")
        value = str(f.get("value") or "").strip()
        if not value or status == "not_found":
            if key == "otzyvy_format":
                return "не удалось извлечь (графический блок)"
            return "не найдено"
        return value

    row = {
        "Дата записи":    datetime.now().strftime("%d.%m.%Y"),
        "Конкурент":      _competitor,
        "Ссылка на сайт": _redact_url(url),
    }
    for key, header in _V2_LANDING_FIELD_MAP:
        row[header] = gv(key)

    return [_make_row(LANDING_HEADERS, row)], warnings


def _build_highlights(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    _competitor = username

    visual_data = sources.get("highlights_visual")
    if not visual_data or not isinstance(visual_data, dict):
        warnings.append("stage5b2v_highlights_visual.json отсутствует; Хайлайты пропущены")
        return [], warnings

    analyzed = visual_data.get("analyzed_highlights", [])
    if not analyzed:
        warnings.append("analyzed_highlights пуст; Хайлайты пропущены")
        return [], warnings

    def _fv(h: dict, key: str) -> str:
        f = h.get("fields", {}).get(key) or {}
        status = f.get("data_status", "not_found")
        value = str(f.get("value") or "")
        return "не найдено" if (not value or status == "not_found") else value

    rows = []
    for h in analyzed:
        if h.get("skipped"):
            continue
        cta_targeted = h.get("cta_targeted") or {}
        cta_final = str(cta_targeted.get("text") or "").strip()
        if cta_final.lower() in ("not_found", "не найдено", "нет cta", "cta не найден", ""):
            cta_final = "CTA не найден"
        row = {
            "Дата записи":          datetime.now().strftime("%d.%m.%Y"),
            "Конкурент":            _competitor,
            "Название highlight":   h.get("title", ""),
            "Порядок":              str(h.get("position", "")),
            "Тема highlight":       _fv(h, "tema"),
            "Задача highlight":     _fv(h, "zadacha"),
            "Что внутри":           _fv(h, "chto_vnutri"),
            "Механика подачи":      _fv(h, "mekhanika"),
            "Хук обложки":          "",
            "CTA финальных кадров": cta_final,
            "Количество кадров":    "",
            "Куда ведет CTA":       _fv(h, "cta"),
        }
        rows.append(_make_row(HIGHLIGHTS_HEADERS, row))

    if not rows:
        warnings.append("Все хайлайты пропущены в visual analysis; нет строк")
    return rows, warnings


def _build_reels(sources: dict, username: str) -> tuple[list, list]:
    warnings = []
    _competitor = username

    reels_raw = sources.get("stage5c2_reels")
    if not reels_raw or not isinstance(reels_raw, dict):
        warnings.append("stage5c2_reels_analysis.json отсутствует; Reels пропущены")
        return [], warnings

    reels = reels_raw.get("reels") or []
    if not reels:
        warnings.append("reels пуст в stage5c2_reels_analysis.json; Reels пропущены")
        return [], warnings

    _c1_by_id: dict = {}
    _c1_raw = sources.get("stage5c1_reels")
    if isinstance(_c1_raw, dict):
        for r in (_c1_raw.get("reels") or []):
            rid = r.get("reel_id") or r.get("id") or ""
            if rid:
                _c1_by_id[str(rid)] = r

    _followers = _followers_count(sources)

    rows = []
    for r in reels:
        reel_id = str(r.get("reel_id") or "")
        url     = r.get("url") or ""
        _c1     = _c1_by_id.get(reel_id, {})

        views     = _c1.get("view_count")    if _c1 else r.get("view_count")
        likes     = _c1.get("likes_count")   if _c1 else r.get("likes_count")
        is_pinned = _c1.get("is_pinned")     if _c1 else r.get("is_pinned")
        published = _fmt_date(_c1.get("timestamp") if _c1 else r.get("published_at"))

        _views_int = views if isinstance(views, (int, float)) else 0
        virality = (
            f"{(_views_int / _followers * 100):.1f}%"
            if (_followers and _views_int)
            else ""
        )

        comments_raw = _c1.get("comments_count") if _c1 else None
        duration_raw = _c1.get("video_duration")  if _c1 else None

        row = {
            "Дата записи":    datetime.now().strftime("%d.%m.%Y"),
            "Конкурент":      _competitor,
            "Ссылка":         _redact_url(url) if url else "",
            "Тема":           _field_ok(r.get("tema"))          or "не найдено",
            "Хук визуальный": _field_ok(r.get("hook"))          or "не найдено",
            "Формат подачи":  _field_ok(r.get("vizual_format")) or "не найдено",
            "Просмотры":      str(views)     if views    is not None else "",
            "Лайки":          str(likes)     if likes    is not None else "",
            "Комментарии":    str(comments_raw) if comments_raw is not None else "",
            "CTA":            _field_ok(r.get("cta"))           or "не найдено",
            "Роль в воронке": _field_ok(r.get("rol_v_voronke")) or "не найдено",
            "Боль":           _field_ok(r.get("bol"))           or "не найдено",
            "Решение":        _field_ok(r.get("reshenie"))      or "не найдено",
            "Крючок":         _field_ok(r.get("kryuchok"))      or "не найдено",
            "Структура":      _field_ok(r.get("struktura"))     or "не найдено",
            "Тип хука":       _field_ok(r.get("hook_type"))     or "не найдено",
            "Вовлечённость":  r.get("engagement_rate") or "",
            "Виральность":    virality,
            "Закреплён":      "да" if is_pinned else "нет",
            "Дата":           published,
            "Длительность":   f"{int(duration_raw)}с" if duration_raw else "",
            "Хэштеги":        _c1.get("hashtags", "")   if _c1 else "",
            "День недели":    _c1.get("day_of_week", "") if _c1 else "",
        }
        rows.append(_make_row(REELS_HEADERS, row))

    return rows, warnings


def _build_posts(sources: dict, username: str) -> tuple[list, list]:
    warnings = []

    acc = get_account(username)
    allowed_types = set(acc.get("posts_sheet_types", ["photo", "carousel"]))

    posts_raw = sources.get("stage5e1_posts")
    if not posts_raw or not isinstance(posts_raw, dict):
        warnings.append("stage5e1_posts_analysis.json отсутствует; Посты пропущены")
        return [], warnings

    input_rows = posts_raw.get("rows") or []
    if not input_rows:
        warnings.append("rows пуст в stage5e1_posts_analysis.json; Посты пропущены")
        return [], warnings

    rows = []
    skipped = 0
    for r in input_rows:
        if not isinstance(r, dict):
            continue
        post_type = r.get("post_type", "")
        if post_type not in allowed_types:
            skipped += 1
            continue
        rows.append(_make_row(POSTS_HEADERS, {"Дата записи": datetime.now().strftime("%d.%m.%Y"), **r}))

    if skipped:
        warnings.append(
            f"{skipped} строк исключено по posts_sheet_types "
            f"(разрешены: {sorted(allowed_types)})"
        )
    return rows, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_SHEET_BUILDERS = [
    ("Описание профиля",   _build_profile,    PROFILE_HEADERS),
    ("Закрепленные посты", _build_pinned,     PINNED_HEADERS),
    ("Воронка",            _build_funnel,     FUNNEL_HEADERS),
    ("Лендинг",            _build_landing,    LANDING_HEADERS),
    ("Анализ хайлайтс",    _build_highlights, HIGHLIGHTS_HEADERS),
    ("Reels",              _build_reels,      REELS_HEADERS),
    ("Посты",              _build_posts,      POSTS_HEADERS),
]


def prepare(username: str, dry_run: bool = False) -> dict:
    """Формирует sheets_payload.json из normalized/*.json."""
    get_account(username)
    logger.info("[15b] prepare_sheets | @%s | dry_run=%s", username, dry_run)

    if dry_run:
        logger.info("[DRY RUN] Файлы не записываются")
        return {"dry_run": True, "sheets": {}}

    sources = _load_sources(username)
    loaded = [k for k, v in sources.items() if v is not None]
    missing = [k for k, v in sources.items() if v is None]
    logger.info("Загружено источников: %d, отсутствует: %d (%s)",
                len(loaded), len(missing), ", ".join(missing) if missing else "—")

    sheets = {}
    all_warnings = []
    for sheet_name, builder, headers in _SHEET_BUILDERS:
        try:
            rows, warns = builder(sources, username)
        except Exception as e:
            logger.error("Ошибка при сборке листа '%s': %s", sheet_name, e)
            rows, warns = [], [f"Ошибка: {e}"]
        sheets[sheet_name] = {"headers": headers, "rows": rows}
        if warns:
            all_warnings.extend([f"[{sheet_name}] {w}" for w in warns])
            for w in warns:
                logger.warning("  [%s] %s", sheet_name, w)

    payload = {
        "account":      username,
        "stage":        "stage15b",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sheets":       sheets,
        "warnings":     all_warnings,
    }

    out_path = normalized(username, "sheets_payload.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    total_rows = sum(len(s["rows"]) for s in sheets.values())
    print(f"\n=== Stage 15b: Prepare Sheets | @{username} ===")
    for name, data in sheets.items():
        print(f"  {name}: {len(data['rows'])} строк")
    print(f"Итого строк: {total_rows} | Предупреждений: {len(all_warnings)}")
    print(f"Сохранено: {out_path}")

    return payload
