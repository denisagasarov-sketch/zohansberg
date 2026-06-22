"""Stage 5A-2D: визуальный анализ хуков закреплённых постов.

Стейдж загружает обложку или выбранные слайды карусели, отправляет их в
OpenAI Vision и сохраняет stage5a2d_pinned_hooks.json.

Использование:
  python3 -m pipeline.stages.analyze_pinned_visuals --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_pinned_visuals --account vlada_kliuiko
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
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
PROMPT_VERSION = "v2"
MAX_LONG_SIDE = 512
JPEG_QUALITY = 85
MAX_CAROUSEL_IMAGES = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36"
    )
}

SINGLE_PROMPT = """Ты анализируешь первый экран закреплённого Instagram-поста.
Верни только JSON:
{
  "hook": {
    "value": "дословный текст с обложки → маркетинговая интерпретация",
    "data_status": "ok|not_found",
    "notes": "что именно видно"
  }
}
Если текста нет, кратко опиши визуал и после стрелки напиши «нет явного хука».
Не додумывай содержание за пределами изображения."""

CAROUSEL_PROMPT = """Ты анализируешь несколько слайдов закреплённой Instagram-карусели.
Первое изображение — обложка, последнее — финальный показанный слайд.
Верни только JSON:
{
  "hook": {
    "value": "элемент первого слайда → маркетинговая интерпретация",
    "data_status": "ok|not_found",
    "notes": "что видно на первом слайде"
  },
  "carousel_narrative": "логика карусели одним предложением",
  "carousel_cta": "дословный CTA с глаголом или пустая строка"
}
Не додумывай невидимое содержание. CTA существует только при явном призыве к действию."""


def _load_posts(username: str) -> list[dict]:
    input_path = normalized(username, "stage5a2b_pinned_posts_details.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Не найден {input_path}. Сначала запустите collect_pinned_details."
        )
    data = json.loads(input_path.read_text(encoding="utf-8"))
    posts = data.get("posts") or []
    if not posts:
        raise ValueError("В stage5a2b_pinned_posts_details.json нет постов")
    return posts


def _carousel_urls(post: dict) -> tuple[list[str], int]:
    urls = [
        item.get("display_url") or item.get("thumbnail_url")
        for item in post.get("carousel_items") or []
    ]
    urls = [url for url in urls if url]
    total = len(urls)
    if total <= MAX_CAROUSEL_IMAGES:
        return urls, total

    middle = urls[1:-2]
    selected = [urls[0]]
    if middle:
        selected.append(middle[0])
    if len(middle) > 1:
        selected.append(middle[len(middle) // 2])
    selected.extend(urls[-2:])
    return selected[:MAX_CAROUSEL_IMAGES], total


def _image_plan(post: dict) -> dict:
    media_type = str(post.get("media_type") or "")
    carousel_urls, carousel_total = _carousel_urls(post)
    if media_type.lower() in {"sidecar", "graphsidecar", "carousel"} and carousel_urls:
        return {
            "image_source": "carousel",
            "urls": carousel_urls,
            "carousel_total": carousel_total,
        }

    url = (
        post.get("display_url")
        or post.get("thumbnail_url")
        or post.get("cover_url")
        or post.get("media_for_visual_analysis", {}).get("primary_image_url")
    )
    return {
        "image_source": "displayUrl",
        "urls": [url] if url else [],
        "carousel_total": 0,
    }


def _download_image(url: str) -> str:
    response = requests.get(url, timeout=20, headers=HEADERS)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "")
    if content_type and not content_type.startswith("image/"):
        raise ValueError(f"URL вернул Content-Type={content_type}")

    image = Image.open(io.BytesIO(response.content)).convert("RGB")
    if max(image.size) > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / max(image.size)
        image = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            Image.Resampling.LANCZOS,
        )
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
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


def _skipped(post: dict, plan: dict, reason: str) -> dict:
    return {
        "position": post.get("position"),
        "post_type": post.get("media_type") or "",
        "carousel_narrative": "",
        "carousel_cta": "",
        "image_source": plan["image_source"],
        "displayUrl_used": plan["urls"][0] if plan["urls"] else "",
        "skipped": True,
        "skip_reason": reason,
    }


def _analyze_post(post: dict) -> dict:
    plan = _image_plan(post)
    if not plan["urls"]:
        return _skipped(post, plan, "no_image_url")

    images = []
    errors = []
    for url in plan["urls"]:
        try:
            images.append({"b64": _download_image(url), "detail": "low"})
        except Exception as error:
            errors.append(str(error))

    if not images:
        return _skipped(post, plan, "all_image_downloads_failed: " + "; ".join(errors))

    is_carousel = plan["image_source"] == "carousel"
    prompt = CAROUSEL_PROMPT if is_carousel else SINGLE_PROMPT
    prompt += (
        f"\nЗакреп №{post.get('position')}, тип {post.get('media_type')}."
        f" Показано изображений: {len(images)} из {plan['carousel_total']}."
    )
    parsed = _parse_response(vision(images, prompt, model=MODEL, max_tokens=700))
    hook = parsed.get("hook") if isinstance(parsed.get("hook"), dict) else {}
    return {
        "position": post.get("position"),
        "post_type": post.get("media_type") or "",
        "carousel_narrative": str(parsed.get("carousel_narrative") or "")[:400],
        "carousel_cta": str(parsed.get("carousel_cta") or "")[:150],
        "image_source": plan["image_source"],
        "displayUrl_used": plan["urls"][0],
        "skipped": False,
        "hook": {
            "value": str(hook.get("value") or "")[:300],
            "data_status": hook.get("data_status")
            if hook.get("data_status") in {"ok", "not_found"} else "not_found",
            "notes": str(hook.get("notes") or "")[:300],
        },
        "images_analyzed": len(images),
        "download_warnings": errors,
    }


def analyze(username: str, dry_run: bool = False) -> dict:
    """Анализирует первый экран каждого закрепа через OpenAI Vision."""
    get_account(username)
    posts = _load_posts(username)
    plans = [_image_plan(post) for post in posts]
    logger.info(
        "[5A-2D] analyze_pinned_visuals | @%s | posts=%d | dry_run=%s",
        username,
        len(posts),
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Изображения не скачиваются, OpenAI не вызывается")
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "posts_total": len(posts),
            "planned_vision_calls": sum(1 for plan in plans if plan["urls"]),
            "actual_vision_calls": 0,
            "image_plans": plans,
        }

    results = [_analyze_post(post) for post in posts]
    output = {
        "account": username,
        "stage": "stage5a2d",
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "posts": results,
    }
    output_path = normalized(username, "stage5a2d_pinned_hooks.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    analyzed_count = sum(1 for result in results if not result["skipped"])
    print(f"\n=== Stage 5A-2D: Pinned Visual Hooks | @{username} ===")
    print(f"Обработано: {analyzed_count}/{len(results)}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2D: analyze pinned visuals")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не скачивать изображения")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
