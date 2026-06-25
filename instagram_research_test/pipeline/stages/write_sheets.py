"""Stage 16: записывает payload.json в Google Sheets.

Режимы записи:
  replace — заменить строки аккаунта свежесобранными (по умолчанию).
  upsert  — «Актуализировать»: для листов «Посты»/«Reels» слить свежие строки
            с уже записанными по ссылке (история копится), остальные листы
            ведут себя как replace.
"""

import argparse
import json
import logging

from pipeline.core.config import get_account
from pipeline.core.paths import normalized
from pipeline.core import sheets_client
from pipeline.core.sheets_merge import merge_rows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Листы, поддерживающие upsert по ссылке: имя листа → имя колонки-ключа.
_UPSERT_SHEETS = {
    "Посты": "Ссылка на пост",
    "Reels": "Ссылка",
}


def _apply_upsert(payload: dict, username: str) -> list:
    """Для листов «Посты»/«Reels» сливает свежие строки с уже записанными по ссылке.

    Меняет payload["sheets"][...]["rows"] на объединённый набор. Если строки
    аккаунта не удалось прочитать (таблица недоступна), лист убирается из payload
    целиком — Apps Script его не тронет, история сохранится. Возвращает warnings.
    """
    warnings = []
    sheets = payload.get("sheets", {})

    for sheet_name, link_header in _UPSERT_SHEETS.items():
        sheet = sheets.get(sheet_name)
        if not sheet:
            continue  # лист не собирался в этом прогоне

        new_rows = sheet.get("rows", [])
        headers  = sheet.get("headers", [])

        try:
            existing = sheets_client.get_account_rows(sheet_name, username)
        except Exception as e:
            # Не смогли прочитать существующее → НЕ перезаписываем лист, чтобы не
            # потерять историю. Убираем из payload (Apps Script его пропустит).
            warnings.append(
                f"[{sheet_name}] не удалось прочитать существующие строки "
                f"({type(e).__name__}); лист НЕ обновлён, история сохранена"
            )
            logger.warning("upsert: %s @%s — чтение не удалось: %s; лист пропущен",
                           sheet_name, username, e)
            del sheets[sheet_name]
            continue

        merged = merge_rows(existing["rows"], new_rows, headers, link_header)
        sheet["rows"] = merged
        logger.info(
            "upsert: %s @%s — было %d, свежих %d → итог %d строк",
            sheet_name, username, len(existing["rows"]), len(new_rows), len(merged),
        )

    return warnings


def write(username: str, dry_run: bool = False, write_mode: str = "replace") -> dict:
    get_account(username)

    logger.info("[16] write_sheets | @%s | dry_run=%s | write_mode=%s", username, dry_run, write_mode)

    if dry_run:
        logger.info("[DRY RUN] Файлы не отправляются")
        return {"dry_run": True, "rows_written": 0}

    payload_path = normalized(username, "sheets_payload.json")
    if not payload_path.exists():
        raise FileNotFoundError(f"sheets_payload.json не найден: {payload_path}")

    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    upsert_warnings = []
    if write_mode == "upsert":
        upsert_warnings = _apply_upsert(payload, username)

    sheets = payload.get("sheets", {})
    rows_written = sum(len(s.get("rows", [])) for s in sheets.values())

    # На уровне Apps Script запись всегда replace по аккаунту: при upsert набор
    # строк уже объединён в Python, поэтому отправляем как replace.
    send_mode = "replace" if write_mode == "upsert" else write_mode
    result = sheets_client.write_payload(payload, dry_run=False, write_mode=send_mode)

    print(f"\n=== Stage 16: Write Sheets | @{username} (режим: {write_mode}) ===")
    print(f"Листов: {len(sheets)} | строк: {rows_written}")
    for w in upsert_warnings:
        print(f"  ⚠️ {w}")

    return {**result, "rows_written": rows_written, "upsert_warnings": upsert_warnings}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 16: write payload to Google Sheets")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не отправлять запрос")
    parser.add_argument("--write-mode", default="replace", choices=["replace", "upsert"])
    args = parser.parse_args()
    write(args.account, args.dry_run, write_mode=args.write_mode)
