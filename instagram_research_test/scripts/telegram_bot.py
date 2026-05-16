"""Telegram bot for running the Instagram competitor research pipeline."""

import asyncio
import json
import logging
import os
import re
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
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

BASE        = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"

load_dotenv(BASE / ".env", override=True)

current_job: dict = {
    "account":             None,
    "started_at":          None,
    "running":             False,
    "chat_id":             None,
    "apify_balance_before": None,
}


def get_allowed_ids() -> set:
    raw = os.environ.get("TELEGRAM_ALLOWED_IDS", "")
    if not raw.strip():
        return set()
    return {int(x.strip()) for x in raw.split(",") if x.strip().isdigit()}


def is_allowed(update: Update) -> bool:
    return update.effective_chat.id in get_allowed_ids()


def validate_username(username: str):
    username = username.lstrip("@").strip()
    if not re.match(r'^[a-zA-Z0-9._]{1,30}$', username):
        return None
    return username


async def _get_apify_balance() -> float | None:
    """Return current Apify monthly spend in USD, or None on failure."""
    try:
        from dotenv import dotenv_values
        token = dotenv_values(BASE / ".env").get("APIFY_TOKEN", "")
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


def _build_stages_summary(username: str) -> str:
    """Read normalized/output files and build a numbered per-stage summary string."""
    norm = BASE / "data" / username / "normalized"
    out  = BASE / "output" / username
    lines = []

    def _j(path):
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except Exception:
            return None

    # 1. Профиль и закрепы
    pi = _j(norm / "pinned_posts_index.json")
    if pi:
        n = len(pi.get("pinned_posts") or [])
        lines.append(f"1. Профиль и закрепы — ✅ {n} закрепа найдено")
    else:
        lines.append("1. Профиль и закрепы — ⏭ пропущен")

    # 2. Детали закрепов
    a2b = _j(norm / "stage5a2b_pinned_posts_details.json")
    if a2b:
        posts = a2b.get("posts") or []
        n_sidecar = sum(1 for p in posts if p.get("media_type") == "Sidecar")
        detail = f"есть {n_sidecar} карусели" if n_sidecar else "нет каруселей"
        lines.append(f"2. Детали закрепов — ✅ {len(posts)} поста, {detail}")
    else:
        lines.append("2. Детали закрепов — ⏭ пропущен")

    # 3. Семантика закрепов
    a2c = _j(norm / "stage5a2c_pinned_posts_semantic.json")
    if a2c:
        posts = a2c.get("posts") or []
        n_cta  = sum(1 for p in posts if (p.get("google_sheet_fields") or {}).get("Какой CTA"))
        n_role = sum(1 for p in posts if (p.get("google_sheet_fields") or {}).get("Роль в воронке"))
        lines.append(f"3. Семантика закрепов — ✅ {len(posts)} поста, CTA у {n_cta}, роль у {n_role}")
    else:
        lines.append("3. Семантика закрепов — ⏭ пропущен")

    # 4. Валидация семантики
    a2c_fix = _j(norm / "stage5a2c_pinned_posts_semantic_fixed.json")
    if a2c_fix:
        n_notes = sum(len(p.get("postprocessing_notes") or []) for p in (a2c_fix.get("posts") or []))
        if n_notes:
            lines.append(f"4. Валидация семантики — ⚠️ {n_notes} правки применены")
        else:
            lines.append("4. Валидация семантики — ✅ правок не потребовалось")
    elif a2c:
        lines.append("4. Валидация семантики — ✅ правок не потребовалось")
    else:
        lines.append("4. Валидация семантики — ⏭ пропущен")

    # 5. Хуки с обложек
    a2d = _j(norm / "stage5a2d_pinned_hooks.json")
    if a2d:
        posts = a2d.get("posts") or []
        n_ok = sum(1 for p in posts if (p.get("hook") or {}).get("data_status") == "ok")
        lines.append(f"5. Хуки с обложек — ✅ {n_ok}/{len(posts)} хуков извлечено")
    else:
        lines.append("5. Хуки с обложек — ⏭ пропущен")

    # 6. Анализ bio
    a2e = _j(norm / "stage5a2e_bio_semantic.json")
    if a2e:
        _ru = {"dlya_kogo": "аудитория", "obeshchanie": "оффер",
                "trust_arguments": "доверие", "social_proof": "соцдоки", "cta": "CTA"}
        filled = [_ru.get(k, k) for k, v in (a2e.get("fields") or {}).items()
                  if isinstance(v, dict) and v.get("data_status") == "ok"]
        lines.append(f"6. Анализ bio — {'✅ ' + ', '.join(filled) if filled else '⚠️ поля не найдены'}")
    else:
        lines.append("6. Анализ bio — ⏭ пропущен")

    # 7. Ссылка из bio
    a2f = _j(norm / "stage5a2f_link_destination.json")
    if a2f:
        dt = (a2f.get("result") or {}).get("destination_type") or "неизвестно"
        lines.append(f"7. Ссылка из bio — ✅ тип: {dt}")
    else:
        lines.append("7. Ссылка из bio — ⏭ пропущен")

    # 8. Анализ лендинга
    a2g = _j(norm / "stage5a2g_landing_analysis.json")
    if a2g:
        fields = a2g.get("fields") or {}
        n_ok = sum(1 for v in fields.values() if isinstance(v, dict) and v.get("data_status") == "ok")
        lines.append(f"8. Анализ лендинга — ✅ {n_ok}/{len(fields)} полей заполнено")
    else:
        lines.append("8. Анализ лендинга — ⏭ пропущен")

    # 9. Хайлайты
    hi  = _j(norm / "highlights_index.json")
    b2s = _j(norm / "stage5b2_highlights_stories_summary.json")
    if hi:
        total = len(hi.get("highlights") or [])
        if b2s:
            ok_results  = [r for r in (b2s.get("results") or []) if r.get("status") == "OK"]
            n_in_table  = len(ok_results)
            titles      = [r.get("title", "?") for r in ok_results[:5]]
            table_str   = ", ".join(titles)
            n_not       = total - n_in_table
            if n_not > 0:
                table_str += f" (+{n_not} не вошли)"
            lines.append(f"9. Хайлайты — ✅ {total} штук\n   В таблице: {table_str}")
        else:
            lines.append(f"9. Хайлайты — ✅ {total} штук, названия и порядок")
    else:
        lines.append("9. Хайлайты — ⏭ пропущен")

    # 10. Vision хайлайтов
    b2v = _j(norm / "stage5b2v_highlights_visual.json")
    if b2v:
        analyzed = b2v.get("analyzed_highlights") or []
        n_ok      = sum(1 for h in analyzed if h.get("fields") and not h.get("skipped"))
        n_skipped = sum(1 for h in analyzed if h.get("skipped"))
        if n_ok:
            lines.append(f"10. Vision хайлайтов — ✅ {n_ok} из {len(analyzed)} проанализировано")
        elif n_skipped == len(analyzed):
            lines.append("10. Vision хайлайтов — ⚠️ пропущен, нет данных сторис")
        else:
            lines.append(f"10. Vision хайлайтов — ⚠️ {n_ok} OK, {n_skipped} пропущено")
    else:
        lines.append("10. Vision хайлайтов — ⏭ пропущен")

    # 11. Сборка данных
    d1 = _j(out / "stage5d1" / "stage5d1_summary.json")
    if d1:
        n_warns = len(d1.get("all_warnings") or [])
        lines.append(f"11. Сборка данных — ✅ все листы заполнены, {n_warns} предупреждений")
    else:
        lines.append("11. Сборка данных — ⏭ пропущен")

    # 12. Запись в таблицу
    wr = _j(out / "stage5d3_write" / "write_response.json")
    if wr:
        if wr.get("ok"):
            lines.append("12. Запись в таблицу — ✅ данные обновлены")
        else:
            lines.append("12. Запись в таблицу — ❌ ошибка записи")
    else:
        lines.append("12. Запись в таблицу — ⏭ пропущен")

    return "\n".join(lines)


def _build_changes_summary(username: str) -> str | None:
    """Compare current vs previous profile snapshot; return change description or None."""
    norm = BASE / "data" / username / "normalized"

    def _j(path):
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except Exception:
            return None

    current  = _j(norm / "profile_summary.json")
    previous = _j(norm / "previous_profile_snapshot.json")

    if previous is None or current is None:
        return None

    def _val(d: dict, key: str) -> str:
        v = (d or {}).get(key)
        return str(v.get("value", "") if isinstance(v, dict) else (v or "")).strip()

    changes = []

    if _val(current, "bio_text") != _val(previous, "bio_text"):
        changes.append("bio изменился")

    cur_url  = _val(current,  "external_url")
    prev_url = _val(previous, "external_url")
    if cur_url != prev_url:
        changes.append(f"ссылка в bio: {prev_url or '—'} → {cur_url or '—'}")

    # pinned count
    cur_pi  = _j(norm / "pinned_posts_index.json")
    prev_pi = _j(norm / "previous_pinned_snapshot.json")
    if cur_pi is not None and prev_pi is not None:
        cur_n  = len(cur_pi.get("pinned_posts") or [])
        prev_n = len(prev_pi.get("pinned_posts") or [])
        if cur_n != prev_n:
            changes.append(f"закрепов: было {prev_n} → стало {cur_n}")

    # highlights count
    cur_hi  = _j(norm / "highlights_index.json")
    prev_hi = _j(norm / "previous_highlights_snapshot.json")
    if cur_hi is not None and prev_hi is not None:
        cur_n  = len(cur_hi.get("highlights") or [])
        prev_n = len(prev_hi.get("highlights") or [])
        if cur_n != prev_n:
            changes.append(f"хайлайтов: было {prev_n} → стало {cur_n}")

    if not changes:
        return None

    lines = ["🔄 Изменения с прошлого запуска:"] + [f"- {c}" for c in changes]
    return "\n".join(lines)


def _get_stale_count(username: str) -> int:
    """Return number of stale highlight IDs recorded for a username."""
    path = BASE / "data" / username / "normalized" / "stale_highlights.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return len(data.get("stale_highlight_ids") or [])
    except Exception:
        return 0


def _get_remaining_highlights(username: str) -> tuple[int, int]:
    """Return (already_processed, remaining) for a username."""
    norm = BASE / "data" / username / "normalized"

    def _j(path):
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        except Exception:
            return None

    hi  = _j(norm / "highlights_index.json")
    b2s = _j(norm / "stage5b2_highlights_stories_summary.json")
    if not hi or not b2s:
        return 0, 0
    total     = len(hi.get("highlights") or [])
    processed = b2s.get("highlights_ok", 0)
    remaining = max(0, total - processed)
    return processed, remaining


def _highlights_load_keyboard(username: str, remaining: int,
                               stale_count: int = 0) -> InlineKeyboardMarkup:
    buttons = []
    if remaining > 0:
        cost_5   = round(min(5,  remaining) * 0.03, 2)
        cost_10  = round(min(10, remaining) * 0.03, 2)
        cost_all = round(remaining * 0.03, 2)
        row = []
        if remaining >= 1:
            row.append(InlineKeyboardButton(f"+5 (~${cost_5:.2f})",   callback_data=f"hl_more_5:{username}"))
        if remaining >= 10:
            row.append(InlineKeyboardButton(f"+10 (~${cost_10:.2f})", callback_data=f"hl_more_10:{username}"))
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton(
            f"Все оставшиеся (~${cost_all:.2f})", callback_data=f"hl_more_all:{username}"
        )])
    if stale_count > 0:
        cost_stale = round(stale_count * 0.03, 2)
        buttons.append([InlineKeyboardButton(
            f"🔄 Обновить протухшие ({stale_count} шт. ~${cost_stale:.2f})",
            callback_data=f"hl_refresh_stale:{username}",
        )])
    return InlineKeyboardMarkup(buttons)


def _main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Новый анализ",    callback_data="new_analysis"),
            InlineKeyboardButton("⚡ Быстрый анализ", callback_data="quick_analysis"),
        ],
        [InlineKeyboardButton("📊 Статус", callback_data="status")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not is_allowed(update):
        await update.message.reply_text(
            f"⛔ У вас нет доступа.\n"
            f"Ваш chat_id: {chat_id}\n"
            f"Сообщите его администратору."
        )
        return
    await update.message.reply_text(
        "Привет! Я бот для анализа Instagram-конкурентов.\n\n"
        "🔍 Новый анализ — полный запуск с Apify (сбор + OpenAI)\n"
        "⚡ Быстрый анализ — только OpenAI по уже собранным данным\n\n"
        "Или используйте команды:\n"
        "/analyze username — быстрый анализ\n"
        "/analyze_full username — полный анализ\n"
        "/status — текущий статус",
        reply_markup=_main_keyboard(),
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_allowed(update):
        await query.edit_message_text("⛔ Нет доступа.")
        return

    if query.data == "status":
        if current_job["running"]:
            elapsed = int((time.time() - current_job["started_at"]) / 60)
            await query.edit_message_text(
                f"⏳ Выполняется анализ @{current_job['account']}\n"
                f"Запущен: {elapsed} мин назад",
                reply_markup=_main_keyboard(),
            )
        else:
            await query.edit_message_text("✅ Нет активных анализов", reply_markup=_main_keyboard())
        return

    if query.data in ("new_analysis", "quick_analysis"):
        context.user_data["waiting_mode"] = query.data
        label = "полный (с Apify)" if query.data == "new_analysis" else "быстрый (без Apify)"
        await query.edit_message_text(
            f"Режим: {label}\n\n"
            "Введите username аккаунта Instagram для анализа\n"
            "(например: kate.jet):"
        )
        return

    if query.data.startswith("hl_more_"):
        parts    = query.data.split(":", 1)
        amount   = parts[0][len("hl_more_"):]   # "5", "10", "all"
        username = parts[1] if len(parts) > 1 else ""

        if not username:
            await query.edit_message_text("❌ Ошибка: username не найден в callback")
            return

        if current_job["running"]:
            await query.answer(f"⏳ Уже выполняется анализ @{current_job['account']}. Дождитесь завершения.")
            return

        processed, remaining = _get_remaining_highlights(username)

        if remaining == 0:
            await query.edit_message_text(f"✅ Все хайлайты @{username} уже загружены")
            return

        if amount == "all":
            limit = remaining
        else:
            try:
                limit = int(amount)
            except ValueError:
                await query.edit_message_text("❌ Неверный параметр кнопки")
                return

        await query.edit_message_text(
            f"⏳ Загружаю ещё {limit} хайлайтов для @{username}...\n"
            f"   (позиции {processed + 1}–{processed + limit})"
        )

        current_job["account"]              = username
        current_job["started_at"]           = time.time()
        current_job["running"]              = True
        current_job["chat_id"]              = update.effective_chat.id
        current_job["apify_balance_before"] = await _get_apify_balance()

        asyncio.create_task(
            _run_pipeline(update, context, username,
                          skip_apify=False,
                          highlights_limit=limit,
                          highlights_from=processed)
        )
        return

    if query.data.startswith("hl_refresh_stale:"):
        username = query.data[len("hl_refresh_stale:"):]

        if current_job["running"]:
            await query.answer(f"⏳ Уже выполняется анализ @{current_job['account']}. Дождитесь завершения.")
            return

        stale_count = _get_stale_count(username)
        if stale_count == 0:
            await query.edit_message_text(f"✅ Протухших хайлайтов для @{username} нет")
            return

        await query.edit_message_text(
            f"⏳ Обновляю {stale_count} протухших хайлайтов для @{username}..."
        )

        current_job["account"]              = username
        current_job["started_at"]           = time.time()
        current_job["running"]              = True
        current_job["chat_id"]              = update.effective_chat.id
        current_job["apify_balance_before"] = await _get_apify_balance()

        asyncio.create_task(
            _run_pipeline(update, context, username,
                          skip_apify=False,
                          refresh_stale=True)
        )


async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _start_analysis(update, context, skip_apify=True)


async def analyze_full(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _start_analysis(update, context, skip_apify=False)


async def _start_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE, skip_apify: bool):
    if not is_allowed(update):
        await update.message.reply_text(f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}")
        return

    args = context.args
    if not args:
        await update.message.reply_text("❌ Укажите username. Пример: /analyze kate.jet")
        return

    username = validate_username(args[0])
    if not username:
        await update.message.reply_text("❌ Неверный формат username. Только латиница, цифры, точки, подчеркивания.")
        return

    await _launch(update, context, username, skip_apify)


async def _launch(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str, skip_apify: bool):
    if current_job["running"]:
        await update.message.reply_text(
            f"⏳ Уже выполняется анализ @{current_job['account']}.\n"
            f"Дождитесь завершения."
        )
        return

    current_job["account"]             = username
    current_job["started_at"]          = time.time()
    current_job["running"]             = True
    current_job["chat_id"]             = update.effective_chat.id
    current_job["apify_balance_before"] = await _get_apify_balance()

    mode = "быстрый (без Apify)" if skip_apify else "полный (с Apify)"
    await update.message.reply_text(
        f"🚀 Запускаю анализ @{username}...\n"
        f"Режим: {mode}\n"
        f"⏱ Обычно занимает 2-5 минут"
    )
    logger.info(f"Starting pipeline for @{username}, skip_apify={skip_apify}")

    asyncio.create_task(_run_pipeline(update, context, username, skip_apify))


async def _run_pipeline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    username: str,
    skip_apify: bool,
    highlights_limit: int = 5,
    highlights_from: int = 0,
    refresh_stale: bool = False,
):
    start = time.time()
    log_path = BASE / "output" / username / "pipeline.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(SCRIPTS_DIR / "run_pipeline.py"), "--account", username]
    if skip_apify:
        cmd.append("--skip-apify")
    if refresh_stale:
        cmd.append("--refresh-stale")
    else:
        cmd += ["--highlights-limit", str(highlights_limit)]
        if highlights_from > 0:
            cmd += ["--highlights-from", str(highlights_from)]

    try:
        loop = asyncio.get_running_loop()
        with open(log_path, "w", encoding="utf-8") as log_file:
            result = await loop.run_in_executor(
                None,
                lambda: __import__("subprocess").run(
                    cmd,
                    cwd=str(BASE),
                    env=os.environ.copy(),
                    stdout=log_file,
                    stderr=log_file,
                )
            )

        elapsed = time.time() - start
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        # OpenAI + Apify costs from costs.json (written by collect_costs stage)
        openai_cost_str = ""
        apify_cost_str  = ""
        costs_path = BASE / "output" / username / "costs.json"
        if costs_path.exists():
            try:
                costs_data   = json.loads(costs_path.read_text())
                totals       = costs_data.get("totals", {})
                apify_stages = costs_data.get("apify_stages") or {}

                openai_cost_str = (
                    f"OpenAI ${totals.get('total_cost_usd', 0):.4f}"
                    f" ({totals.get('total_tokens', 0)} токенов)"
                )

                apify_total = totals.get("apify_total_usd")
                if apify_stages:
                    parts = []
                    for s, v in apify_stages.items():
                        label = f"{s} ${v['cost_usd']:.4f}"
                        if v.get("detail"):
                            label += f" ({v['detail']})"
                        parts.append(label)
                    breakdown = ", ".join(parts)
                    if apify_total is not None:
                        apify_cost_str = f"Apify ${apify_total:.4f}: {breakdown}"
                    else:
                        apify_cost_str = f"Apify {breakdown}"
            except Exception:
                pass

        # Fallback: Apify balance delta if costs.json had no apify data
        if not apify_cost_str:
            apify_balance_after  = await _get_apify_balance()
            apify_balance_before = current_job.get("apify_balance_before")
            if apify_balance_after is not None and apify_balance_before is not None:
                apify_delta = round(apify_balance_after - apify_balance_before, 4)
                apify_cost_str = f"Apify ${apify_delta:.4f}"
            else:
                apify_cost_str = "Apify см. console.apify.com"

        # Per-stage summary
        stages_text   = _build_stages_summary(username)
        costs_line    = f"13. Затраты — ✅ {openai_cost_str}, {apify_cost_str}"
        changes_block = _build_changes_summary(username)

        header = "✅ Анализ @{u} завершен!" if result.returncode == 0 else "⚠️ Анализ @{u} завершен с ошибками."
        header = header.format(u=username)

        text = (
            f"{header}\n\n"
            f"⏱ Время: {minutes} мин {seconds} сек\n\n"
            f"📋 Стадии:\n{stages_text}\n{costs_line}\n\n"
            + (f"{changes_block}\n\n" if changes_block else "")
            + f"🔗 Таблица: {SPREADSHEET_URL}"
        )
        if result.returncode != 0:
            text += f"\n📄 Лог: {log_path}"

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        logger.info(f"Pipeline for @{username} finished, returncode={result.returncode}")

        # If highlights were limited or stale, offer action buttons
        _, remaining  = _get_remaining_highlights(username)
        stale_count   = _get_stale_count(username)
        if remaining > 0 or stale_count > 0:
            keyboard = _highlights_load_keyboard(username, remaining, stale_count)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Догрузить ещё хайлайты для @{username}:",
                reply_markup=keyboard,
            )

    except Exception as e:
        logger.exception(f"Pipeline error for @{username}: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Ошибка при анализе @{username}: {str(e)[:200]}"
        )
    finally:
        current_job["running"]             = False
        current_job["account"]             = None
        current_job["started_at"]          = None
        current_job["chat_id"]             = None
        current_job["apify_balance_before"] = None


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text(f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}")
        return
    if current_job["running"]:
        elapsed = int((time.time() - current_job["started_at"]) / 60)
        await update.message.reply_text(
            f"⏳ Выполняется анализ @{current_job['account']}\n"
            f"Запущен: {elapsed} мин назад"
        )
    else:
        await update.message.reply_text("✅ Нет активных анализов")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text(f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}")
        return

    mode = context.user_data.pop("waiting_mode", None)
    if mode in ("new_analysis", "quick_analysis"):
        username = validate_username(update.message.text or "")
        if not username:
            await update.message.reply_text(
                "❌ Неверный формат username. Только латиница, цифры, точки, подчеркивания.\n"
                "Попробуйте ещё раз:"
            )
            context.user_data["waiting_mode"] = mode
            return
        skip_apify = (mode == "quick_analysis")
        await _launch(update, context, username, skip_apify)
    else:
        await update.message.reply_text(
            "Используйте /analyze username для запуска",
            reply_markup=_main_keyboard(),
        )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не найден в .env")
        sys.exit(1)

    allowed = get_allowed_ids()
    if not allowed:
        logger.error("TELEGRAM_ALLOWED_IDS не задан в .env")
        sys.exit(1)

    logger.info(f"Бот запускается. Разрешенных пользователей: {len(allowed)}")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("help",         start))
    app.add_handler(CommandHandler("analyze",      analyze))
    app.add_handler(CommandHandler("analyze_full", analyze_full))
    app.add_handler(CommandHandler("status",       status))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
