"""Core: обёртка над Google Sheets Apps Script Web App."""

import os
import requests
from pipeline.core.config import load_env


def get_webhook_url() -> str:
    load_env()
    url = os.getenv("GOOGLE_SHEETS_WEBAPP_URL")
    if not url:
        raise EnvironmentError("GOOGLE_SHEETS_WEBAPP_URL не найден в .env")
    return url


def write_payload(payload: dict, dry_run: bool = True, write_mode: str = "replace") -> dict:
    """
    Отправляет payload в Google Sheets.
    dry_run=True: только печатает план, не отправляет.
    write_mode="replace": перезаписывает строки аккаунта (по умолчанию).
    write_mode="append": дописывает строки без удаления старых.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    if dry_run:
        sheets = payload.get("sheets", {})
        print("[DRY RUN] Будет записано:")
        for name, data in sheets.items():
            rows = data.get("rows", [])
            print(f"  {name}: {len(rows)} строк")
        return {"dry_run": True, "sheets": list(sheets.keys())}

    if write_mode == "append":
        _logger.warning(
            "write_mode='append' передан в Apps Script, но Apps Script может не поддерживать этот режим. "
            "Убедитесь, что скрипт обновлён для обработки поля write_mode='append'."
        )

    url = get_webhook_url()
    secret = os.getenv("GOOGLE_SHEETS_SYNC_SECRET", "")
    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ")
    resp = requests.post(
        url,
        json={
            "secret": secret,
            "mode": "write",
            "write_mode": write_mode,
            "spreadsheet_id": spreadsheet_id,
            "start_row": 3,
            "account_label": payload.get("account", ""),
            "rename_headers": True,
            "sheets": payload.get("sheets", {}),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
