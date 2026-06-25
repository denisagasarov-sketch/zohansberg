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


_DEFAULT_SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ"


def _request_base() -> tuple[str, dict]:
    """URL веб-приложения + общие поля запроса (secret, spreadsheet_id)."""
    url = get_webhook_url()
    base = {
        "secret": os.getenv("GOOGLE_SHEETS_SYNC_SECRET", ""),
        "spreadsheet_id": os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", _DEFAULT_SPREADSHEET_ID),
    }
    return url, base


def write_payload(payload: dict, dry_run: bool = True, write_mode: str = "replace") -> dict:
    """
    Отправляет payload в Google Sheets.
    dry_run=True: только печатает план, не отправляет.

    Apps Script всегда заменяет строки аккаунта по колонке «Конкурент»
    (replace-семантика). Режим «Актуализировать» (upsert) реализован на стороне
    Python в write_sheets: существующие строки сливаются со свежими ДО отправки,
    поэтому сюда уже приходит полный актуальный набор строк аккаунта.
    """
    if dry_run:
        sheets = payload.get("sheets", {})
        print("[DRY RUN] Будет записано:")
        for name, data in sheets.items():
            rows = data.get("rows", [])
            print(f"  {name}: {len(rows)} строк")
        return {"dry_run": True, "sheets": list(sheets.keys())}

    url, base = _request_base()
    resp = requests.post(
        url,
        json={
            **base,
            "mode": "write",
            "write_mode": write_mode,
            "start_row": 3,
            "account_label": payload.get("account", ""),
            "rename_headers": True,
            "sheets": payload.get("sheets", {}),
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def get_account_rows(sheet_name: str, account_label: str) -> dict:
    """Читает полные строки одного аккаунта из листа (Apps Script mode=get_account_rows).

    Возврат: {"headers": [...], "rows": [[...], ...]}. Пустой rows валиден
    (аккаунт ещё не записан в этот лист).

    Поднимает RuntimeError при сетевой ошибке или ok=false — вызывающий код
    (upsert) обязан отличать «нет строк» от «не смог прочитать», чтобы не
    затереть историю при недоступности таблицы.
    """
    url, base = _request_base()
    resp = requests.post(
        url,
        json={
            **base,
            "mode": "get_account_rows",
            "sheet_name": sheet_name,
            "account_label": account_label,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(
            f"get_account_rows ok=false для листа '{sheet_name}' @{account_label}: "
            f"{data.get('errors') or data}"
        )
    return {"headers": data.get("headers") or [], "rows": data.get("rows") or []}
