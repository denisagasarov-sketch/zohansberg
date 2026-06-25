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
import logging

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
    scout, format_scout_message, triage as scout_triage, drop_codes,
)
from pipeline.stages import collect_posts, analyze_posts

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
