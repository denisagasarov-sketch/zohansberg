"""Telegram bot for Instagram competitor research pipeline."""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters, ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

BASE            = Path(__file__).parent.parent.parent  # zohansberg-instagram-test/
RESEARCH_DIR    = BASE / "instagram_research_test"
ACCOUNTS_PATH   = RESEARCH_DIR / "data" / "accounts.json"
RUN_PY          = RESEARCH_DIR / "run.py"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
SHEET_TAB_POSTS = f"{SPREADSHEET_URL}#gid=0"

load_dotenv(RESEARCH_DIR / ".env", override=True)

# ---------------------------------------------------------------------------
# Global job state (one job at a time)
# ---------------------------------------------------------------------------
current_job: dict = {
    "running": False,
    "account": None,
    "started_at": None,
    "chat_id": None,
    "apify_balance_before": None,
    "progress_msg_id": None,
}

# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def get_allowed_ids() -> set:
    raw = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()} if raw.strip() else set()


def is_allowed(update: Update) -> bool:
    return update.effective_chat.id in get_allowed_ids()


def validate_username(username: str) -> str | None:
    username = username.lstrip("@").strip()
    return username if re.match(r'^[a-zA-Z0-9._]{1,30}$', username) else None


def _valid_account(uname) -> bool:
    """True только для реального username (защита от '?' при потере контекста)."""
    return bool(uname) and bool(re.match(r'^[a-zA-Z0-9._]{1,30}$', str(uname)))

# ---------------------------------------------------------------------------
# accounts.json helpers
# ---------------------------------------------------------------------------

def _load_accounts() -> list[dict]:
    try:
        data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
        return data.get("accounts", [])
    except Exception:
        return []


def _ensure_account(username: str) -> None:
    # Защита от мусорных записей вида "?" — только валидные username.
    if not re.match(r'^[a-zA-Z0-9._]{1,30}$', username or ""):
        logger.warning("Skip _ensure_account: invalid username %r", username)
        return
    try:
        data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
        existing = [a["username"] for a in data.get("accounts", [])]
        if username not in existing:
            data.setdefault("accounts", []).append({
                "username": username,
                "url": f"https://www.instagram.com/{username}/",
            })
            ACCOUNTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Added %s to accounts.json", username)
    except Exception as e:
        logger.warning("Could not update accounts.json: %s", e)

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------

_BLOCK_LABELS = {
    "01-04": "Профиль и закрепы (01-04)",
    "05":    "Bio анализ (05)",
    "06-07": "Ссылка и лендинг (06-07)",
    "08-10": "Хайлайты (08-10)",
    "11-12": "Reels (11-12)",
    "13-14": "Посты (13-14)",
}
_BLOCK_STAGES = {
    "01-04": ["01", "02", "03", "04"],
    "05":    ["05"],
    "06-07": ["06", "07"],
    "08-10": ["08", "09", "10"],
    "11-12": ["11", "12"],
    "13-14": ["13", "14"],
}
_SHEET_LABELS = {
    "prof": "Описание профиля",
    "pins": "Закрепы",
    "hi":   "Хайлайты",
    "re":   "Reels",
    "po":   "Посты",
    "fu":   "Воронка",
    "la":   "Лендинг",
}

# ---------------------------------------------------------------------------
# Account summary helpers
# ---------------------------------------------------------------------------

def _format_followers(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n) if n else "—"
    if n >= 1_000_000:
        val = f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{val}M"
    if n >= 1_000:
        val = f"{n / 1_000:.1f}".rstrip("0").rstrip(".")
        return f"{val}K"
    return str(n)


# Группы блоков для сводки: (ключи meta.json, отображаемое название)
_SUMMARY_BLOCKS = [
    (["profile", "bio"], "Профиль и bio"),
    (["pinned"],         "Закрепы"),
    (["highlights"],     "Хайлайты"),
    (["reels"],          "Reels"),
    (["posts"],          "Посты"),
    (["landing"],        "Лендинг"),
]

# Листы таблицы в порядке важности для короткой строки
_SHEET_DISPLAY_ORDER = [
    ("Посты",              "Посты"),
    ("Reels",              "Reels"),
    ("Закрепленные посты", "Закрепы"),
    ("Описание профиля",   "Профиль"),
]


def _read_profile_brief(username: str) -> tuple[str, str]:
    """Возвращает (full_name, followers_str) из profile_summary.json."""
    full_name = ""
    followers_str = ""
    try:
        p = RESEARCH_DIR / "data" / username / "normalized" / "profile_summary.json"
        if p.exists():
            ps = json.loads(p.read_text(encoding="utf-8"))
            fn = ps.get("full_name", {})
            full_name = fn.get("value", "") if isinstance(fn, dict) else str(fn)
            fc = ps.get("followers_count", {})
            fc_val = fc.get("value") if isinstance(fc, dict) else fc
            followers_str = _format_followers(fc_val)
    except Exception:
        pass
    return full_name, followers_str


# ---------------------------------------------------------------------------
# Live sheet counts — «В таблице: N» читаем прямо из Google Sheets
# (mode get_sheet_data), а не из локального sheets_payload.json.
# ---------------------------------------------------------------------------

_SHEET_COUNT_TTL         = 15.0  # сек: кэш, чтобы не дёргать таблицу на каждый рендер экрана
_SHEET_COUNT_TIMEOUT     = 15.0  # сек: бюджет ОДНОГО запроса (запросы идут последовательно)
_SHEET_COUNT_RETRY_DELAY = 2.0   # сек: пауза перед ретраем, если первое чтение пустое (гонка после записи)
_SHEET_COUNT_CACHE: dict[str, tuple[float, dict]] = {}


async def _fetch_competitor_count(client, url, body_base: dict, sheet_name: str, username: str) -> int | None:
    """Число строк листа, где колонка «Конкурент» == username. None — лист недоступен."""
    try:
        r = await client.post(url, json={
            **body_base, "mode": "get_sheet_data",
            "sheet_name": sheet_name, "column": "Конкурент",
        })
        data = r.json()
        if not data.get("ok"):
            logger.warning("get_sheet_data ok=false: лист '%s' @%s — %s",
                           sheet_name, username, data.get("errors") or data)
            return None
        needle = username.strip()
        return sum(1 for v in (data.get("data") or []) if str(v).strip() == needle)
    except Exception as e:
        logger.warning("get_sheet_data ошибка: лист '%s' @%s — %s: %s",
                       sheet_name, username, type(e).__name__, e)
        return None


async def _read_sheet_counts_live(username: str) -> dict:
    """{имя_листа: число_строк_аккаунта} из ЖИВОЙ таблицы (mode get_sheet_data).

    Матчит строки по колонке «Конкурент» == username. Значение None означает, что
    лист недоступен (таймаут/ошибка) — экран покажет «—». Результат кэшируется на
    _SHEET_COUNT_TTL секунд, чтобы не дёргать таблицу на каждый рендер экрана.
    """
    sheets = [name for name, _ in _SHEET_DISPLAY_ORDER]
    now = time.monotonic()
    cached = _SHEET_COUNT_CACHE.get(username)
    if cached and now - cached[0] < _SHEET_COUNT_TTL:
        return cached[1]

    url = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "")
    if not url:
        logger.warning("Live sheet counts: GOOGLE_SHEETS_WEBAPP_URL не задан")
        return {name: None for name in sheets}

    body_base = {
        "secret": os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", ""),
        "spreadsheet_id": os.environ.get(
            "GOOGLE_SHEETS_SPREADSHEET_ID", "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
        ),
    }

    async def _read_once() -> dict:
        out = {name: None for name in sheets}
        try:
            async with httpx.AsyncClient(timeout=_SHEET_COUNT_TIMEOUT) as client:
                # ПОСЛЕДОВАТЕЛЬНО: Apps Script single-threaded, при параллели поздние
                # запросы стоят в очереди и упираются в общий дедлайн → таймаут → «—».
                for name in sheets:
                    out[name] = await _fetch_competitor_count(client, url, body_base, name, username)
        except Exception as e:
            logger.warning("Live sheet counts failed for @%s: %s", username, e)
        return out

    counts = await _read_once()
    # Ретрай при полном провале — типично сразу после записи (лок/холодный старт Apps Script).
    if all(v is None for v in counts.values()):
        logger.info("Live sheet counts @%s: пусто, ретрай через %.0fс", username, _SHEET_COUNT_RETRY_DELAY)
        await asyncio.sleep(_SHEET_COUNT_RETRY_DELAY)
        counts = await _read_once()

    # Кэшируем ТОЛЬКО удачное чтение, чтобы не залипли прочерки на _SHEET_COUNT_TTL секунд.
    if any(v is not None for v in counts.values()):
        _SHEET_COUNT_CACHE[username] = (now, counts)
    return counts


def _get_account_summary(username: str, sheet_counts: dict) -> str:
    meta = _read_meta(username)
    full_name, followers_str = _read_profile_brief(username)

    lines = [f"📋 @{username}"]
    profile_parts = []
    if full_name:
        profile_parts.append(f"👤 {full_name}")
    if followers_str:
        profile_parts.append(f"{followers_str} подписчиков")
    if profile_parts:
        lines.append(" | ".join(profile_parts))

    lines.append("\n📅 Последние обновления:")
    for block_keys, label in _SUMMARY_BLOCKS:
        dates = [meta[k] for k in block_keys if k in meta]
        if dates:
            latest = max(dates)
            date_display = latest.split(" ")[0] if " " in latest else latest
            lines.append(f"✅ {label} — {date_display}")
        else:
            lines.append(f"⚠️ {label} — нет данных")

    table_parts = []
    for sheet_key, short_name in _SHEET_DISPLAY_ORDER:
        count = sheet_counts.get(sheet_key)
        table_parts.append(f"{short_name}: {count if count is not None else '—'}")
    lines.append("\n📊 В таблице:")
    lines.append("  " + " | ".join(table_parts))

    return "\n".join(lines)


def _accounts_list_text() -> str:
    accounts = _load_accounts()
    if not accounts:
        return "Нет аккаунтов. Добавьте первый:"

    lines = ["Выберите аккаунт для анализа:\n"]
    for acc in accounts[:10]:
        uname = acc.get("username", "")
        data_dir = RESEARCH_DIR / "data" / uname / "normalized"

        has_data = False
        latest_date = ""
        try:
            p = data_dir / "meta.json"
            if p.exists():
                meta = json.loads(p.read_text(encoding="utf-8"))
                if meta:
                    has_data = True
                    latest = max(meta.values())
                    parts = latest.split(".")
                    if len(parts) >= 2:
                        latest_date = f"{parts[0]}.{parts[1]}"
        except Exception:
            pass

        sheet_parts = []
        try:
            p = data_dir / "sheets_payload.json"
            if p.exists():
                sp = json.loads(p.read_text(encoding="utf-8"))
                sheets = sp.get("sheets", {})
                for sheet_key, short_name in _SHEET_DISPLAY_ORDER[:3]:
                    sd = sheets.get(sheet_key, {})
                    n = len(sd.get("rows", [])) if isinstance(sd, dict) else 0
                    if n:
                        sheet_parts.append(f"{short_name} {n}")
        except Exception:
            pass

        status = "✅" if has_data else "⚪"
        header = f"@{uname} {status}"
        if latest_date:
            header += f" — {latest_date}"
        lines.append(header)
        if sheet_parts:
            lines.append("  " + " | ".join(sheet_parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Account screen: freshness of data blocks (mirror of pipeline/core/meta.py)
# ---------------------------------------------------------------------------

# TTL в днях, синхронизировано с pipeline/core/meta.py BLOCK_TTL_DAYS
_BLOCK_TTL_DAYS = {
    "profile": 30, "pinned": 30, "bio": 30, "landing": 30,
    "highlights": 14, "reels": 7, "posts": 7,
}

# Порядок и подписи 7 блоков на экране аккаунта
_BLOCK_ORDER = [
    ("profile",    "Профиль"),
    ("pinned",     "Закрепы"),
    ("bio",        "Bio"),
    ("landing",    "Лендинг"),
    ("highlights", "Хайлайты"),
    ("reels",      "Reels"),
    ("posts",      "Посты"),
]

# Блок → стейджи (инверсия STAGE_TO_BLOCK из meta.py)
_BLOCK_TO_STAGES = {
    "profile":    ["01"],
    "pinned":     ["02", "03", "04"],
    "bio":        ["05"],
    "landing":    ["06", "07"],
    "highlights": ["08", "09", "10"],
    "reels":      ["11", "12"],
    "posts":      ["13", "14"],
}

# Канонический порядок стейджей для сортировки выборки
_ALL_STAGES_ORDER = [
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "15b", "16",
]


def _read_meta(username: str) -> dict:
    try:
        p = RESEARCH_DIR / "data" / username / "normalized" / "meta.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _block_freshness(username: str) -> dict:
    """block -> (state, date_str): state ∈ {'fresh', 'stale', 'none'}."""
    meta = _read_meta(username)
    result = {}
    for block, ttl in _BLOCK_TTL_DAYS.items():
        last = meta.get(block)
        if not last:
            result[block] = ("none", None)
            continue
        try:
            dt = datetime.strptime(last, "%d.%m.%Y %H:%M")
            days = (datetime.now() - dt).days
            result[block] = ("stale" if days >= ttl else "fresh", last.split(" ")[0])
        except Exception:
            result[block] = ("stale", last)
    return result


def _stages_for_blocks(blocks: list[str]) -> list[str]:
    """Стейджи для набора блоков + обязательные 15/15b/16, в каноническом порядке."""
    wanted = set()
    for b in blocks:
        wanted.update(_BLOCK_TO_STAGES.get(b, []))
    wanted.update(["15", "15b", "16"])
    return [s for s in _ALL_STAGES_ORDER if s in wanted]


# ---------------------------------------------------------------------------
# Группы листов для выбора сбора (5 штук): подпись + стейджи + блоки meta.
# ---------------------------------------------------------------------------
_GROUPS = [
    ("profile",    "👤 Профиль и закрепы", ["01", "02", "03", "04", "05"], ["profile", "pinned", "bio"]),
    ("landing",    "🔗 Лендинг и воронка", ["06", "07"],                   ["landing"]),
    ("highlights", "✨ Хайлайты",          ["08", "09", "10"],             ["highlights"]),
    ("reels",      "🎬 Reels",             ["11", "12"],                   ["reels"]),
    ("posts",      "📝 Посты",             ["13", "14"],                   ["posts"]),
]
_GROUP_KEYS   = [g[0] for g in _GROUPS]
_GROUP_LABEL  = {g[0]: g[1] for g in _GROUPS}
_GROUP_STAGES = {g[0]: g[2] for g in _GROUPS}
_GROUP_BLOCKS = {g[0]: g[3] for g in _GROUPS}
# Apify-стоимость на группу (OpenAI считается по стейджам из _OPENAI_COSTS)
_GROUP_APIFY  = {"profile": 0.05, "landing": 0.0, "highlights": 0.10, "reels": 0.05, "posts": 0.10}


def _selected_groups(settings: dict) -> list[str]:
    groups = settings.get("groups") or {}
    return [k for k in _GROUP_KEYS if groups.get(k)]


def _stages_for_groups(group_keys: list[str]) -> list[str]:
    """Стейджи для выбранных групп + обязательные 15/15b/16, в каноническом порядке.

    Группа «Лендинг» (06/07) требует profile_summary.json (стейдж 01): если
    выбрана landing, но не profile — тихо подтягиваем 01, чтобы 06 не упал.
    """
    wanted = set()
    for gk in group_keys:
        wanted.update(_GROUP_STAGES.get(gk, []))
    if "landing" in group_keys and "profile" not in group_keys:
        wanted.add("01")
    wanted.update(["15", "15b", "16"])
    return [s for s in _ALL_STAGES_ORDER if s in wanted]


def _ddmmyyyy_key(dstr: str):
    try:
        return datetime.strptime(dstr, "%d.%m.%Y")
    except Exception:
        return datetime.min


def _short_date(dstr: str) -> str:
    """'24.06.2026' -> '24.06' для компактной свежести по группам."""
    parts = (dstr or "").split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else dstr


def _account_screen_text(username: str, sheet_counts: dict) -> str:
    full_name, followers_str = _read_profile_brief(username)
    fresh = _block_freshness(username)

    lines = [f"📋 @{username}"]
    head = []
    if full_name:
        head.append(f"👤 {full_name}")
    if followers_str:
        head.append(f"{followers_str} подписчиков")
    if head:
        lines.append(" | ".join(head))

    lines.append("\n🗂 Свежесть данных:")
    for gk in _GROUP_KEYS:
        # самая свежая дата среди блоков группы; ⚠️ если хоть один блок устарел
        dated = []
        for b in _GROUP_BLOCKS[gk]:
            st, ds = fresh.get(b, ("none", None))
            if ds:
                dated.append((st, ds))
        if dated:
            latest = max((ds for _, ds in dated), key=_ddmmyyyy_key)
            stale  = any(st == "stale" for st, _ in dated)
            lines.append(f"{_GROUP_LABEL[gk]} — {_short_date(latest)}" + (" ⚠️" if stale else ""))
        else:
            lines.append(f"{_GROUP_LABEL[gk]} — нет данных")

    table_parts = []
    for sheet_key, short in _SHEET_DISPLAY_ORDER:
        c = sheet_counts.get(sheet_key)
        table_parts.append(f"{short}: {c if c is not None else '—'}")
    lines.append("\n📊 В таблице: " + " | ".join(table_parts))

    lines.append("\n──────────────")
    lines.append("🔄 Собрать заново — полный анализ, данные в таблице обновятся")
    lines.append("➕ Добавить новые посты — только посты которых ещё нет в таблице")
    lines.append("⚡ Быстрое обновление — пересобрать только устаревшие блоки")
    lines.append("⚙️ Выбрать что собирать — группы листов и режим записи")

    return "\n".join(lines)


def _account_screen_keyboard(username: str, fresh: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("⚡ Быстрое обновление", callback_data=f"accrun:stale:{username}")],
        [
            InlineKeyboardButton("🔄 Собрать заново",        callback_data=f"accrun:all:{username}"),
            InlineKeyboardButton("➕ Добавить новые посты",  callback_data=f"accrun:append:{username}"),
        ],
        [InlineKeyboardButton("⚙️ Выбрать что собирать", callback_data=f"acc:{username}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"accdel:{username}")],
        [
            InlineKeyboardButton("❓ Справка", callback_data=f"help:account:{username}"),
            InlineKeyboardButton("← Назад",   callback_data="show_accounts"),
        ],
    ]
    return InlineKeyboardMarkup(rows)


# ---------------------------------------------------------------------------
# Account deletion (path-traversal safe)
# ---------------------------------------------------------------------------

def _safe_account_dir(username: str) -> Path | None:
    """Возвращает data/<username>/ только если имя валидно и путь внутри data/."""
    if not re.match(r'^[a-zA-Z0-9._]{1,30}$', username):
        return None
    data_root = (RESEARCH_DIR / "data").resolve()
    target = (data_root / username).resolve()
    if target == data_root or data_root not in target.parents:
        return None
    return target


def _remove_account_from_json(username: str) -> bool:
    try:
        data = json.loads(ACCOUNTS_PATH.read_text(encoding="utf-8"))
        before = data.get("accounts", [])
        after = [a for a in before if a.get("username") != username]
        if len(after) == len(before):
            return False
        data["accounts"] = after
        ACCOUNTS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        logger.warning("Could not remove %s from accounts.json: %s", username, e)
        return False


async def _delete_account_from_sheets(username: str) -> tuple[bool, int, str]:
    url            = os.environ.get("GOOGLE_SHEETS_WEBAPP_URL", "")
    secret         = os.environ.get("GOOGLE_SHEETS_SYNC_SECRET", "")
    spreadsheet_id = os.environ.get(
        "GOOGLE_SHEETS_SPREADSHEET_ID", "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"
    )
    if not url:
        return (False, 0, "GOOGLE_SHEETS_WEBAPP_URL не задан в .env")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json={
                "secret": secret,
                "mode": "delete_account",
                "spreadsheet_id": spreadsheet_id,
                "account_label": username,
            })
            data = r.json()
            ok = bool(data.get("ok"))
            deleted = int(data.get("deleted_rows_total", 0) or 0)
            err = "; ".join(data.get("errors", []) or [])
            return (ok, deleted, err)
    except Exception as e:
        return (False, 0, str(e))


# Apify cost estimates per block (USD)
_APIFY_COSTS = {"01-04": 0.05, "08-10": 0.10, "11-12": 0.05, "13-14": 0.10}
# OpenAI cost estimates per block (USD)
_OPENAI_COSTS = {"03": 0.05, "04": 0.03, "05": 0.02, "07": 0.05, "10": 0.08, "12": 0.08, "14": 0.15}


def _default_settings() -> dict:
    return {
        "groups":         {k: True for k in _GROUP_KEYS},
        "target_count":   30,           # сколько последних постов собирать (фото+карусель)
        "content_filter": "all",
        "write_mode":     "replace",
    }


def _get_settings(context: ContextTypes.DEFAULT_TYPE) -> dict:
    s = context.user_data.get("settings")
    # Миграция старого стейта (blocks/period/types) → новая схема групп.
    if not isinstance(s, dict) or "groups" not in s:
        s = _default_settings()
        context.user_data["settings"] = s
    return s


def _build_stages_list(settings: dict) -> list[str]:
    return _stages_for_groups(_selected_groups(settings))

# ---------------------------------------------------------------------------
# Cost estimate
# ---------------------------------------------------------------------------

def _estimate_cost(settings: dict) -> str:
    apify_total  = 0.0
    openai_total = 0.0
    apify_parts  = []
    openai_parts = []

    for gk in _selected_groups(settings):
        a = _GROUP_APIFY.get(gk, 0.0)
        if a:
            apify_total += a
            apify_parts.append(f"{_GROUP_LABEL[gk]} ${a:.2f}")
        for stage in _GROUP_STAGES[gk]:
            o = _OPENAI_COSTS.get(stage, 0)
            if o:
                openai_total += o
                openai_parts.append(f"{_GROUP_LABEL[gk]} · stage {stage} ${o:.2f}")

    lines = ["💰 Смета:"]
    if apify_parts:
        lines.append(f"Apify: ~${apify_total:.2f}\n  " + "\n  ".join(apify_parts))
    else:
        lines.append("Apify: $0 (Apify не используется)")
    if openai_parts:
        lines.append(f"OpenAI: ~${openai_total:.2f}\n  " + "\n  ".join(openai_parts))
    else:
        lines.append("OpenAI: $0")
    lines.append(f"Итого: ~${apify_total + openai_total:.2f}")
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# Settings screen builders
# ---------------------------------------------------------------------------

def _ck(val: bool) -> str:
    return "☑" if val else "☐"


def _settings_text(username: str, settings: dict) -> str:
    wm = settings.get("write_mode", "replace")
    mode_line = ("Перезаписать — заменить строки аккаунта"
                 if wm == "replace" else "Дополнить — дописать без удаления")
    return (
        f"⚙️ Что собрать — @{username}\n\n"
        f"Отмечены группы листов для обновления (по умолчанию — все).\n"
        f"Сними галочку с того, что обновлять не нужно.\n\n"
        f"Режим: {mode_line}."
    )


def _settings_keyboard(username: str, settings: dict) -> InlineKeyboardMarkup:
    groups = settings.get("groups") or {}
    wm     = settings.get("write_mode", "replace")
    cnt    = settings.get("target_count", 30)

    # 5 групп — чекбоксы с явным ВКЛ/выкл (по умолчанию все включены)
    rows = [
        [InlineKeyboardButton(
            f"{'☑️ ВКЛ ·' if groups.get(k) else '⬜ выкл ·'} {_GROUP_LABEL[k]}",
            callback_data=f"grp:{k}")]
        for k in _GROUP_KEYS
    ]
    # Количество постов — подэкран
    rows.append([InlineKeyboardButton(f"📝 Постов: {cnt} ▸", callback_data="cntmenu")])
    # Режим записи — два тоггла
    rows.append([
        InlineKeyboardButton("🔄 Перезаписать ✓" if wm == "replace" else "🔄 Перезаписать",
                             callback_data="wm:replace"),
        InlineKeyboardButton("➕ Дополнить ✓" if wm == "append" else "➕ Дополнить",
                             callback_data="wm:append"),
    ])
    rows.append([InlineKeyboardButton("🚀 Запустить", callback_data="action:launch")])
    rows.append([
        InlineKeyboardButton("💰 Смета", callback_data="action:estimate"),
        InlineKeyboardButton("← Назад",  callback_data=f"accview:{username}"),
    ])
    return InlineKeyboardMarkup(rows)


def _count_text(username: str, settings: dict) -> str:
    return (
        f"📝 Сколько последних постов собирать — @{username}\n\n"
        f"Сейчас: {settings.get('target_count', 30)}.\n"
        f"Берём последние N постов (фото + карусель), без привязки к периоду."
    )


def _count_keyboard(username: str, settings: dict) -> InlineKeyboardMarkup:
    cur = settings.get("target_count", 30)

    def b(n):
        return InlineKeyboardButton(f"[{n}]" if n == cur else str(n), callback_data=f"cnt:{n}")

    return InlineKeyboardMarkup([
        [b(10), b(20), b(30), b(50)],
        [InlineKeyboardButton("← Назад", callback_data=f"acc:{username}")],
    ])

# ---------------------------------------------------------------------------
# Main menu / account selection
# ---------------------------------------------------------------------------

def _main_menu_text() -> str:
    return (
        "👋 Привет! Я помогаю анализировать Instagram-конкурентов.\n\n"
        "Собираю данные профиля, постов, Reels и хайлайтов — "
        "и записываю всё в таблицу.\n\n"
        "Выбери конкурента из списка или добавь нового 👇"
    )


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Мои конкуренты", callback_data="show_accounts"),
            InlineKeyboardButton("➕ Добавить нового", callback_data="acc_new"),
        ],
        [InlineKeyboardButton("❓ Справка", callback_data="help:main")],
    ])


def _accounts_keyboard() -> InlineKeyboardMarkup:
    accounts = _load_accounts()
    rows = []
    for acc in accounts[:10]:
        uname = acc.get("username", "")
        rows.append([InlineKeyboardButton(f"@{uname}", callback_data=f"accview:{uname}")])
    rows.append([InlineKeyboardButton("➕ Добавить новый", callback_data="acc_new")])
    rows.append([InlineKeyboardButton("← Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

# ---------------------------------------------------------------------------
# Help screen texts
# ---------------------------------------------------------------------------

_HELP_MAIN = (
    "❓ Как это работает\n\n"
    "Бот собирает данные из Instagram и записывает их в Google Таблицу.\n\n"
    "1. Добавь конкурента по username (например kate.jet)\n"
    "2. Нажми «Собрать заново»\n"
    "3. Через 3–10 минут данные появятся в таблице\n\n"
    "Стоимость одного анализа — $0.5–2 в зависимости от количества постов."
)

_HELP_ACCOUNT = (
    "❓ Что означают значки\n\n"
    "✅ — данные свежие\n"
    "⚠️ — данные устарели, лучше обновить\n"
    "⚪ — данных нет, ещё не собирались\n\n"
    "🔄 Собрать заново — удалит старые данные и соберёт всё с нуля\n"
    "➕ Добавить новые посты — оставит старые, добавит только новые\n"
    "⚡ Быстрое обновление — пересоберёт только устаревшее"
)

_HELP_SETTINGS = (
    "❓ Что выбирать\n\n"
    "Блоки — части профиля которые нужно собрать.\n"
    "Если нужен только анализ постов — оставь галочку только на «Посты».\n\n"
    "Период — за сколько месяцев собирать посты.\n"
    "Чем меньше период — тем быстрее и дешевле.\n\n"
    "Типы постов — обычно достаточно Фото + Карусель."
)

# ---------------------------------------------------------------------------
# Apify balance
# ---------------------------------------------------------------------------

async def _get_apify_balance() -> float | None:
    try:
        from dotenv import dotenv_values
        token = dotenv_values(RESEARCH_DIR / ".env").get("APIFY_TOKEN", "")
        if not token:
            return None
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"https://api.apify.com/v2/users/me/usage/monthly?token={token}"
            )
            services = r.json()["data"].get("monthlyServiceUsage", {})
            return round(sum(v.get("amountAfterVolumeDiscountUsd", 0) for v in services.values()), 4)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Progress parsing from log
# ---------------------------------------------------------------------------

_STAGE_NAMES = {
    "01":  "Профиль и закрепы",
    "02":  "Детали закрепов",
    "03":  "Анализ текста закрепов",
    "04":  "Визуал закрепов",
    "05":  "Анализ bio",
    "06":  "Классификация ссылки",
    "07":  "Анализ лендинга",
    "08":  "Сбор хайлайтов",
    "09":  "Сбор сторис",
    "10":  "Анализ хайлайтов",
    "11":  "Сбор Reels",
    "12":  "Анализ Reels",
    "13":  "Сбор постов",
    "14":  "Анализ постов",
    "15":  "Сборка данных",
    "15b": "Подготовка таблицы",
    "16":  "Запись в таблицу",
}


def _parse_progress(log_path: Path, stages: list[str]) -> str:
    done: set[str] = set()
    failed: set[str] = set()
    current: str | None = None

    if log_path.exists():
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                # "[1/N] 01 collect_profile" — stage started
                m = re.search(r'\[(\d+)/\d+\] (\w+) (\w+)', line)
                if m:
                    current = m.group(2)
                # "01 collect_profile: ok" / ": dry_run" / ": failed — ..." — итог стейджа
                m2 = re.search(r'^(\w+) \w+: (ok|dry_run|failed)\b', line.strip())
                if m2:
                    status = m2.group(2)
                    if status == "failed":
                        failed.add(m2.group(1))
                    else:
                        done.add(m2.group(1))
                    if current == m2.group(1):
                        current = None
        except Exception:
            pass

    lines = []
    for s in stages:
        name = _STAGE_NAMES.get(s, s)
        if s in failed:
            lines.append(f"❌ {name}")
        elif s in done:
            lines.append(f"✅ {name}")
        elif s == current:
            lines.append(f"⚙️ {name}...")
        else:
            lines.append(f"⏳ {name}")
    return "\n".join(lines)


def _mode_desc(write_mode: str) -> str:
    """Человекочитаемое описание режима записи для прогресса."""
    return "полный анализ" if write_mode == "replace" else "добавление новых постов"


def _parse_final_stats(log_path: Path) -> str:
    """Extract key numbers from log for the final report."""
    if not log_path.exists():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
        lines = []
        for line in text.splitlines():
            if "Reels" in line and "Собрано" in line:
                lines.append(f"🎬 {line.strip()}")
            if "Posts Index" in line and "Собрано" in line:
                lines.append(f"📝 {line.strip()}")
            if "Проанализировано:" in line:
                lines.append(f"🤖 {line.strip()}")
            if "Листов:" in line and "строк:" in line:
                lines.append(f"📊 {line.strip()}")
        return "\n".join(lines[:6])
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

async def _run_pipeline_task(
    bot,
    chat_id: int,
    username: str,
    stages: list[str],
    dry_run: bool,
    settings: dict,
    progress_msg_id: int | None,
):
    log_path = RESEARCH_DIR / "data" / username / "pipeline.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, str(RUN_PY),
        "--account", username,
        "--stages", ",".join(stages),
        "--write-mode", settings.get("write_mode", "replace"),
    ]
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    # Посты: всегда фото+карусель, режим «последние N» (count), без периода.
    env["PIPELINE_POST_TYPES"]     = "photo,carousel"
    env["PIPELINE_CONTENT_MODE"]   = "count"
    env["PIPELINE_TARGET_COUNT"]   = str(settings.get("target_count", 30))
    env["PIPELINE_CONTENT_FILTER"] = settings.get("content_filter", "all")

    start_ts = time.time()
    wm_label = _mode_desc(settings.get("write_mode", "replace"))

    async def _update_progress():
        while current_job["running"]:
            await asyncio.sleep(30)
            if not current_job["running"]:
                break
            elapsed_min = int((time.time() - start_ts) / 60)
            progress = _parse_progress(log_path, stages)
            text = (
                f"⏳ Анализ @{username} — {wm_label} [{elapsed_min} мин]\n\n"
                f"{progress}"
            )
            try:
                if progress_msg_id:
                    await bot.edit_message_text(
                        chat_id=chat_id, message_id=progress_msg_id, text=text
                    )
            except Exception:
                pass

    progress_task = asyncio.create_task(_update_progress())

    try:
        loop = asyncio.get_running_loop()
        with open(log_path, "w", encoding="utf-8") as log_file:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    cwd=str(RESEARCH_DIR),
                    env=env,
                    stdout=log_file,
                    stderr=log_file,
                ),
            )
    except Exception as e:
        logger.exception("Pipeline error for @%s: %s", username, e)
        result = None
    finally:
        progress_task.cancel()
        current_job["running"]              = False
        current_job["account"]              = None
        current_job["started_at"]           = None
        current_job["chat_id"]              = None
        current_job["progress_msg_id"]      = None

    elapsed = time.time() - start_ts
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Apify cost delta
    apify_before = current_job.get("apify_balance_before")
    apify_after  = await _get_apify_balance()
    if apify_before is not None and apify_after is not None:
        apify_cost_str = f"Apify ${apify_after - apify_before:.4f}"
    else:
        apify_cost_str = "Apify см. console.apify.com"

    ok = result is not None and result.returncode == 0
    header = f"{'✅' if ok else '⚠️'} Анализ @{username} {'завершён' if ok else 'завершён с ошибками'} за {minutes} мин {seconds} сек"

    stats = _parse_final_stats(log_path)
    progress_final = _parse_progress(log_path, stages)

    text = (
        f"{header}\n\n"
        f"{progress_final}\n\n"
    )
    if stats:
        text += f"📋 Итоги:\n{stats}\n\n"
    text += f"💰 {apify_cost_str}\n"
    if dry_run:
        text += "\n🧪 Это был dry-run — данные не записаны"
    else:
        text += f"\n🔗 Таблица: {SPREADSHEET_URL}"
        sheet_counts = await _read_sheet_counts_live(username)
        account_summary = _get_account_summary(username, sheet_counts)
        text += f"\n\n{account_summary}"
    if not ok and log_path.exists():
        text += f"\n📄 Лог: {log_path}"

    # Навигация после завершения — чтобы не застрять на отчёте
    nav = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 К конкуренту", callback_data=f"accview:{username}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
    ])
    try:
        if progress_msg_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg_id,
                                        text=text, reply_markup=nav)
        else:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=nav)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=nav)

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text(
            f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}"
        )
        return
    await update.message.reply_text(
        _main_menu_text(),
        reply_markup=_main_keyboard(),
    )


async def _start_run(query, context, username: str, stages: list[str],
                     dry_run: bool, write_mode: str, settings: dict):
    """Запускает пайплайн с заданным набором стейджей и режимом записи."""
    if current_job["running"]:
        await query.answer(
            f"⏳ Уже выполняется анализ @{current_job['account']}. Дождитесь завершения.",
            show_alert=True,
        )
        return

    # Защита от потери сессии: username должен быть реальным, не "?".
    if not _valid_account(username):
        await query.edit_message_text(
            "⚠️ Сессия сброшена — выбери конкурента заново.",
            reply_markup=_accounts_keyboard(),
        )
        return

    _ensure_account(username)

    mode_label = "🧪 Dry-run" if dry_run else "Запускаю"
    wm_label = _mode_desc(write_mode)
    progress_text = (
        f"⏳ {mode_label} @{username} — {wm_label} [0 мин]\n\n"
        + "\n".join(f"⏳ {_STAGE_NAMES.get(st, st)}" for st in stages)
    )
    msg = await query.edit_message_text(progress_text)

    run_settings = dict(settings)
    run_settings["write_mode"] = write_mode

    current_job["running"]              = True
    current_job["account"]              = username
    current_job["started_at"]           = time.time()
    current_job["chat_id"]              = query.message.chat_id
    current_job["progress_msg_id"]      = msg.message_id
    current_job["apify_balance_before"] = await _get_apify_balance()

    asyncio.create_task(_run_pipeline_task(
        bot=context.bot,
        chat_id=query.message.chat_id,
        username=username,
        stages=stages,
        dry_run=dry_run,
        settings=run_settings,
        progress_msg_id=msg.message_id,
    ))


async def _perform_delete(query, username: str):
    """Удаляет аккаунт: accounts.json + папку data/<username>/ + строки из таблицы."""
    await query.edit_message_text(f"🗑 Удаляю @{username}…")
    lines = []

    # 1. accounts.json
    if _remove_account_from_json(username):
        lines.append("✅ Удалён из списка аккаунтов")
    else:
        lines.append("⚠️ В списке аккаунтов не найден")

    # 2. Папка data/<username>/ (с защитой от path traversal)
    target = _safe_account_dir(username)
    if target is None:
        lines.append("⚠️ Недопустимое имя — папка не тронута")
    elif target.exists():
        try:
            shutil.rmtree(target)
            lines.append(f"✅ Папка data/{username}/ удалена")
        except Exception as e:
            lines.append(f"⚠️ Папка: {e}")
    else:
        lines.append("ℹ️ Папки с данными не было")

    # 3. Строки из Google-таблицы
    ok, deleted, err = await _delete_account_from_sheets(username)
    if ok:
        lines.append(f"✅ Из таблицы удалено строк: {deleted}")
    else:
        lines.append(f"⚠️ Таблица: {err or 'не удалось удалить'}")

    await query.edit_message_text(
        f"🗑 @{username} удалён\n\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("← К списку", callback_data="show_accounts")
        ]]),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(update):
        await query.edit_message_text("⛔ Нет доступа.")
        return

    data = query.data

    # ── Main menu ──────────────────────────────────────────────────────────
    if data == "main_menu":
        await query.edit_message_text(
            _main_menu_text(),
            reply_markup=_main_keyboard(),
        )
        return

    # ── Help screens (возврат на тот же экран) ────────────────────────────
    if data == "help:main":
        await query.edit_message_text(
            _HELP_MAIN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Назад", callback_data="main_menu")
            ]]),
        )
        return

    if data.startswith("help:account:"):
        username = data[len("help:account:"):]
        await query.edit_message_text(
            _HELP_ACCOUNT,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Назад", callback_data=f"accview:{username}")
            ]]),
        )
        return

    if data.startswith("help:settings:"):
        username = data[len("help:settings:"):]
        await query.edit_message_text(
            _HELP_SETTINGS,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("← Назад", callback_data=f"acc:{username}")
            ]]),
        )
        return

    # ── Account list ──────────────────────────────────────────────────────
    if data == "show_accounts":
        await query.edit_message_text(
            _accounts_list_text(),
            reply_markup=_accounts_keyboard(),
        )
        return

    if data == "acc_new":
        context.user_data["waiting_for"] = "new_username"
        await query.edit_message_text(
            "Введите Instagram username нового аккаунта\n(например: kate.jet):"
        )
        return

    # ── Account view screen (свежесть данных + действия) ──────────────────
    if data.startswith("accview:"):
        username = data[len("accview:"):]
        context.user_data["username"] = username
        _get_settings(context)
        fresh = _block_freshness(username)
        sheet_counts = await _read_sheet_counts_live(username)
        await query.edit_message_text(
            _account_screen_text(username, sheet_counts),
            reply_markup=_account_screen_keyboard(username, fresh),
        )
        return

    # ── Account run actions (Быстрое обновление / Собрать заново / Добавить новые посты) ─
    if data.startswith("accrun:"):
        _, action_kind, username = data.split(":", 2)
        context.user_data["username"] = username
        s = _get_settings(context)
        if action_kind == "stale":
            fresh = _block_freshness(username)
            blocks = [b for b, (st, _) in fresh.items() if st in ("stale", "none")]
            stages = _stages_for_blocks(blocks)
            write_mode = "replace"
        elif action_kind == "append":
            stages = list(_ALL_STAGES_ORDER)
            write_mode = "append"
        else:  # "all"
            stages = list(_ALL_STAGES_ORDER)
            write_mode = "replace"
        await _start_run(query, context, username, stages, dry_run=False,
                         write_mode=write_mode, settings=s)
        return

    # ── Account delete (confirm + perform) ────────────────────────────────
    if data.startswith("accdelyes:"):
        username = data[len("accdelyes:"):]
        await _perform_delete(query, username)
        return

    if data.startswith("accdel:"):
        username = data[len("accdel:"):]
        await query.edit_message_text(
            f"🗑 Удалить @{username}?\n\n"
            f"Будут удалены:\n"
            f"• запись из списка аккаунтов\n"
            f"• папка data/{username}/ (все собранные данные)\n"
            f"• строки аккаунта из Google-таблицы\n\n"
            f"Действие необратимо.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 Да, удалить", callback_data=f"accdelyes:{username}")],
                [InlineKeyboardButton("← Отмена",       callback_data=f"accview:{username}")],
            ]),
        )
        return

    if data.startswith("acc:"):
        username = data[4:]
        context.user_data["username"] = username
        s = _get_settings(context)
        await query.edit_message_text(
            _settings_text(username, s),
            reply_markup=_settings_keyboard(username, s),
        )
        return

    # ── Settings toggles ──────────────────────────────────────────────────
    username = context.user_data.get("username", "?")
    s = _get_settings(context)

    if data == "cntmenu":           # подэкран «Количество постов»
        await query.edit_message_text(_count_text(username, s),
                                      reply_markup=_count_keyboard(username, s))
        return

    if data.startswith("cnt:"):     # выбор количества постов → назад в настройки
        try:
            s["target_count"] = int(data[4:])
        except ValueError:
            pass
        await query.edit_message_text(_settings_text(username, s),
                                      reply_markup=_settings_keyboard(username, s))
        return

    if data.startswith("grp:"):     # toggle group
        key = data[4:]
        if key in s.get("groups", {}):
            s["groups"][key] = not s["groups"][key]

    elif data.startswith("wm:"):    # set write mode (replace/append)
        mode = data[3:]
        if mode in ("replace", "append"):
            s["write_mode"] = mode

    # ── Actions ──────────────────────────────────────────────────────────
    elif data in ("action:estimate", "action:launch"):
        # Защита от потери сессии (рестарт бота → username="?").
        if not _valid_account(username):
            await query.edit_message_text(
                "⚠️ Сессия сброшена — выбери конкурента заново.",
                reply_markup=_accounts_keyboard(),
            )
            return
        # Защита от пустого выбора групп.
        if not _selected_groups(s):
            try:
                await query.edit_message_text(
                    "⚠️ Выбери хотя бы одну группу для сбора.\n\n" + _settings_text(username, s),
                    reply_markup=_settings_keyboard(username, s),
                )
            except Exception:
                pass
            return
        if data == "action:estimate":
            estimate = _estimate_cost(s)
            stages   = _build_stages_list(s)
            estimate += f"\n\nСтейджи: {', '.join(stages)}"
            await query.edit_message_text(
                estimate,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Назад к настройкам", callback_data=f"acc:{username}")
                ]]),
            )
            return
        # action:launch
        stages = _build_stages_list(s)
        await _start_run(query, context, username, stages, dry_run=False,
                         write_mode=s.get("write_mode", "replace"), settings=s)
        return

    # Re-render settings after toggle
    await query.edit_message_text(
        _settings_text(username, s),
        reply_markup=_settings_keyboard(username, s),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text(
            f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}"
        )
        return

    waiting = context.user_data.pop("waiting_for", None)

    if waiting == "new_username":
        username = validate_username(update.message.text or "")
        if not username:
            await update.message.reply_text(
                "❌ Неверный формат. Только латиница, цифры, точки, подчеркивания.\n"
                "Попробуйте ещё раз:"
            )
            context.user_data["waiting_for"] = "new_username"
            return
        context.user_data["username"] = username
        context.user_data["settings"] = _default_settings()
        s = context.user_data["settings"]
        await update.message.reply_text(
            _settings_text(username, s),
            reply_markup=_settings_keyboard(username, s),
        )
        return

    await update.message.reply_text(
        "Используйте кнопку ниже для запуска анализа:",
        reply_markup=_main_keyboard(),
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text(f"⛔ Нет доступа.")
        return
    if current_job["running"]:
        elapsed = int((time.time() - current_job["started_at"]) / 60)
        await update.message.reply_text(
            f"⏳ Выполняется анализ @{current_job['account']}\n"
            f"Запущен: {elapsed} мин назад"
        )
    else:
        await update.message.reply_text("✅ Нет активных анализов")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в .env")
        sys.exit(1)

    if not get_allowed_ids():
        logger.error("TELEGRAM_ALLOWED_IDS не задан в .env")
        sys.exit(1)

    logger.info("Бот запускается...")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
