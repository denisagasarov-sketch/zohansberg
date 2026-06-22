"""Core: загрузка конфигурации из accounts.json и .env."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[3]  # корень репо
_ACCOUNTS_PATH = BASE / "instagram_research_test" / "data" / "accounts.json"


def load_env() -> None:
    """Загружает .env из корня проекта."""
    env_path = BASE / "instagram_research_test" / ".env"
    load_dotenv(dotenv_path=env_path)


def get_account(username: str) -> dict:
    """Возвращает конфиг аккаунта из accounts.json."""
    data = json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))
    accounts = data if isinstance(data, list) else [data]
    for acc in accounts:
        if acc.get("username") == username:
            return acc
    raise ValueError(f"Аккаунт '{username}' не найден в accounts.json")


def get_apify_token() -> str:
    load_env()
    token = os.getenv("APIFY_TOKEN") or os.getenv("APIFY_API_TOKEN")
    if not token:
        raise EnvironmentError("APIFY_TOKEN не найден в .env")
    return token


def get_openai_key() -> str:
    load_env()
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or not key.startswith("sk-"):
        raise EnvironmentError("OPENAI_API_KEY не найден или невалиден в .env")
    return key
