"""Telegram bot for Instagram competitor research pipeline."""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
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

# Apify cost estimates per block (USD)
_APIFY_COSTS = {"01-04": 0.05, "08-10": 0.10, "11-12": 0.05, "13-14": 0.10}
# OpenAI cost estimates per block (USD)
_OPENAI_COSTS = {"03": 0.05, "04": 0.03, "05": 0.02, "07": 0.05, "10": 0.08, "12": 0.08, "14": 0.15}


def _default_settings() -> dict:
    return {
        "blocks":         {k: True  for k in _BLOCK_LABELS},
        "post_types":     {"photo": True, "carousel": True, "video": False},
        "content_mode":   "period",
        "months_back":    6,
        "target_count":   30,
        "content_filter": "all",
        "sheets":         {k: True for k in _SHEET_LABELS},
    }


def _get_settings(context: ContextTypes.DEFAULT_TYPE) -> dict:
    if "settings" not in context.user_data:
        context.user_data["settings"] = _default_settings()
    return context.user_data["settings"]


def _build_stages_list(settings: dict) -> list[str]:
    stages = []
    for block_key, enabled in settings["blocks"].items():
        if enabled:
            stages.extend(_BLOCK_STAGES[block_key])
    stages += ["15", "15b", "16"]
    # deduplicate preserving order
    seen = set()
    result = []
    for s in stages:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result

# ---------------------------------------------------------------------------
# Cost estimate
# ---------------------------------------------------------------------------

def _estimate_cost(settings: dict) -> str:
    apify_total  = 0.0
    openai_total = 0.0
    apify_parts  = []
    openai_parts = []

    for block_key, enabled in settings["blocks"].items():
        if not enabled:
            continue
        a = _APIFY_COSTS.get(block_key, 0)
        if a:
            apify_total += a
            apify_parts.append(f"{_BLOCK_LABELS[block_key].split('(')[0].strip()} ${a:.2f}")
        for stage in _BLOCK_STAGES[block_key]:
            o = _OPENAI_COSTS.get(stage, 0)
            if o:
                openai_total += o
                openai_parts.append(f"stage {stage} ${o:.2f}")

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
    s = settings
    pt = s["post_types"]
    cm = "За период" if s["content_mode"] == "period" else "Кол-во штук"
    mo = s["months_back"]
    tc = s["target_count"]
    cf_labels = {"all": "Все", "professional": "Проф", "personal": "Личный"}
    cf = cf_labels.get(s["content_filter"], s["content_filter"])

    block_lines = "\n".join(
        f"{_ck(s['blocks'][k])} {label}"
        for k, label in _BLOCK_LABELS.items()
    )
    sheet_lines = "\n".join(
        f"{_ck(s['sheets'][k])} {label}"
        for k, label in _SHEET_LABELS.items()
    )

    return (
        f"=== Настройки анализа @{username} ===\n\n"
        f"БЛОКИ:\n{block_lines}\n\n"
        f"ПОСТЫ — фильтры:\n"
        f"{_ck(pt['photo'])} Фото  {_ck(pt['carousel'])} Карусель  {_ck(pt['video'])} Видео\n"
        f"Режим: {cm}   Период: {mo}м   Кол-во: {tc}\n"
        f"Контент: {cf}\n\n"
        f"ЗАПИСЬ В ТАБЛИЦУ:\n{sheet_lines}"
    )


def _settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    s = settings
    pt = s["post_types"]
    cf = s["content_filter"]
    mo = s["months_back"]
    cm = s["content_mode"]

    def tb(key):
        return _ck(s["blocks"][key])

    rows = [
        # Blocks row 1-2
        [
            InlineKeyboardButton(f"{tb('01-04')} Профиль/закрепы", callback_data="tbl:01-04"),
            InlineKeyboardButton(f"{tb('05')} Bio",                callback_data="tbl:05"),
        ],
        [
            InlineKeyboardButton(f"{tb('06-07')} Ссылка/лендинг", callback_data="tbl:06-07"),
            InlineKeyboardButton(f"{tb('08-10')} Хайлайты",       callback_data="tbl:08-10"),
        ],
        [
            InlineKeyboardButton(f"{tb('11-12')} Reels",          callback_data="tbl:11-12"),
            InlineKeyboardButton(f"{tb('13-14')} Посты",          callback_data="tbl:13-14"),
        ],
        # Post types
        [
            InlineKeyboardButton(f"{_ck(pt['photo'])} Фото",      callback_data="tpt:photo"),
            InlineKeyboardButton(f"{_ck(pt['carousel'])} Кар.",   callback_data="tpt:carousel"),
            InlineKeyboardButton(f"{_ck(pt['video'])} Видео",     callback_data="tpt:video"),
        ],
        # Content mode
        [
            InlineKeyboardButton(
                f"{'▶' if cm=='period' else '·'} За период",
                callback_data="scm:period",
            ),
            InlineKeyboardButton(
                f"{'▶' if cm=='count' else '·'} Кол-во штук",
                callback_data="scm:count",
            ),
        ],
        # Months
        [
            InlineKeyboardButton(f"{'[' if mo==1  else ''}1м{']'  if mo==1  else ''}", callback_data="smo:1"),
            InlineKeyboardButton(f"{'[' if mo==3  else ''}3м{']'  if mo==3  else ''}", callback_data="smo:3"),
            InlineKeyboardButton(f"{'[' if mo==6  else ''}6м{']'  if mo==6  else ''}", callback_data="smo:6"),
            InlineKeyboardButton(f"{'[' if mo==12 else ''}12м{']' if mo==12 else ''}", callback_data="smo:12"),
        ],
        # Content filter
        [
            InlineKeyboardButton(f"{'▶' if cf=='all'          else '·'} Все",     callback_data="scf:all"),
            InlineKeyboardButton(f"{'▶' if cf=='professional' else '·'} Проф",   callback_data="scf:professional"),
            InlineKeyboardButton(f"{'▶' if cf=='personal'     else '·'} Личный", callback_data="scf:personal"),
        ],
        # Sheets row 1
        [
            InlineKeyboardButton(f"{_ck(s['sheets']['prof'])} Профиль", callback_data="tsh:prof"),
            InlineKeyboardButton(f"{_ck(s['sheets']['pins'])} Закрепы", callback_data="tsh:pins"),
            InlineKeyboardButton(f"{_ck(s['sheets']['hi'])} Хайлайты", callback_data="tsh:hi"),
        ],
        # Sheets row 2
        [
            InlineKeyboardButton(f"{_ck(s['sheets']['re'])} Reels",   callback_data="tsh:re"),
            InlineKeyboardButton(f"{_ck(s['sheets']['po'])} Посты",   callback_data="tsh:po"),
            InlineKeyboardButton(f"{_ck(s['sheets']['fu'])} Воронка", callback_data="tsh:fu"),
            InlineKeyboardButton(f"{_ck(s['sheets']['la'])} Лендинг", callback_data="tsh:la"),
        ],
        # Actions
        [
            InlineKeyboardButton("💰 Смета",   callback_data="action:estimate"),
            InlineKeyboardButton("🧪 Dry-run", callback_data="action:dryrun"),
            InlineKeyboardButton("🚀 Запустить", callback_data="action:launch"),
        ],
        [InlineKeyboardButton("← Назад", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(rows)

# ---------------------------------------------------------------------------
# Main menu / account selection
# ---------------------------------------------------------------------------

def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Анализ конкурента", callback_data="show_accounts"),
    ]])


def _accounts_keyboard() -> InlineKeyboardMarkup:
    accounts = _load_accounts()
    rows = []
    for acc in accounts[:10]:
        uname = acc.get("username", "")
        rows.append([InlineKeyboardButton(f"@{uname}", callback_data=f"acc:{uname}")])
    rows.append([InlineKeyboardButton("➕ Добавить новый", callback_data="acc_new")])
    rows.append([InlineKeyboardButton("← Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

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
    "01": "collect_profile",    "02": "collect_pinned_details",
    "03": "analyze_pinned_posts", "04": "analyze_pinned_visuals",
    "05": "analyze_bio",        "06": "classify_profile_link",
    "07": "analyze_landing",    "08": "collect_highlights",
    "09": "collect_stories",    "10": "analyze_highlights",
    "11": "collect_reels",      "12": "analyze_reels",
    "13": "collect_posts",      "14": "analyze_posts",
    "15": "build_payload",      "15b": "prepare_sheets",
    "16": "write_sheets",
}


def _parse_progress(log_path: Path, stages: list[str]) -> str:
    done: set[str] = set()
    current: str | None = None

    if log_path.exists():
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                # "[1/N] 01 collect_profile" — stage started
                m = re.search(r'\[(\d+)/\d+\] (\w+) (\w+)', line)
                if m:
                    current = m.group(2)
                # "01 collect_profile: ok" — stage done
                m2 = re.search(r'^(\w+) \w+: (ok|dry_run)$', line.strip())
                if m2:
                    done.add(m2.group(1))
                    if current == m2.group(1):
                        current = None
        except Exception:
            pass

    lines = []
    for s in stages:
        name = _STAGE_NAMES.get(s, s)
        if s in done:
            lines.append(f"✅ {s} {name}")
        elif s == current:
            lines.append(f"⚙️ {s} {name}...")
        else:
            lines.append(f"⏳ {s} {name}")
    return "\n".join(lines)


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
    ]
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    # Pass settings as env vars for future stage reads
    pt_enabled = [k for k, v in settings["post_types"].items() if v]
    env["PIPELINE_POST_TYPES"]     = ",".join(pt_enabled)
    env["PIPELINE_CONTENT_MODE"]   = settings["content_mode"]
    env["PIPELINE_MONTHS_BACK"]    = str(settings["months_back"])
    env["PIPELINE_TARGET_COUNT"]   = str(settings["target_count"])
    env["PIPELINE_CONTENT_FILTER"] = settings["content_filter"]

    start_ts = time.time()

    async def _update_progress():
        while current_job["running"]:
            await asyncio.sleep(30)
            if not current_job["running"]:
                break
            elapsed_min = int((time.time() - start_ts) / 60)
            progress = _parse_progress(log_path, stages)
            text = (
                f"⏳ Анализ @{username} [{elapsed_min} мин]\n\n"
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
    if not ok and log_path.exists():
        text += f"\n📄 Лог: {log_path}"

    try:
        if progress_msg_id:
            await bot.edit_message_text(chat_id=chat_id, message_id=progress_msg_id, text=text)
        else:
            await bot.send_message(chat_id=chat_id, text=text)
    except Exception:
        await bot.send_message(chat_id=chat_id, text=text)

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
        "Привет! Я бот для анализа Instagram-конкурентов.",
        reply_markup=_main_keyboard(),
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
            "Выберите действие:",
            reply_markup=_main_keyboard(),
        )
        return

    # ── Account list ──────────────────────────────────────────────────────
    if data == "show_accounts":
        await query.edit_message_text(
            "Выберите аккаунт для анализа:",
            reply_markup=_accounts_keyboard(),
        )
        return

    if data == "acc_new":
        context.user_data["waiting_for"] = "new_username"
        await query.edit_message_text(
            "Введите Instagram username нового аккаунта\n(например: kate.jet):"
        )
        return

    if data.startswith("acc:"):
        username = data[4:]
        context.user_data["username"] = username
        if "settings" not in context.user_data:
            context.user_data["settings"] = _default_settings()
        s = context.user_data["settings"]
        await query.edit_message_text(
            _settings_text(username, s),
            reply_markup=_settings_keyboard(s),
        )
        return

    # ── Settings toggles ──────────────────────────────────────────────────
    username = context.user_data.get("username", "?")
    s = _get_settings(context)

    if data.startswith("tbl:"):     # toggle block
        key = data[4:]
        if key in s["blocks"]:
            s["blocks"][key] = not s["blocks"][key]

    elif data.startswith("tpt:"):   # toggle post type
        key = data[4:]
        if key in s["post_types"]:
            s["post_types"][key] = not s["post_types"][key]

    elif data.startswith("tsh:"):   # toggle sheet
        key = data[4:]
        if key in s["sheets"]:
            s["sheets"][key] = not s["sheets"][key]

    elif data.startswith("scm:"):   # set content mode
        s["content_mode"] = data[4:]

    elif data.startswith("smo:"):   # set months
        s["months_back"] = int(data[4:])

    elif data.startswith("scf:"):   # set content filter
        s["content_filter"] = data[4:]

    # ── Actions ──────────────────────────────────────────────────────────
    elif data == "action:estimate":
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

    elif data in ("action:dryrun", "action:launch"):
        dry_run = (data == "action:dryrun")

        if current_job["running"]:
            await query.answer(
                f"⏳ Уже выполняется анализ @{current_job['account']}. Дождитесь завершения.",
                show_alert=True,
            )
            return

        stages = _build_stages_list(s)
        _ensure_account(username)

        mode_label = "🧪 Dry-run" if dry_run else "🚀 Запускаю"
        progress_text = (
            f"⏳ {mode_label} @{username} [0 мин]\n\n"
            + "\n".join(f"⏳ {st} {_STAGE_NAMES.get(st, st)}" for st in stages)
        )
        msg = await query.edit_message_text(progress_text)

        current_job["running"]              = True
        current_job["account"]              = username
        current_job["started_at"]           = time.time()
        current_job["chat_id"]              = update.effective_chat.id
        current_job["progress_msg_id"]      = msg.message_id
        current_job["apify_balance_before"] = await _get_apify_balance()

        asyncio.create_task(_run_pipeline_task(
            bot=context.bot,
            chat_id=update.effective_chat.id,
            username=username,
            stages=stages,
            dry_run=dry_run,
            settings=dict(s),
            progress_msg_id=msg.message_id,
        ))
        return

    # Re-render settings after toggle
    await query.edit_message_text(
        _settings_text(username, s),
        reply_markup=_settings_keyboard(s),
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
            reply_markup=_settings_keyboard(s),
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
