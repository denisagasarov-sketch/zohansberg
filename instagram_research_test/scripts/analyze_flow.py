"""
Telegram-флоу для анализа конкурента: разведка → выбор → запуск.
Плюс команда /prompts — показать промпты пайплайна read-only (моноширинно).

КАК ПОДКЛЮЧИТЬ к существующему боту (scripts/telegram_bot.py):

    from analyze_flow import build_analyze_conversation, prompts_handler
    app.add_handler(build_analyze_conversation())
    app.add_handler(prompts_handler())

Модуль лежит рядом с telegram_bot.py (каталог scripts/), который запускается
как `python3 scripts/telegram_bot.py` — поэтому scripts/ оказывается на
sys.path[0] и импорт берётся по имени модуля. Сам telegram_bot.py добавляет
RESEARCH_DIR в sys.path, чтобы здесь резолвились `from pipeline.stages ...`.

Зависимости: python-telegram-bot >= 20 (async), как в вашем bot.log.

Флоу:
    /analyze <username>
      → scout() показывает сводку (посты/типы/период/скрытые лайки/оценка/цена)
      → инлайн-кнопки выбора объёма и типа контента
      → подтверждение → collect(...) + analyze(...) в фоне
"""

import asyncio
import html
import json
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from pipeline.stages.scout_posts import (
    scout, format_scout_message, triage as scout_triage, triage_counts, drop_codes,
)
from pipeline.stages import collect_posts, analyze_posts, build_payload, prepare_sheets, write_sheets
from pipeline.core import sheets_client
from pipeline.core.paths import normalized

logger = logging.getLogger(__name__)

CHOOSING_PERIOD, CHOOSING_FILTER, CONFIRMING = range(3)

# Telegram режет сообщения на 4096 символов — длинные промпты бьём на части.
_TG_LIMIT = 3900

# Типы постов, идущие в лист «Посты» (фото + карусели). Используются и для
# раскладки по периодам в scout, и для сбора/триажа выбранного среза.
_POST_TYPES = ["photo", "carousel"]


def _period_keyboard(s: dict) -> InlineKeyboardMarkup:
    """Кнопки выбора ГЛУБИНЫ выборки 3/6/12/24 мес с числом постов на каждой."""
    bd = {b["months"]: b for b in s.get("period_breakdown", [])}

    def lbl(m: int) -> str:
        b = bd.get(m)
        if not b:
            return f"{m} мес"
        cnt = f"{b['count']}+" if b.get("lower_bound") else str(b["count"])
        return f"{m} мес · {cnt}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbl(3),  callback_data="period:3"),
         InlineKeyboardButton(lbl(6),  callback_data="period:6")],
        [InlineKeyboardButton(lbl(12), callback_data="period:12"),
         InlineKeyboardButton(lbl(24), callback_data="period:24")],
        [InlineKeyboardButton("✕ Отмена", callback_data="period:cancel")],
    ])


def _filter_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Только экспертные (без личного)", callback_data="filter:professional")],
        [InlineKeyboardButton("Все, кроме мусора", callback_data="filter:all")],
        [InlineKeyboardButton("← Назад", callback_data="filter:back")],
    ])


# ─────────────────────────────────────────────────────────────────────────────
# /analyze <username>  — шаг 1: разведка
# ─────────────────────────────────────────────────────────────────────────────
async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.args:
        await update.message.reply_text(
            "Использование: /analyze <username>\nНапример: /analyze kate.jet"
        )
        return ConversationHandler.END

    username = context.args[0].lstrip("@").strip()
    context.user_data["username"] = username

    msg = await update.message.reply_text(f"🔍 Разведка @{username}…")

    # scout — блокирующий (Apify), уводим в поток, чтобы не вешать event loop.
    # Глубокий батч (~200) + раскладка по периодам, БЕЗ GPT. Триаж НЕ здесь —
    # он применяется к ВЫБРАННОМУ срезу уже на запуске (см. confirm_run).
    try:
        s = await asyncio.to_thread(scout, username)
    except Exception as e:
        logger.exception("scout failed")
        await msg.edit_text(f"Не удалось собрать разведку по @{username}: {e}")
        return ConversationHandler.END

    context.user_data["scout_items"] = s.pop("items", [])  # сырые посты для триажа среза
    context.user_data["scout"] = s

    await msg.edit_text(
        format_scout_message(s) + "\n\nЗа какой период анализируем?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_period_keyboard(s),
    )
    return CHOOSING_PERIOD


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 2: выбор ГЛУБИНЫ (период)
# ─────────────────────────────────────────────────────────────────────────────
async def choose_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]

    if choice == "cancel":
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    months = int(choice)
    context.user_data["mode"] = "period"
    context.user_data["months_back"] = months

    bd = {b["months"]: b for b in context.user_data["scout"].get("period_breakdown", [])}
    b = bd.get(months, {})
    cnt = f"{b['count']}+" if b.get("lower_bound") else b.get("count", "?")
    context.user_data["period_label"] = f"за {months} мес (~{cnt} постов)"
    context.user_data["period_est_cost"] = b.get("est_cost_usd", 0)
    context.user_data["period_est_minutes"] = b.get("est_minutes", 0)
    context.user_data["period_lower_bound"] = bool(b.get("lower_bound"))

    await q.edit_message_text(
        f"Период: {context.user_data['period_label']}.\n\nКакой контент берём?",
        reply_markup=_filter_keyboard(),
    )
    return CHOOSING_FILTER


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 3: фильтр контента → подтверждение
# ─────────────────────────────────────────────────────────────────────────────
async def choose_filter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]

    if choice == "back":
        return await _reshow_period(q, context)

    context.user_data["content_filter"] = choice
    s = context.user_data["scout"]
    u = context.user_data
    filter_label = "только экспертные" if choice == "professional" else "все, кроме мусора"
    plus = "+" if u.get("period_lower_bound") else ""

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Запустить анализ", callback_data="confirm:go")],
        [InlineKeyboardButton("✕ Отмена", callback_data="confirm:cancel")],
    ])
    await q.edit_message_text(
        f"```\n"
        f"Запуск анализа @{s['account']}\n"
        f"{'─' * 28}\n"
        f"Период : {u['period_label']}\n"
        f"Контент: {filter_label}\n"
        f"Оценка : ≈ ${u.get('period_est_cost', 0)}{plus} · ≈ {u.get('period_est_minutes', 0)} мин\n"
        f"```",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    return CONFIRMING


async def _reshow_period(q, context) -> int:
    s = context.user_data["scout"]
    await q.edit_message_text(
        format_scout_message(s) + "\n\nЗа какой период анализируем?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_period_keyboard(s),
    )
    return CHOOSING_PERIOD


# ─────────────────────────────────────────────────────────────────────────────
# Запуск пайплайна
# ─────────────────────────────────────────────────────────────────────────────
async def confirm_run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    if q.data.endswith("cancel"):
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    u = context.user_data
    username = u["username"]
    await q.edit_message_text(f"⏳ Анализирую @{username}… это займёт несколько минут.")

    months_back = u.get("months_back", 6)

    def _run():
        # Триаж на ВЫБРАННОМ срезе: L0 режет вне периода/типа (бесплатно),
        # L1 (один gpt-4o-mini батч) — personal. drop-коды не собираем вовсе.
        items = u.get("scout_items") or []
        try:
            verdicts = scout_triage(items, months_back, _POST_TYPES)
        except Exception:
            logger.exception("triage failed — продолжаем без триажа (анализ сам отфильтрует)")
            verdicts = []
        drop = drop_codes(verdicts)
        triage_map = {v["short_code"]: v for v in verdicts if v.get("short_code")}

        collect_posts.collect(
            username,
            months_back=months_back,
            post_types=_POST_TYPES,
            content_mode="period",
            exclude_codes=drop or None,
        )
        # triage-карта: keep/review берутся оттуда, _is_relevant повторно не вызывается.
        return analyze_posts.analyze(
            username,
            content_filter=u.get("content_filter", "all"),
            triage=triage_map or None,
        )

    try:
        result = await asyncio.to_thread(_run)
    except Exception as e:
        logger.exception("pipeline failed")
        await q.edit_message_text(f"Ошибка прогона @{username}: {e}")
        return ConversationHandler.END

    ok = result.get("posts_ok", "?")
    filt = result.get("filtered_count", "?")
    rev = result.get("review_count", 0)
    await q.edit_message_text(
        f"✅ Готово, @{username}.\n"
        f"Проанализировано: {ok} · спорных (mixed): {rev} · отфильтровано: {filt}\n"
        f"Результат записан в Google Sheets."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Отменено.")
    return ConversationHandler.END


def build_analyze_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("analyze", analyze_start)],
        states={
            CHOOSING_PERIOD: [CallbackQueryHandler(choose_period, pattern=r"^period:")],
            CHOOSING_FILTER: [CallbackQueryHandler(choose_filter, pattern=r"^filter:")],
            CONFIRMING:      [CallbackQueryHandler(confirm_run, pattern=r"^confirm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# /prompts — показать промпты пайплайна read-only, моноширинным
# ─────────────────────────────────────────────────────────────────────────────
def _chunk_mono(title: str, text: str) -> list[str]:
    """Режет длинный промпт на части ≤ лимита Telegram, каждая в ``` блоке."""
    header = f"*{title}*\n"
    out, buf = [], ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > _TG_LIMIT:
            out.append(buf)
            buf = ""
        buf += line
    if buf:
        out.append(buf)
    msgs = []
    for i, part in enumerate(out):
        prefix = header if i == 0 else ""
        msgs.append(prefix + "```\n" + html.escape(part) + "\n```")
    return msgs


async def show_prompts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Импортируем сами переменные промптов — показываем ровно то, что уходит в модель."""
    from pipeline.stages.analyze_posts import (
        FILTER_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
        USER_PROMPT_TEMPLATE,
        MODEL,
        FILTER_MODEL,
    )

    await update.message.reply_text(
        f"Промпты пайплайна (read-only).\n"
        f"Анализ: `{MODEL}` · фильтр: `{FILTER_MODEL}`",
        parse_mode=ParseMode.MARKDOWN,
    )

    blocks = [
        ("1/3 · Фильтр мусора (system)", FILTER_SYSTEM_PROMPT),
        ("2/3 · Анализ — справочник механик (system)", SYSTEM_PROMPT),
        ("3/3 · Анализ — поля и определения (user)", USER_PROMPT_TEMPLATE),
    ]
    for title, text in blocks:
        for chunk in _chunk_mono(title, text):
            await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN)


def prompts_handler() -> CommandHandler:
    return CommandHandler("prompts", show_prompts)


# ═════════════════════════════════════════════════════════════════════════════
# Умный флоу: /start → «Анализировать конкурента» → username → экран состояния
# Поверх существующего пайплайна — НИКАКОЙ новой логики collect/analyze/триаж/
# upsert: только новая входная точка, экран состояния и оркестрация записи.
# ═════════════════════════════════════════════════════════════════════════════
SMART_USERNAME, SMART_ACTION, SMART_PERIOD, SMART_PERIOD_MODE = range(4)

_DEFAULT_MONTHS = 12


def _table_state(username: str) -> dict:
    """Состояние листа «Посты» для аккаунта: число строк + дата последнего анализа.

    Дату берём как максимум по колонке «Дата записи» (если её нет/не парсится —
    возвращаем только число строк). При ошибке чтения — ok=False.
    """
    try:
        data = sheets_client.get_account_rows("Посты", username)
    except Exception as e:
        return {"ok": False, "error": type(e).__name__}
    hdr, rows = data["headers"], data["rows"]
    last = None
    if "Дата записи" in hdr:
        di = hdr.index("Дата записи")
        best = None
        for r in rows:
            v = str(r[di]).strip() if di < len(r) else ""
            try:
                d = datetime.strptime(v, "%d.%m.%Y")
            except Exception:
                continue
            if best is None or d > best:
                best = d
        last = best.strftime("%d.%m.%Y") if best else None
    return {"ok": True, "count": len(rows), "last_date": last}


def _smart_status_text(username: str, tbl: dict, s: dict) -> str:
    """Моноширинный экран состояния: что в таблице + раскладка Instagram по периодам."""
    bd = {b["months"]: b for b in s.get("period_breakdown", [])}

    def cnt(m: int) -> str:
        b = bd.get(m, {})
        return f"{b.get('count', 0)}{'+' if b.get('lower_bound') else ''}"

    if tbl.get("ok"):
        tline = f"В таблице  : {tbl['count']} постов"
        if tbl.get("last_date"):
            tline += f" (посл. анализ {tbl['last_date']})"
    else:
        tline = f"В таблице  : не прочитать ({tbl.get('error')})"

    body = (
        f"@{username}\n"
        f"{'─' * 30}\n"
        f"{tline}\n"
        f"В Instagram (photo+carousel):\n"
        f"   3 мес → {cnt(3)}\n"
        f"   6 мес → {cnt(6)}\n"
        f"  12 мес → {cnt(12)}\n"
        f"  24 мес → {cnt(24)}\n"
        f"Скрытые лайки: {s.get('hidden_likes', 0)} из {s.get('total', 0)}"
    )
    return "```\n" + body + "\n```"


def _smart_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"♻️ Перезаписать за {_DEFAULT_MONTHS} мес",
                              callback_data=f"smartrun:replace:{_DEFAULT_MONTHS}")],
        [InlineKeyboardButton(f"🔁 Обновить (upsert) {_DEFAULT_MONTHS} мес",
                              callback_data=f"smartrun:upsert:{_DEFAULT_MONTHS}")],
        [InlineKeyboardButton("📅 Выбрать период…", callback_data="smartperiod:menu")],
        [InlineKeyboardButton("✕ Отмена", callback_data="smartcancel:x")],
    ])


def _smart_period_keyboard(s: dict) -> InlineKeyboardMarkup:
    bd = {b["months"]: b for b in s.get("period_breakdown", [])}

    def lbl(m: int) -> str:
        b = bd.get(m, {})
        c = f"{b.get('count', 0)}{'+' if b.get('lower_bound') else ''}"
        return f"{m} мес · {c}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(lbl(3),  callback_data="smartp:3"),
         InlineKeyboardButton(lbl(6),  callback_data="smartp:6")],
        [InlineKeyboardButton(lbl(12), callback_data="smartp:12"),
         InlineKeyboardButton(lbl(24), callback_data="smartp:24")],
        [InlineKeyboardButton("← Назад", callback_data="smartp:back")],
    ])


def _smart_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("♻️ Перезаписать", callback_data="smartm:replace"),
         InlineKeyboardButton("🔁 Обновить (upsert)", callback_data="smartm:upsert")],
        [InlineKeyboardButton("← Назад", callback_data="smartm:back")],
    ])


def _run_pipeline(scout_items: list, username: str, months: int, write_mode: str) -> tuple:
    """collect → triage → analyze → build → prepare → ОБРЕЗАТЬ payload до «Посты» → write.

    Использует существующие стейджи без изменений; различие replace/upsert — только
    в write_mode. Запись ограничена листом «Посты» обрезкой sheets_payload.json
    (как в run_upsert_posts.py): Apps Script пишет лишь Object.keys(payload.sheets).
    Возвращает (analyze_out, write_result, triage_counts).
    """
    verdicts = scout_triage(scout_items, months, _POST_TYPES)
    drop = drop_codes(verdicts)
    triage_map = {v["short_code"]: v for v in verdicts if v.get("short_code")}

    collect_posts.collect(username, months_back=months, content_mode="period",
                          post_types=_POST_TYPES, exclude_codes=drop or None)
    out = analyze_posts.analyze(username, content_filter="professional", triage=triage_map or None)
    build_payload.build(username)
    prepare_sheets.prepare(username)

    # обрезаем payload до одного листа «Посты» (blast-radius) ДО записи
    sp = normalized(username, "sheets_payload.json")
    payload = json.loads(sp.read_text(encoding="utf-8"))
    posts_sheet = payload.get("sheets", {}).get("Посты")
    if posts_sheet is None:
        raise RuntimeError("листа «Посты» нет в payload — запись отменена")
    payload["sheets"] = {"Посты": posts_sheet}
    sp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    res = write_sheets.write(username, write_mode=write_mode)
    return out, res, triage_counts(verdicts)


# ── handlers ─────────────────────────────────────────────────────────────────
async def smart_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Кнопка «🔍 Анализировать конкурента» → просим username."""
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.edit_message_text("Введите username конкурента (например kate.jet):")
    return SMART_USERNAME


async def smart_entry_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Командная точка входа /competitor (для совместимости/тестов)."""
    context.user_data.clear()
    if context.args:
        update.message.text = context.args[0]
        return await smart_username(update, context)
    await update.message.reply_text("Введите username конкурента (например kate.jet):")
    return SMART_USERNAME


async def smart_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    username = text.lstrip("@").split()[0] if text else ""
    if not username:
        await update.message.reply_text("Пустой username. Введите ещё раз или /cancel.")
        return SMART_USERNAME

    context.user_data["smart_username"] = username
    msg = await update.message.reply_text(f"🔍 Разведка @{username} + чтение таблицы…")

    # scout (Apify) и чтение таблицы — блокирующие, уводим в поток
    try:
        s = await asyncio.to_thread(scout, username)
        tbl = await asyncio.to_thread(_table_state, username)
    except Exception as e:
        logger.exception("smart scout/table failed")
        await msg.edit_text(f"Не удалось собрать данные по @{username}: {e}")
        return ConversationHandler.END

    context.user_data["smart_items"] = s.pop("items", [])
    context.user_data["smart_scout"] = s
    context.user_data["smart_tbl"] = tbl

    await msg.edit_text(
        _smart_status_text(username, tbl, s) + "\n\nЧто делаем?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_smart_action_keyboard(),
    )
    return SMART_ACTION


async def smart_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("smartcancel"):
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    if data.startswith("smartperiod"):
        await q.edit_message_text(
            "За какой период собрать?",
            reply_markup=_smart_period_keyboard(context.user_data["smart_scout"]),
        )
        return SMART_PERIOD

    # smartrun:<mode>:<months>
    _, mode, months = data.split(":")
    return await _smart_execute(q, context, int(months), mode)


async def smart_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]

    if choice == "back":  # назад на экран состояния
        u = context.user_data
        await q.edit_message_text(
            _smart_status_text(u["smart_username"], u["smart_tbl"], u["smart_scout"]) + "\n\nЧто делаем?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_smart_action_keyboard(),
        )
        return SMART_ACTION

    context.user_data["smart_months"] = int(choice)
    await q.edit_message_text(
        f"Период: за {choice} мес.\n\nРежим записи?",
        reply_markup=_smart_mode_keyboard(),
    )
    return SMART_PERIOD_MODE


async def smart_period_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]

    if choice == "back":
        await q.edit_message_text(
            "За какой период собрать?",
            reply_markup=_smart_period_keyboard(context.user_data["smart_scout"]),
        )
        return SMART_PERIOD

    months = context.user_data.get("smart_months", _DEFAULT_MONTHS)
    return await _smart_execute(q, context, months, choice)


async def _smart_execute(q, context, months: int, write_mode: str) -> int:
    u = context.user_data
    username = u["smart_username"]
    items = u.get("smart_items", [])
    mode_label = "перезапись" if write_mode == "replace" else "обновление (upsert)"
    await q.edit_message_text(
        f"⏳ @{username}: {mode_label} за {months} мес… это займёт несколько минут."
    )
    try:
        _out, res, counts = await asyncio.to_thread(_run_pipeline, items, username, months, write_mode)
    except Exception as e:
        logger.exception("smart pipeline failed")
        await q.edit_message_text(f"Ошибка прогона @{username}: {e}")
        return ConversationHandler.END

    warns = res.get("upsert_warnings") or []
    warn_line = ("\n⚠️ " + "; ".join(warns)) if warns else ""
    await q.edit_message_text(
        f"✅ Готово, @{username} ({mode_label}, {months} мес).\n"
        f"Триаж: keep {counts.get('keep', 0)} · review {counts.get('review', 0)} · "
        f"drop {counts.get('drop', 0)}\n"
        f"В листе «Посты» теперь: {res.get('rows_written', '?')} строк.{warn_line}"
    )
    return ConversationHandler.END


def build_smart_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(smart_entry, pattern=r"^smart:start$"),
            CommandHandler("competitor", smart_entry_cmd),
        ],
        states={
            SMART_USERNAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, smart_username)],
            SMART_ACTION:      [CallbackQueryHandler(smart_action, pattern=r"^(smartrun|smartperiod|smartcancel)")],
            SMART_PERIOD:      [CallbackQueryHandler(smart_period, pattern=r"^smartp:")],
            SMART_PERIOD_MODE: [CallbackQueryHandler(smart_period_mode, pattern=r"^smartm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
