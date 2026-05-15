"""Entry-point for the full Instagram competitor research pipeline."""

import argparse
import glob
import os
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BASE        = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"

load_dotenv(BASE / ".env", override=True)

REQUIRED_ENV = ["OPENAI_API_KEY", "APIFY_TOKEN", "GOOGLE_SHEETS_SYNC_SECRET"]

STAGE_ORDER = [
    {
        "name": "5A-1: Сбор профиля и закрепов",
        "script": "stage5a1_run_local.py",
        "requires_apify": True,
        "requires_openai": False,
        "cost_estimate": "$0.07–0.30",
    },
    {
        "name": "5A-2B: Детали закрепов",
        "script": "stage5a2b_run_local.py",
        "requires_apify": False,
        "requires_openai": False,
        "cost_estimate": "$0",
        "extra_args": ["--from-existing-raw"],
    },
    {
        "name": "5A-2C: Семантика закрепов (анализ)",
        "script": "stage5a2c_run_local.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.01–0.05",
        "extra_args": ["--analyze", "--budget-max-usd", "0.10"],
    },
    {
        "name": "5A-2C: Семантика закрепов (фикс)",
        "script": "stage5a2c_run_local.py",
        "requires_apify": False,
        "requires_openai": False,
        "cost_estimate": "$0",
        "extra_args": ["--validate-existing-output", "--write-fixed"],
    },
    {
        "name": "5A-2D: Хуки закрепов (Vision)",
        "script": "stage5a2d_pinned_hooks_visual.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.01",
    },
    {
        "name": "5A-2E: Семантика bio",
        "script": "stage5a2e_bio_semantic_analyzer.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.001",
    },
    {
        "name": "5A-2F: Классификатор ссылки",
        "script": "stage5a2f_link_destination_classifier.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.001",
    },
    {
        "name": "5A-2G: Анализ лендинга",
        "script": "stage5a2g_landing_analyzer.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.05–0.10",
    },
    {
        "name": "5B-1: Сбор хайлайтов",
        "script": "stage5b1_run_local.py",
        "requires_apify": True,
        "requires_openai": False,
        "cost_estimate": "$0.10–0.50",
    },
    {
        "name": "5B-2: Сбор сторис хайлайтов",
        "script": "stage5b2_run_local.py",
        "requires_apify": True,
        "requires_openai": False,
        "cost_estimate": "$0.10–2.00",
    },
    {
        "name": "5B-2V: Vision для хайлайтов",
        "script": "stage5b2v_highlights_visual_analyzer.py",
        "requires_apify": False,
        "requires_openai": True,
        "cost_estimate": "$0.05–0.50",
        "skip_if_no_stories": True,
    },
    {
        "name": "5D-1: Сборка payload",
        "script": "stage5d1_run_local.py",
        "requires_apify": False,
        "requires_openai": False,
        "cost_estimate": "$0",
        "extra_args": ["--require-pinned-semantic"],
    },
    {
        "name": "5D-3: Запись в Google Sheets",
        "script": "stage5d3_write_google_sheets.py",
        "requires_apify": False,
        "requires_openai": False,
        "cost_estimate": "$0",
        "extra_args": ["--write", "--confirm-write", "--allow-row-count-drift"],
    },
    {
        "name": "Подсчет затрат",
        "script": "collect_costs.py",
        "requires_apify": False,
        "requires_openai": False,
        "cost_estimate": "$0",
    },
]


def check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] Отсутствуют переменные окружения: {', '.join(missing)}")
        print(f"Добавьте их в файл .env и повторите запуск.")
        sys.exit(1)


def has_stories_data(account: str) -> bool:
    pattern = str(BASE / "data" / account / "raw" / "stage5b2_stories_*_raw.json")
    return len(glob.glob(pattern)) > 0


def run_stage(stage: dict, account: str, dry_run: bool, skip_apify: bool) -> bool:
    if skip_apify and stage.get("requires_apify"):
        print(f"[SKIP] Пропущен (--skip-apify): {stage['name']}")
        return True

    if stage.get("skip_if_no_stories") and not has_stories_data(account):
        print(f"[SKIP] Пропущен (нет данных сторис): {stage['name']}")
        return True

    cmd = [sys.executable, str(SCRIPTS_DIR / stage["script"]),
           "--account", account]
    if dry_run:
        cmd.append("--dry-run")
    if stage.get("extra_args"):
        cmd.extend(stage["extra_args"])

    result = subprocess.run(cmd, cwd=str(BASE), env=os.environ)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Instagram Competitor Research Pipeline")
    parser.add_argument("--account",    required=True, help="Instagram username")
    parser.add_argument("--estimate",   action="store_true", help="Показать оценку затрат")
    parser.add_argument("--dry-run",    action="store_true", help="Dry-run без реальных API")
    parser.add_argument("--skip-apify", action="store_true", help="Пропустить Apify stages")
    args = parser.parse_args()

    account    = args.account
    dry_run    = args.dry_run
    skip_apify = args.skip_apify

    check_env()

    if args.estimate:
        print(f"\nАккаунт: @{account}")
        print(f"\nОжидаемые затраты по stages:")
        for stage in STAGE_ORDER:
            marker = "[Apify]" if stage.get("requires_apify") else "[OpenAI]" if stage.get("requires_openai") else "[free]"
            print(f"  {marker} {stage['name']}: {stage['cost_estimate']}")
        print(f"\n  Итого: $0.30 – $1.50 (зависит от числа хайлайтов)")
        print(f"\nЗапустить полный анализ? [y/n]: ", end="", flush=True)
        ans = input().strip().lower()
        if ans != "y":
            print("Отменено.")
            sys.exit(0)

    total      = len(STAGE_ORDER)
    completed  = 0
    failed     = 0
    start_time = time.time()

    for i, stage in enumerate(STAGE_ORDER):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{total}] {stage['name']}")
        print(f"{'='*60}")

        ok = run_stage(stage, account, dry_run, skip_apify)

        if ok:
            completed += 1
            print(f"[OK] {stage['name']}")
        else:
            failed += 1
            print(f"[ERROR] Stage завершился с ошибкой: {stage['name']}")
            print("Pipeline остановлен.")
            break

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'='*60}")
    if failed == 0:
        print(f"✅ Анализ @{account} завершен")
    else:
        print(f"⚠️  Анализ @{account} завершен с ошибками ({failed} stages)")
    print(f"⏱  Время: {minutes} мин {seconds} сек")
    costs_path = BASE / "output" / account / "costs.json"
    if costs_path.exists():
        import json
        costs = json.load(open(costs_path))
        total_c = costs.get("totals", {})
        print(f"💰 OpenAI затраты: ${total_c.get('total_cost_usd', 0):.4f} "
              f"({total_c.get('total_tokens', 0)} токенов)")
        print(f"   Apify: см. console.apify.com")
    print(f"📋 Выполнено stages: {completed}/{total}")
    print(f"🔗 Таблица: {SPREADSHEET_URL}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
