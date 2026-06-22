"""Core: все пути проекта в одном месте."""

from pathlib import Path

BASE    = Path(__file__).resolve().parents[3]
PROJECT = BASE / "instagram_research_test"
DATA    = PROJECT / "data"


def raw(account: str, filename: str) -> Path:
    return DATA / account / "raw" / filename


def normalized(account: str, filename: str) -> Path:
    return DATA / account / "normalized" / filename


def tmp(account: str, *parts: str) -> Path:
    return DATA / account / "tmp" / Path(*parts)


def accounts_json() -> Path:
    return DATA / "accounts.json"


def payload_json(account: str) -> Path:
    return normalized(account, "payload.json")
