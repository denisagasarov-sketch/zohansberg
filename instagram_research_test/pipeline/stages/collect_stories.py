"""Stage 5B-2: сборщик сторис внутри Instagram Highlights.

Стейдж читает highlights_index.json, делает один batch-вызов Apify,
раскладывает ответ по highlight ID и сохраняет индекс собранных сторис.

Использование:
  python3 -m pipeline.stages.collect_stories --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.collect_stories --account vlada_kliuiko --limit 3
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone

from pipeline.core.apify_client import run_actor
from pipeline.core.config import get_account, load_env
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ACTOR_ID = "automation-lab/instagram-stories-scraper"


def _unwrap(field):
    if isinstance(field, dict):
        return field.get("value")
    return field


def _normalize_highlight_id(value) -> str | None:
    if value is None:
        return None
    highlight_id = str(value).strip()
    if highlight_id.lower().startswith("highlight:"):
        highlight_id = highlight_id[len("highlight:"):]
    return highlight_id if highlight_id.isdigit() else None


def _load_highlights(username: str) -> list[dict]:
    input_path = normalized(username, "highlights_index.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Не найден {input_path}. Сначала запустите collect_highlights."
        )

    data = json.loads(input_path.read_text(encoding="utf-8"))
    highlights = []
    for item in data.get("highlights", []):
        raw_id = _unwrap(item.get("highlight_id"))
        highlight_id = _normalize_highlight_id(raw_id)
        highlights.append({
            "position": item.get("position", len(highlights) + 1),
            "highlight_id": highlight_id,
            "raw_id": str(raw_id) if raw_id is not None else None,
            "title": _unwrap(item.get("title")) or "—",
            "id_valid": highlight_id is not None,
        })
    return highlights


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


def _item_highlight_id(item: dict) -> str | None:
    return _normalize_highlight_id(item.get("highlightId"))


def _has_image(items: list[dict]) -> bool:
    return any(
        item.get("imageUrl")
        or item.get("thumbnailUrl")
        or (item.get("mediaUrl") and str(item.get("mediaType", "")).lower() == "image")
        for item in items
    )


def _has_video(items: list[dict]) -> bool:
    return any(
        item.get("videoUrl")
        or (item.get("mediaUrl") and str(item.get("mediaType", "")).lower() == "video")
        for item in items
    )


def collect(
    username: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    """Собирает сторис выбранных хайлайтов и возвращает их индекс."""
    account = get_account(username)
    selected_limit = limit if limit is not None else account["highlights_limit"]
    if selected_limit <= 0:
        raise ValueError("limit должен быть положительным числом")

    highlights = _load_highlights(username)
    valid_highlights = [item for item in highlights if item["id_valid"]]
    selected = valid_highlights[:selected_limit]
    payload_preview = {
        "usernames": [username],
        "maxHighlights": len(selected),
        "includeHighlights": True,
        "sessionCookie": "<configured at runtime>",
    }

    logger.info(
        "[5B-2] collect_stories | @%s | selected=%d/%d | dry_run=%s",
        username,
        len(selected),
        len(highlights),
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Apify не вызывается")
        return {
            "dry_run": True,
            "account": username,
            "actor": ACTOR_ID,
            "highlights_total": len(highlights),
            "highlights_valid": len(valid_highlights),
            "highlights_selected": len(selected),
            "payload": payload_preview,
            "planned_apify_calls": 1 if selected else 0,
            "actual_apify_calls": 0,
        }

    if not selected:
        raise ValueError("В highlights_index.json нет валидных highlight ID")

    load_env()
    session_cookie = os.getenv("INSTAGRAM_SESSION_COOKIE", "").strip()
    if not session_cookie:
        raise EnvironmentError("INSTAGRAM_SESSION_COOKIE не найден в .env")

    payload = {
        "usernames": [username],
        "maxHighlights": len(selected),
        "sessionCookie": session_cookie,
        "includeHighlights": True,
    }
    dataset_items = run_actor(actor_id=ACTOR_ID, input_data=payload)

    items_by_highlight: dict[str, list[dict]] = {}
    for item in dataset_items:
        if not isinstance(item, dict):
            continue
        highlight_id = _item_highlight_id(item)
        if highlight_id:
            items_by_highlight.setdefault(highlight_id, []).append(item)

    results = []
    for highlight in selected:
        highlight_id = highlight["highlight_id"]
        stories = items_by_highlight.get(highlight_id, [])
        raw_path = raw(username, f"stage5b2_stories_{highlight_id}_raw.json")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps([_safe_item(item) for item in stories],
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        results.append({
            "position": highlight["position"],
            "highlight_id": highlight_id,
            "title": highlight["title"],
            "status": "OK" if stories else "EMPTY_OR_INACCESSIBLE",
            "stories_count": len(stories),
            "has_imageUrl": _has_image(stories),
            "has_videoUrl": _has_video(stories),
            "raw_path": str(raw_path.relative_to(raw_path.parents[3])),
        })

    output = {
        "stage": "stage5b2",
        "account": username,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "highlights": results,
    }
    output_path = normalized(username, "stage5b2_stories_index.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ok_count = sum(1 for item in results if item["status"] == "OK")
    total_stories = sum(item["stories_count"] for item in results)
    logger.info("Stories index: %s", output_path)
    print(f"\n=== Stage 5B-2: Highlight Stories | @{username} ===")
    print(f"Обработано хайлайтов: {len(results)} | с данными: {ok_count}")
    print(f"Собрано сторис: {total_stories}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5B-2: collect highlight stories")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--limit", type=int, default=None, help="Лимит хайлайтов")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать Apify")
    args = parser.parse_args()
    collect(args.account, args.limit, args.dry_run)
