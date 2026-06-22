"""Stage 5B-1: сборщик индекса Instagram Highlights.

Один вызов Apify возвращает список хайлайтов профиля. Стейдж сохраняет
сырой ответ и нормализованный highlights_index.json без OpenAI и медиа.

Использование:
  python3 -m pipeline.stages.collect_highlights --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.collect_highlights --account vlada_kliuiko --limit 12
"""

import argparse
import json
import logging
from datetime import datetime, timezone

from pipeline.core.apify_client import run_actor
from pipeline.core.config import get_account
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTOR_ID = "singhera07/instagram-scraper"


def _field_ok(value, source_ref: str, notes: str = "") -> dict:
    return {
        "value": value,
        "data_status": "ok",
        "source_ref": source_ref,
        "confidence": "high",
        "notes": notes,
    }


def _field_missing(source_ref: str, notes: str) -> dict:
    return {
        "value": None,
        "data_status": "missing",
        "source_ref": source_ref,
        "confidence": None,
        "notes": notes,
    }


def _safe_item(item: dict) -> dict:
    result = {}
    for key, value in item.items():
        if isinstance(value, str) and len(value) > 5000:
            result[key] = value[:5000] + "...[truncated]"
        elif isinstance(value, bytes):
            result[key] = "[bytes omitted]"
        else:
            result[key] = value
    return result


def _extract_highlights(items: list) -> list[dict]:
    if len(items) != 1 or not isinstance(items[0], dict):
        return [item for item in items if isinstance(item, dict)]

    item = items[0]
    for key in ("data", "items", "results", "highlights"):
        value = item.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]

    if item.get("id") is not None or item.get("title"):
        return [item]
    return []


def _deduplicate(items: list[dict]) -> tuple[list[dict], int]:
    seen_ids = set()
    unique = []
    duplicates = 0

    for item in items:
        highlight_id = item.get("id")
        identity = str(highlight_id) if highlight_id is not None else ""
        if identity and identity in seen_ids:
            duplicates += 1
            continue
        if identity:
            seen_ids.add(identity)
        unique.append(item)

    return unique, duplicates


def _normalize_highlight(item: dict, position: int) -> dict:
    source = "singhera07.highlights"
    highlight_id = item.get("id")
    title = item.get("title")
    cover = item.get("croppedThumbnail") or item.get("cover")
    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    owner_id = owner.get("id")
    owner_username = owner.get("username")

    return {
        "position": position,
        "highlight_id": (
            _field_ok(str(highlight_id), f"{source}.id")
            if highlight_id is not None
            else _field_missing(f"{source}.id", "id field absent in actor output")
        ),
        "title": (
            _field_ok(title, f"{source}.title")
            if title
            else _field_missing(f"{source}.title", "title field absent")
        ),
        "cover_image_url": (
            _field_ok(cover[:2048] if isinstance(cover, str) else cover,
                      f"{source}.croppedThumbnail")
            if cover
            else _field_missing(
                f"{source}.croppedThumbnail",
                "croppedThumbnail absent — non-blocking",
            )
        ),
        "owner_id": (
            _field_ok(str(owner_id), f"{source}.owner.id")
            if owner_id is not None
            else _field_missing(f"{source}.owner.id", "owner.id absent — non-blocking")
        ),
        "owner_username": (
            _field_ok(owner_username, f"{source}.owner.username")
            if owner_username
            else _field_missing(
                f"{source}.owner.username",
                "owner.username absent — non-blocking",
            )
        ),
        "stories_collection_ready": _field_ok(
            highlight_id is not None,
            f"{source}.id",
            "Stage 5B-2 requires a highlight ID",
        ),
    }


def collect(
    username: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Собирает и нормализует индекс хайлайтов профиля."""
    account = get_account(username)
    selected_limit = limit if limit is not None else account["highlights_limit"]
    if selected_limit <= 0:
        raise ValueError("limit должен быть положительным числом")

    payload = {
        "action": "highlights",
        "limit": selected_limit,
        "username": username,
    }
    logger.info(
        "[5B-1] collect_highlights | @%s | limit=%d | dry_run=%s",
        username,
        selected_limit,
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {
            "dry_run": True,
            "account": username,
            "actor": ACTOR_ID,
            "payload": payload,
            "planned_apify_calls": 1,
            "actual_apify_calls": 0,
        }

    dataset_items = run_actor(actor_id=ACTOR_ID, input_data=payload)
    highlights_raw = _extract_highlights(dataset_items)
    unique_items, duplicates_count = _deduplicate(highlights_raw)

    raw_path = raw(username, "stage5b1_highlights_index_raw.json")
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps([_safe_item(item) for item in highlights_raw],
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    highlights = [
        _normalize_highlight(item, position)
        for position, item in enumerate(unique_items, start=1)
    ]
    output = {
        "account": username,
        "stage": "stage5b1",
        "actor": ACTOR_ID,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "planned_apify_calls": 1,
        "actual_apify_calls": 1,
        "apify_run_ids": [],
        "source_payload": payload,
        "highlights_count": len(highlights_raw),
        "unique_highlights_count": len(highlights),
        "duplicates_count": duplicates_count,
        "highlights": highlights,
        "raw_source": str(raw_path.relative_to(raw_path.parents[3])),
    }

    output_path = normalized(username, "highlights_index.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("Raw: %s (%d highlights)", raw_path, len(highlights_raw))
    logger.info("Index: %s", output_path)
    print(f"\n=== Stage 5B-1: Highlights | @{username} ===")
    print(f"Собрано: {len(highlights_raw)} | уникальных: {len(highlights)}")
    print(f"Дубликатов удалено: {duplicates_count}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5B-1: collect highlights index")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--limit", type=int, default=None, help="Лимит хайлайтов")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать Apify")
    args = parser.parse_args()
    collect(args.account, args.limit, args.dry_run)
