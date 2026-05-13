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
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
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
    "account":    None,
    "started_at": None,
    "running":    False,
    "chat_id":    None,
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
        "Команды:\n"
        "/analyze username — запустить анализ (без Apify, данные уже собраны)\n"
        "/analyze_full username — полный анализ с Apify (платный)\n"
        "/status — статус текущего анализа\n"
        "/help — эта справка\n\n"
        "Пример: /analyze vlada_kliuiko"
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
        await update.message.reply_text("❌ Укажите username. Пример: /analyze vlada_kliuiko")
        return

    username = validate_username(args[0])
    if not username:
        await update.message.reply_text("❌ Неверный формат username. Только латиница, цифры, точки, подчеркивания.")
        return

    if current_job["running"]:
        await update.message.reply_text(
            f"⏳ Уже выполняется анализ @{current_job['account']}.\n"
            f"Дождитесь завершения."
        )
        return

    current_job["account"]    = username
    current_job["started_at"] = time.time()
    current_job["running"]    = True
    current_job["chat_id"]    = update.effective_chat.id

    mode = "без Apify" if skip_apify else "полный (с Apify)"
    await update.message.reply_text(
        f"🚀 Запускаю анализ @{username}...\n"
        f"Режим: {mode}\n"
        f"⏱ Обычно занимает 2-5 минут"
    )
    logger.info(f"Starting pipeline for @{username}, skip_apify={skip_apify}")

    asyncio.create_task(_run_pipeline(update, context, username, skip_apify))


async def _run_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str, skip_apify: bool):
    start = time.time()
    log_path = BASE / "output" / username / "pipeline.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(SCRIPTS_DIR / "run_pipeline.py"), "--account", username]
    if skip_apify:
        cmd.append("--skip-apify")

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

        costs_text = ""
        costs_path = BASE / "output" / username / "costs.json"
        if costs_path.exists():
            costs = json.load(open(costs_path))
            total = costs.get("totals", {})
            apify_text = ""
            try:
                from dotenv import dotenv_values
                vals = dotenv_values(BASE / ".env")
                token = vals.get("APIFY_TOKEN", "")
                if token:
                    async with httpx.AsyncClient(timeout=5) as client:
                        r = await client.get(
                            f"https://api.apify.com/v2/users/me/usage/monthly?token={token}"
                        )
                        services = r.json()["data"].get("monthlyServiceUsage", {})
                        used = sum(v.get("amountAfterVolumeDiscountUsd", 0) for v in services.values())
                        r2 = await client.get(
                            f"https://api.apify.com/v2/users/me?token={token}"
                        )
                        limit = r2.json().get("data", {}).get("plan", {}).get("monthlyUsageCreditsUsd", 5.0)
                        remaining = float(limit) - used
                        apify_text = f"\n   Apify: потрачено ${used:.2f}, остаток ${remaining:.2f}"
            except Exception:
                apify_text = "\n   Apify: см. console.apify.com"
            costs_text = (
                f"\n💰 OpenAI: ${total.get('total_cost_usd', 0):.4f} "
                f"({total.get('total_tokens', 0)} токенов)"
                f"{apify_text}"
            )

        if result.returncode == 0:
            text = (
                f"✅ Анализ @{username} завершен!\n\n"
                f"⏱ Время: {minutes} мин {seconds} сек{costs_text}\n"
                f"🔗 Таблица: {SPREADSHEET_URL}"
            )
        else:
            text = (
                f"⚠️ Анализ @{username} завершен с ошибками.\n\n"
                f"⏱ Время: {minutes} мин {seconds} сек{costs_text}\n"
                f"📄 Лог: {log_path}\n"
                f"🔗 Таблица: {SPREADSHEET_URL}"
            )

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        logger.info(f"Pipeline for @{username} finished, returncode={result.returncode}")

    except Exception as e:
        logger.exception(f"Pipeline error for @{username}: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ Ошибка при анализе @{username}: {str(e)[:200]}"
        )
    finally:
        current_job["running"]    = False
        current_job["account"]    = None
        current_job["started_at"] = None
        current_job["chat_id"]    = None


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


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_allowed(update):
        await update.message.reply_text("Используйте /analyze username для запуска")
    else:
        await update.message.reply_text(f"⛔ Нет доступа. Ваш chat_id: {update.effective_chat.id}")


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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
