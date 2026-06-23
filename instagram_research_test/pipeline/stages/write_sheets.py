"""Stage 16: записывает payload.json в Google Sheets."""

import argparse
import json
import logging

from pipeline.core.config import get_account
from pipeline.core.paths import normalized
from pipeline.core import sheets_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


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

    sheets = payload.get("sheets", {})
    rows_written = sum(len(s.get("rows", [])) for s in sheets.values())

    result = sheets_client.write_payload(payload, dry_run=False, write_mode=write_mode)

    print(f"\n=== Stage 16: Write Sheets | @{username} ===")
    print(f"Листов: {len(sheets)} | строк: {rows_written}")

    return {**result, "rows_written": rows_written}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 16: write payload to Google Sheets")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не отправлять запрос")
    parser.add_argument("--write-mode", default="replace", choices=["replace", "append"])
    args = parser.parse_args()
    write(args.account, args.dry_run, write_mode=args.write_mode)
