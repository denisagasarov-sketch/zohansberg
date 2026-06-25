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

from pipeline.stages.scout_posts import scout, format_scout_message
from pipeline.stages import collect_posts, analyze_posts

logger = logging.getLogger(__name__)

CHOOSING_SCOPE, CHOOSING_FILTER, CONFIRMING = range(3)

# Telegram режет сообщения на 4096 символов — длинные промпты бьём на части.
_TG_LIMIT = 3900


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

    # scout — блокирующий (Apify), уводим в поток, чтобы не вешать event loop
    try:
        s = await asyncio.to_thread(scout, username)
    except Exception as e:
        logger.exception("scout failed")
        await msg.edit_text(f"Не удалось собрать разведку по @{username}: {e}")
        return ConversationHandler.END

    context.user_data["scout"] = s

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Все {s['total']}", callback_data="scope:all")],
        [
            InlineKeyboardButton("10", callback_data="scope:10"),
            InlineKeyboardButton("30", callback_data="scope:30"),
            InlineKeyboardButton("50", callback_data="scope:50"),
        ],
        [InlineKeyboardButton("За 6 мес.", callback_data="scope:period6")],
        [InlineKeyboardButton("✕ Отмена", callback_data="scope:cancel")],
    ])
    await msg.edit_text(
        format_scout_message(s) + "\n\nСколько постов анализируем?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    return CHOOSING_SCOPE


# ─────────────────────────────────────────────────────────────────────────────
# Шаг 2: выбор объёма
# ─────────────────────────────────────────────────────────────────────────────
async def choose_scope(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":", 1)[1]

    if choice == "cancel":
        await q.edit_message_text("Отменено.")
        return ConversationHandler.END

    if choice == "period6":
        context.user_data["mode"] = "period"
        context.user_data["months_back"] = 6
        context.user_data["target_count"] = None
        scope_label = "за последние 6 месяцев"
    else:
        context.user_data["mode"] = "count"
        context.user_data["months_back"] = 6
        s = context.user_data["scout"]
        context.user_data["target_count"] = s["total"] if choice == "all" else int(choice)
        scope_label = f"{context.user_data['target_count']} постов"

    context.user_data["scope_label"] = scope_label

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Только экспертные (без личного)", callback_data="filter:professional")],
        [InlineKeyboardButton("Все, кроме мусора", callback_data="filter:all")],
        [InlineKeyboardButton("← Назад", callback_data="filter:back")],
    ])
    await q.edit_message_text(
        f"Объём: {scope_label}.\n\nКакой контент берём?",
        reply_markup=kb,
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
        return await _reshow_scope(q, context)

    context.user_data["content_filter"] = choice
    s = context.user_data["scout"]
    filter_label = "только экспертные" if choice == "professional" else "все, кроме мусора"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Запустить анализ", callback_data="confirm:go")],
        [InlineKeyboardButton("✕ Отмена", callback_data="confirm:cancel")],
    ])
    await q.edit_message_text(
        f"```\n"
        f"Запуск анализа @{s['account']}\n"
        f"{'─' * 28}\n"
        f"Объём  : {context.user_data['scope_label']}\n"
        f"Контент: {filter_label}\n"
        f"Цена   : ≈ ${s['est_cost_usd']} · ≈ {s['est_minutes']} мин\n"
        f"```",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    return CONFIRMING


async def _reshow_scope(q, context) -> int:
    s = context.user_data["scout"]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Все {s['total']}", callback_data="scope:all")],
        [
            InlineKeyboardButton("10", callback_data="scope:10"),
            InlineKeyboardButton("30", callback_data="scope:30"),
            InlineKeyboardButton("50", callback_data="scope:50"),
        ],
        [InlineKeyboardButton("За 6 мес.", callback_data="scope:period6")],
        [InlineKeyboardButton("✕ Отмена", callback_data="scope:cancel")],
    ])
    await q.edit_message_text(
        format_scout_message(s) + "\n\nСколько постов анализируем?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )
    return CHOOSING_SCOPE


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

    def _run():
        collect_posts.collect(
            username,
            months_back=u.get("months_back", 6),
            post_types=["photo", "carousel"],
            content_mode=u["mode"],
            target_count=u.get("target_count") or 30,
        )
        return analyze_posts.analyze(
            username,
            content_filter=u.get("content_filter", "all"),
        )

    try:
        result = await asyncio.to_thread(_run)
    except Exception as e:
        logger.exception("pipeline failed")
        await q.edit_message_text(f"Ошибка прогона @{username}: {e}")
        return ConversationHandler.END

    ok = result.get("posts_ok", "?")
    filt = result.get("filtered_count", "?")
    await q.edit_message_text(
        f"✅ Готово, @{username}.\n"
        f"Проанализировано: {ok} · отфильтровано: {filt}\n"
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
            CHOOSING_SCOPE:  [CallbackQueryHandler(choose_scope, pattern=r"^scope:")],
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
