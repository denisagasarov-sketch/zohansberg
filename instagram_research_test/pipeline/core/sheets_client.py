"""Core: обёртка над Google Sheets Apps Script Web App."""

import os
import requests
from pipeline.core.config import load_env


def get_webhook_url() -> str:
    load_env()
    url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")
    if not url:
        raise EnvironmentError("GOOGLE_SHEETS_WEBHOOK_URL не найден в .env")
    return url


def write_payload(payload: dict, dry_run: bool = True) -> dict:
    """
    Отправляет payload в Google Sheets.
    dry_run=True: только печатает план, не отправляет.
    """
    if dry_run:
        sheets = payload.get("sheets", {})
        print("[DRY RUN] Будет записано:")
        for name, data in sheets.items():
            rows = data.get("rows", [])
            print(f"  {name}: {len(rows)} строк")
        return {"dry_run": True, "sheets": list(sheets.keys())}

    url = get_webhook_url()
    resp = requests.post(
        url,
        json={"action": "write", **payload},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
