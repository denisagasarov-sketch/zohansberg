"""Stage 5A-2B: технические детали закреплённых постов.

Стейдж читает raw Stage 5A-1, сопоставляет записи с pinned_posts_index.json
и сохраняет нормализованные подписи и медиа без внешних API-вызовов.

Использование:
  python3 -m pipeline.stages.collect_pinned_details --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.collect_pinned_details --account vlada_kliuiko
"""

import argparse
import json
import logging
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DISPLAY_FIELDS = ("displayUrl", "displaySrc", "display_url")
THUMBNAIL_FIELDS = ("thumbnailSrc", "thumbnailUrl", "thumbnail_src", "thumbnail_url")
VIDEO_FIELDS = ("videoUrl", "video_url", "videoSrc")
CAROUSEL_FIELDS = (
    "carouselMedia", "sidecar", "sidecars", "carousel_media",
    "edge_sidecar_to_children", "childPosts",
)
CONFIRMED_FIELDS = ("url", "id", "shortCode", "caption", "type", "timestamp", "isPinned")


def _unwrap(field):
    if isinstance(field, dict):
        return field.get("value")
    return field


def _first(item: dict, fields: tuple[str, ...]):
    for field in fields:
        value = item.get(field)
        if value not in (None, "", []):
            return value
    return None


def _load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_refs(username: str) -> list[dict]:
    index = _load_json(normalized(username, "pinned_posts_index.json"))
    refs = []
    for position, item in enumerate(index.get("pinned_posts", []), start=1):
        refs.append({
            "position": item.get("position", position),
            "permalink": _unwrap(item.get("url")),
            "shortcode": _unwrap(item.get("shortcode")),
            "post_id": _unwrap(item.get("content_id")),
            "media_type": _unwrap(item.get("type")),
        })
    if not refs:
        raise ValueError("В pinned_posts_index.json нет закреплённых постов")
    return refs


def _load_raw_posts(username: str) -> list[dict]:
    data = _load_json(raw(username, "stage5a1_posts_for_pinned_raw.json"))
    if not isinstance(data, list):
        raise ValueError("stage5a1_posts_for_pinned_raw.json должен содержать массив")
    return [item for item in data if isinstance(item, dict)]


def _match(ref: dict, posts: list[dict]) -> dict | None:
    for item in posts:
        if ref["shortcode"] and item.get("shortCode") == ref["shortcode"]:
            return item
        if ref["post_id"] and str(item.get("id") or "") == str(ref["post_id"]):
            return item
        if ref["permalink"] and item.get("url") == ref["permalink"]:
            return item
    return None


def _carousel_items(item: dict) -> list[dict]:
    raw_items = _first(item, CAROUSEL_FIELDS)
    if not isinstance(raw_items, list):
        return []
    result = []
    for position, slide in enumerate(raw_items, start=1):
        if not isinstance(slide, dict):
            continue
        result.append({
            "position": position,
            "media_type": slide.get("type") or slide.get("mediaType"),
            "display_url": _first(slide, DISPLAY_FIELDS),
            "thumbnail_url": _first(slide, THUMBNAIL_FIELDS),
            "video_url": _first(slide, VIDEO_FIELDS),
        })
    return result


def _empty_post(ref: dict) -> dict:
    return {
        **ref,
        "timestamp": None,
        "full_caption": None,
        "caption_for_analysis": None,
        "caption_length": 0,
        "caption_is_full": "missing",
        "caption_source_field": None,
        "display_url": None,
        "thumbnail_url": None,
        "video_url": None,
        "cover_url": None,
        "carousel_items": [],
        "carousel_items_count": 0,
        "media_for_visual_analysis": {
            "primary_image_url": None,
            "candidate_urls": [],
            "source_fields": [],
        },
        "has_full_caption": False,
        "has_cover_or_thumbnail": False,
        "has_carousel_items": False,
        "has_media_urls": False,
        "analysis_readiness": {
            "caption_semantic_possible": False,
            "visual_ocr_input_possible": False,
        },
        "source_quality": "missing",
        "missing_fields": ["actor_item"],
        "limitations": ["закреплённый пост не найден в raw Stage 5A-1"],
    }


def _normalize_post(ref: dict, item: dict | None) -> dict:
    if item is None:
        return _empty_post(ref)

    caption = str(item.get("caption") or "")
    display_url = _first(item, DISPLAY_FIELDS)
    thumbnail_url = _first(item, THUMBNAIL_FIELDS)
    video_url = _first(item, VIDEO_FIELDS)
    carousel = _carousel_items(item)
    candidate_urls = [url for url in (display_url, thumbnail_url, video_url) if url]
    for slide in carousel:
        candidate_urls.extend(
            url for url in (slide["display_url"], slide["thumbnail_url"], slide["video_url"])
            if url
        )

    has_caption = bool(caption)
    has_cover = bool(display_url or thumbnail_url)
    has_carousel = bool(carousel)
    has_media = bool(candidate_urls)
    limitations = []
    if not has_caption:
        limitations.append("caption отсутствует")
    if not has_cover:
        limitations.append("cover/thumbnail отсутствует")

    return {
        "position": ref["position"],
        "permalink": item.get("url") or ref["permalink"],
        "shortcode": item.get("shortCode") or ref["shortcode"],
        "post_id": item.get("id") or ref["post_id"],
        "timestamp": item.get("timestamp"),
        "media_type": item.get("type") or ref["media_type"],
        "full_caption": caption or None,
        "caption_for_analysis": caption[:5000] or None,
        "caption_length": len(caption),
        "caption_is_full": True if len(caption) > 300 else "unknown",
        "caption_source_field": "caption" if caption else None,
        "display_url": display_url,
        "thumbnail_url": thumbnail_url,
        "video_url": video_url,
        "cover_url": display_url or thumbnail_url,
        "carousel_items": carousel,
        "carousel_items_count": len(carousel),
        "media_for_visual_analysis": {
            "primary_image_url": display_url or thumbnail_url or (
                carousel[0]["display_url"] if carousel else None
            ),
            "candidate_urls": candidate_urls,
            "source_fields": [
                field for field in (*DISPLAY_FIELDS, *THUMBNAIL_FIELDS, *VIDEO_FIELDS)
                if item.get(field)
            ],
        },
        "has_full_caption": len(caption) > 300,
        "has_cover_or_thumbnail": has_cover,
        "has_carousel_items": has_carousel,
        "has_media_urls": has_media,
        "analysis_readiness": {
            "caption_semantic_possible": has_caption,
            "visual_ocr_input_possible": has_cover or has_carousel,
        },
        "source_quality": "full" if has_caption and has_media else "partial",
        "missing_fields": [
            field for field, present in (
                ("full_caption", has_caption),
                ("display_url / thumbnail_url", has_cover),
            ) if not present
        ],
        "limitations": limitations,
    }


def _schema_summary(items: list[dict]) -> dict:
    fields = sorted({key for item in items for key in item})
    return {
        "items_count": len(items),
        "all_fields": fields,
        "confirmed_fields_present": [field for field in CONFIRMED_FIELDS if field in fields],
        "confirmed_fields_missing": [field for field in CONFIRMED_FIELDS if field not in fields],
        "display_url_fields_found": [field for field in DISPLAY_FIELDS if field in fields],
        "thumbnail_fields_found": [field for field in THUMBNAIL_FIELDS if field in fields],
        "video_url_fields_found": [field for field in VIDEO_FIELDS if field in fields],
        "carousel_fields_found": [field for field in CAROUSEL_FIELDS if field in fields],
        "schema_confidence": "high" if items and "caption" in fields else "low",
    }


def collect(username: str, dry_run: bool = False) -> dict:
    """Нормализует детали закреплённых постов из raw Stage 5A-1."""
    get_account(username)
    refs = _load_refs(username)
    raw_posts = _load_raw_posts(username)
    matched = [(ref, _match(ref, raw_posts)) for ref in refs]
    matched_count = sum(1 for _, item in matched if item is not None)

    logger.info(
        "[5A-2B] collect_pinned_details | @%s | matched=%d/%d | dry_run=%s",
        username,
        matched_count,
        len(refs),
        dry_run,
    )
    if dry_run:
        logger.info("[DRY RUN] Файлы не записываются, внешние API не вызываются")
        return {
            "dry_run": True,
            "account": username,
            "pinned_total": len(refs),
            "matched_total": matched_count,
            "raw_posts_total": len(raw_posts),
            "planned_apify_calls": 0,
            "actual_apify_calls": 0,
        }

    posts = [_normalize_post(ref, item) for ref, item in matched]
    warnings = [
        f"Закреп {ref['position']} не найден в raw"
        for ref, item in matched if item is None
    ]
    output = {
        "account": username,
        "stage": "stage5a2b",
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "stage5a1_existing_raw",
        "actor": "apify/instagram-scraper",
        "run_id": None,
        "dataset_id": None,
        "strategy": "from_existing_stage5a1_raw",
        "total_pinned_posts": len(posts),
        "warnings": warnings,
        "posts": posts,
        "summary": {
            "posts_with_full_caption": sum(1 for post in posts if post["has_full_caption"]),
            "posts_with_cover_or_thumbnail": sum(
                1 for post in posts if post["has_cover_or_thumbnail"]
            ),
            "posts_with_carousel_items": sum(1 for post in posts if post["has_carousel_items"]),
            "caption_semantic_possible": sum(
                1 for post in posts if post["analysis_readiness"]["caption_semantic_possible"]
            ),
            "visual_ocr_input_possible": sum(
                1 for post in posts if post["analysis_readiness"]["visual_ocr_input_possible"]
            ),
            "next_stage_recommendation": "Можно запускать анализ текста закрепов.",
        },
    }

    output_path = normalized(username, "stage5a2b_pinned_posts_details.json")
    schema_path = normalized(username, "stage5a2b_pinned_posts_schema_summary.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    schema_path.write_text(
        json.dumps(_schema_summary([item for _, item in matched if item]),
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n=== Stage 5A-2B: Pinned Details | @{username} ===")
    print(f"Закрепов: {len(refs)} | найдено в raw: {matched_count}")
    print(f"Сохранено: {output_path}")
    print(f"Схема: {schema_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2B: collect pinned details")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не записывать файлы")
    args = parser.parse_args()
    collect(args.account, args.dry_run)
