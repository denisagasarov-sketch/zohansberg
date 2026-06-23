"""Stage 5B-2V: визуальный анализ Instagram Highlights.

Стейдж выбирает до пяти кадров каждого хайлайта, анализирует их совместно
через OpenAI Vision и сохраняет stage5b2v_highlights_visual.json.

Использование:
  python3 -m pipeline.stages.analyze_highlights --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_highlights --account vlada_kliuiko
"""

import argparse
import base64
import io
import json
import logging
from datetime import datetime, timezone

import requests
from PIL import Image

from pipeline.core.config import get_account
from pipeline.core.openai_client import vision
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
PROMPT_VERSION = "v2"
MAX_IMAGES = 5
IMAGE_MAX_SIDE = 512
FIELD_NAMES = ("tema", "zadacha", "chto_vnutri", "mekhanika", "cta")

PROMPT = """Ты анализируешь несколько кадров одного Instagram highlight.
Первый кадр показывает начало, последние кадры — завершение и возможный CTA.
Используй только видимые данные и отвечай по-русски. Верни только JSON:
{
  "tema": {"value": "тема", "data_status": "ok|not_found", "notes": "..."},
  "zadacha": {"value": "доверие|прогрев|лидогенерация|социальное доказательство|обучение", "data_status": "ok|not_found", "notes": "..."},
  "chto_vnutri": {"value": "одно предложение о содержании", "data_status": "ok|not_found", "notes": "..."},
  "mekhanika": {"value": "скрин|видео|репост сторис|сторис ученика|кейс|результат|переписка|продажа через отзыв или точное своё описание", "data_status": "ok|not_found", "notes": "..."},
  "cta": {"value": "директ|бот|сайт|курс|лид-магнит или пустая строка", "data_status": "ok|not_found", "notes": "..."},
  "cover_hook": "что цепляет взгляд на первом кадре",
  "cta_text": "дословный CTA с финального кадра или пустая строка"
}
CTA существует только при явном призыве к действию с глаголом. Не додумывай
пропущенные кадры."""


def _unwrap(field):
    if isinstance(field, dict):
        return field.get("value")
    return field


def _load_highlights(username: str) -> list[dict]:
    index_path = normalized(username, "highlights_index.json")
    if not index_path.exists():
        raise FileNotFoundError(
            f"Не найден {index_path}. Сначала запустите collect_highlights."
        )
    data = json.loads(index_path.read_text(encoding="utf-8"))
    result = []
    for position, item in enumerate(data.get("highlights", []), start=1):
        highlight_id = _unwrap(item.get("highlight_id"))
        if highlight_id is None:
            continue
        result.append({
            "highlight_id": str(highlight_id),
            "title": str(_unwrap(item.get("title")) or ""),
            "position": item.get("position", position),
        })
    if not result:
        raise ValueError("В highlights_index.json нет валидных хайлайтов")
    return result


def _load_stories(username: str, highlight_id: str) -> list[dict]:
    stories_path = raw(username, f"stage5b2_stories_{highlight_id}_raw.json")
    if not stories_path.exists():
        return []
    data = json.loads(stories_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("stories", "items", "data"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
    return []


def _story_url(story: dict) -> str:
    return str(
        story.get("imageUrl")
        or story.get("thumbnailUrl")
        or story.get("mediaUrl")
        or ""
    )


def _select_urls(stories: list[dict]) -> list[str]:
    urls = [_story_url(story) for story in stories]
    urls = [url for url in urls if url]
    if len(urls) <= MAX_IMAGES:
        return urls

    indexes = [0, len(urls) // 3, (len(urls) * 2) // 3, len(urls) - 2, len(urls) - 1]
    selected = []
    for index in indexes:
        url = urls[index]
        if url not in selected:
            selected.append(url)
    return selected[:MAX_IMAGES]


def _download_image(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 AppleWebKit/537.36"},
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"URL вернул Content-Type={content_type}")

    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    if max(image.size) > IMAGE_MAX_SIDE:
        scale = IMAGE_MAX_SIDE / max(image.size)
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_response(response: str) -> dict:
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = "\n".join(
            line for line in stripped.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Ответ Vision должен быть JSON-объектом")
    return parsed


def _normalize_fields(parsed: dict) -> dict:
    fields = {}
    for name in FIELD_NAMES:
        entry = parsed.get(name) if isinstance(parsed.get(name), dict) else {}
        status = entry.get("data_status")
        fields[name] = {
            "value": str(entry.get("value") or "")[:500],
            "data_status": status if status in {"ok", "not_found"} else "not_found",
            "notes": str(entry.get("notes") or "")[:300],
        }
    return fields


def _skipped(meta: dict, stories: list, urls: list[str], reason: str) -> dict:
    return {
        **meta,
        "stories_total": len(stories),
        "stories_selected": len(urls),
        "imageUrls_used": urls,
        "skipped": True,
        "skip_reason": reason,
    }


def _analyze_one(meta: dict, stories: list[dict]) -> dict:
    urls = _select_urls(stories)
    if not urls:
        return _skipped(meta, stories, urls, "no_image_urls")

    images = []
    successful_urls = []
    download_errors = []
    for url in urls:
        try:
            images.append({"b64": _download_image(url), "detail": "low"})
            successful_urls.append(url)
        except Exception as error:
            download_errors.append(str(error))

    if not images:
        return _skipped(meta, stories, urls, "all_image_downloads_failed")

    prompt = (
        f"Highlight: {meta['title']}\n"
        f"Кадров показано: {len(images)} из {len(stories)}.\n\n{PROMPT}"
    )
    parsed = _parse_response(vision(images, prompt, model=MODEL, max_tokens=1100))
    fields = _normalize_fields(parsed)
    cta_text = str(parsed.get("cta_text") or "")[:100]
    return {
        **meta,
        "stories_total": len(stories),
        "stories_selected": len(successful_urls),
        "imageUrls_used": successful_urls,
        "skipped": False,
        "fields": fields,
        "tokens_used": None,
        "cover_hook": {
            "status": "ok" if parsed.get("cover_hook") else "not_found",
            "text": str(parsed.get("cover_hook") or "")[:300],
        },
        "cta_targeted": {
            "status": "ok" if cta_text else "not_found",
            "text": cta_text,
            "frames_used": min(2, len(successful_urls)),
        },
        "download_warnings": download_errors,
    }


def analyze(username: str, dry_run: bool = False) -> dict:
    """Анализирует визуальный контент всех доступных хайлайтов."""
    get_account(username)
    highlights = _load_highlights(username)
    prepared = [
        (meta, _load_stories(username, meta["highlight_id"]))
        for meta in highlights
    ]
    logger.info(
        "[5B-2V] analyze_highlights | @%s | highlights=%d | dry_run=%s",
        username,
        len(highlights),
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Изображения не скачиваются, OpenAI не вызывается")
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "highlights_total": len(highlights),
            "highlights_with_stories": sum(1 for _, stories in prepared if stories),
            "planned_vision_calls": sum(1 for _, stories in prepared if _select_urls(stories)),
            "actual_vision_calls": 0,
            "selection_preview": [
                {
                    **meta,
                    "stories_total": len(stories),
                    "images_selected": len(_select_urls(stories)),
                }
                for meta, stories in prepared
            ],
        }

    results = []
    for meta, stories in prepared:
        try:
            results.append(_analyze_one(meta, stories))
        except Exception as error:
            logger.error("Highlight %s failed: %s", meta["highlight_id"], error)
            results.append(_skipped(meta, stories, _select_urls(stories), str(error)))

    output = {
        "account": username,
        "stage": "stage5b2v",
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analyzed_highlights": results,
    }
    output_path = normalized(username, "stage5b2v_highlights_visual.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    analyzed_count = sum(1 for result in results if not result["skipped"])
    print(f"\n=== Stage 5B-2V: Highlights Visual | @{username} ===")
    print(f"Проанализировано: {analyzed_count}/{len(results)}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5B-2V: analyze highlights")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не скачивать изображения")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
