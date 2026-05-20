"""Stage 5E-1: Posts Analyzer — полный анализ (download + GPT + сохранение).

Reads data/{account}/raw/posts_test_raw.json and profile_summary.json.
Computes ERR per post, downloads media, sends to GPT-4o, builds sheet rows.
Output: data/{account}/normalized/stage5e1_posts_analysis.json

Usage:
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --metrics-only
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --limit 5 --download-only
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --limit 5 --dry-run
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --limit 5
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --limit 15 --post-types photo,carousel
    python scripts/stage5e1_posts_analyzer.py --account vlada_kliuiko --limit 5 --refresh-days 0
"""

import argparse
import base64
import json
import logging
import os
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE = Path(__file__).parent.parent

INPUT_FILENAME = "posts_test_raw.json"
STAGE          = "stage5e1"
GPT_MODEL      = "gpt-4o"

KATE_ACCOUNT  = "kate.jet"
KATE_NORM_DIR = BASE / "data" / KATE_ACCOUNT / "normalized"
KATE_RAW_DIR  = BASE / "data" / KATE_ACCOUNT / "raw"

MAX_SLIDES        = 10
MAX_CONTENT_BYTES = 200 * 1024 * 1024  # 200 MB

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
}


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _unwrap(obj: dict, *keys):
    """Extract plain value from a possibly dict-wrapped profile field."""
    for k in keys:
        v = obj.get(k)
        if v is not None:
            return v.get("value") if isinstance(v, dict) else v
    return None


def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video", "Image": "photo"}.get(raw_type, "photo")


def _post_type_ru(raw_type: str) -> str:
    return {"Sidecar": "карусель", "Video": "видео", "Image": "фото"}.get(raw_type, "фото")


# ---------------------------------------------------------------------------
# Accounts config
# ---------------------------------------------------------------------------

def _load_accounts_config() -> dict:
    path = BASE / "data" / "accounts.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_posts(username: str, limit: int) -> list:
    path = BASE / "data" / username / "raw" / INPUT_FILENAME
    if not path.exists():
        sys.exit(f"[ERROR] Файл не найден: {path.relative_to(BASE)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data[:limit] if limit else data


def load_posts_unified(username: str) -> tuple[list, str, dict]:
    """Load posts, preferring stage5e0_posts_index.json, fallback to posts_test_raw.json.

    Returns (posts, source_label, url_to_raw):
        posts        — raw-Apify-compatible dicts for compute_metrics() / download_media()
        source_label — human-readable source description for dry-run output
        url_to_raw   — dict[url → full raw item]
    """
    index_path    = BASE / "data" / username / "normalized" / "stage5e0_posts_index.json"
    raw_e0_path   = BASE / "data" / username / "raw"        / "stage5e0_posts_raw.json"
    fallback_path = BASE / "data" / username / "raw"        / INPUT_FILENAME

    if index_path.exists():
        index       = json.loads(index_path.read_text(encoding="utf-8"))
        posts_index = index.get("posts") or []

        # Build url → full raw item for captions and media download
        url_to_raw: dict[str, dict] = {}
        if raw_e0_path.exists():
            try:
                raw_items = json.loads(raw_e0_path.read_text(encoding="utf-8"))
                for item in raw_items:
                    url = item.get("url") or ""
                    if not url.startswith("http"):
                        short = item.get("shortCode") or item.get("id") or ""
                        url = f"https://www.instagram.com/p/{short}/" if short else ""
                    if url:
                        url_to_raw[url] = item
            except Exception:
                pass

        by_type = index.get("by_type") or {}
        total   = index.get("total", len(posts_index))
        parts   = [f"{v} {k}" for k, v in by_type.items() if v]
        source_label = f"stage5e0_posts_index.json ({total} постов: {', '.join(parts)})"

        _reverse_type = {"carousel": "Sidecar", "video": "Video", "photo": "Image"}
        posts_out = []
        for p in posts_index:
            url     = p.get("url") or ""
            raw     = url_to_raw.get(url, {})
            unified = dict(raw)  # start with full raw (displayUrl, childPosts, videoUrl, etc.)
            if not unified.get("type"):
                unified["type"] = _reverse_type.get(p.get("post_type", "photo"), "Image")
            unified["likesCount"]     = p.get("likes", 0)
            unified["commentsCount"]  = p.get("comments", 0)
            unified["videoPlayCount"] = p.get("views", 0)
            unified["url"]            = url
            unified["shortCode"]      = p.get("short_code") or unified.get("shortCode") or ""
            unified["caption"]        = raw.get("caption") or p.get("caption_preview") or ""
            unified["timestamp"]      = p.get("timestamp") or unified.get("timestamp") or ""
            posts_out.append(unified)

        return posts_out, source_label, url_to_raw

    # Fallback: old behavior
    if not fallback_path.exists():
        sys.exit(f"[ERROR] Файл не найден: {fallback_path.relative_to(BASE)}")
    data         = json.loads(fallback_path.read_text(encoding="utf-8"))
    source_label = f"{INPUT_FILENAME} (fallback)"
    url_to_raw   = {(item.get("url") or ""): item for item in data if item.get("url")}
    return data, source_label, url_to_raw


def compute_metrics(posts: list, followers: int) -> list[dict]:
    results = []
    for post in posts:
        raw_type = post.get("type") or "Image"
        likes    = max(0, int(post.get("likesCount")    or 0))
        comments = int(post.get("commentsCount") or 0)
        reposts  = int(post.get("sharesCount")   or 0)
        views    = int(post.get("videoPlayCount") or post.get("videoViewCount") or 0)
        err      = round((likes + comments + reposts) / followers * 100, 2) if followers > 0 else 0.0

        results.append({
            "post_id":       post.get("id") or post.get("shortCode") or "",
            "url":           post.get("url") or "",
            "raw_type":      raw_type,
            "post_type":     _post_type(raw_type),
            "caption":       post.get("caption") or "(caption отсутствует)",
            "likes":         likes,
            "comments":      comments,
            "reposts":       reposts,
            "views":         views,
            "err":           err,
            "err_above_avg": None,  # filled below after mean is known
        })

    if results:
        avg = statistics.mean(r["err"] for r in results)
        for r in results:
            r["err_above_avg"] = "да" if r["err"] > avg else "нет"

    return results


def load_kate_context() -> dict:
    kate_profile_path = KATE_NORM_DIR / "profile_summary.json"
    kate_raw_path     = KATE_RAW_DIR  / INPUT_FILENAME

    kate_bio = ""
    if kate_profile_path.exists():
        try:
            prof     = json.loads(kate_profile_path.read_text(encoding="utf-8"))
            kate_bio = _unwrap(prof, "bio_text") or ""
        except Exception:
            pass

    kate_recent_posts = "данные недоступны"
    kate_avg_err: float | str = "н/д"

    if kate_raw_path.exists():
        try:
            kate_raw       = json.loads(kate_raw_path.read_text(encoding="utf-8"))[:10]
            kate_followers = 0
            if kate_profile_path.exists():
                prof           = json.loads(kate_profile_path.read_text(encoding="utf-8"))
                kate_followers = int(_unwrap(prof, "followers_count") or 0)

            lines: list[str]   = []
            errs:  list[float] = []
            for p in kate_raw:
                raw_type = p.get("type") or "Image"
                caption  = (p.get("caption") or "")[:80]
                lines.append(f"  {_post_type_ru(raw_type)} | {caption}")

                if kate_followers > 0:
                    likes    = int(p.get("likesCount")    or 0)
                    comments = int(p.get("commentsCount") or 0)
                    reposts  = int(p.get("sharesCount")   or 0)
                    errs.append((likes + comments + reposts) / kate_followers * 100)

            kate_recent_posts = "\n".join(lines)
            kate_avg_err      = round(statistics.mean(errs), 2) if errs else "н/д"
        except Exception as e:
            kate_recent_posts = f"ошибка чтения: {e}"

    return {
        "kate_bio":          kate_bio,
        "kate_recent_posts": kate_recent_posts,
        "kate_avg_err":      kate_avg_err,
    }


# ---------------------------------------------------------------------------
# Media download
# ---------------------------------------------------------------------------

def download_and_encode(url: str, save_path: Path) -> Optional[str]:
    """Download url to save_path and return base64-encoded content, or None on failure."""
    try:
        import requests
    except ImportError:
        logger.error("requests не установлен: pip install requests")
        return None

    try:
        resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=30, stream=True)
        resp.raise_for_status()

        content_length = int(resp.headers.get("Content-Length", 0))
        if content_length > MAX_CONTENT_BYTES:
            logger.warning("Пропущен файл >200MB: %s (%d bytes)", url[:80], content_length)
            return None

        save_path.parent.mkdir(parents=True, exist_ok=True)
        data = resp.content
        save_path.write_bytes(data)
        return base64.b64encode(data).decode("utf-8")

    except Exception as e:
        logger.error("Ошибка скачивания %s: %s", url[:80], e)
        return None


def download_media(post: dict, post_type: str, username: str) -> dict:
    """Download post media and return base64-encoded images.

    Returns:
        {
            "images_b64": [{"b64": str, "detail": "high"}, ...],
            "fallback_thumbnail": bool,
            "mechanic_note": str,
        }
    """
    post_id  = post.get("id") or post.get("shortCode") or "unknown"
    tmp_dir  = BASE / "data" / username / "tmp" / "posts" / str(post_id)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    images_b64:        list[dict] = []
    fallback_thumbnail             = False
    mechanic_note                  = ""

    # ── Photo ────────────────────────────────────────────────────────────────
    if post_type == "photo":
        url = post.get("displayUrl") or ""
        if url:
            b64 = download_and_encode(url, tmp_dir / "image.jpg")
            if b64:
                images_b64.append({"b64": b64, "detail": "high"})

    # ── Carousel ─────────────────────────────────────────────────────────────
    elif post_type == "carousel":
        # Primary: childPosts[i].displayUrl; fallback: post.images[]
        slide_urls = [
            c.get("displayUrl") for c in post.get("childPosts", [])
            if c.get("displayUrl")
        ]
        if not slide_urls:
            slide_urls = [u for u in post.get("images", []) if u]

        for i, url in enumerate(slide_urls[:MAX_SLIDES]):
            b64 = download_and_encode(url, tmp_dir / f"slide_{i:02d}.jpg")
            if b64:
                images_b64.append({"b64": b64, "detail": "high"})

        if not images_b64:
            mechanic_note = "(слайды недоступны)"

    # ── Video ─────────────────────────────────────────────────────────────────
    elif post_type == "video":
        video_url = post.get("videoUrl") or ""

        if video_url:
            video_path = tmp_dir / "video.mp4"
            b64_video  = download_and_encode(video_url, video_path)

            if b64_video and video_path.exists():
                try:
                    ffprobe_result = subprocess.run(
                        [
                            "ffprobe", "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            str(video_path),
                        ],
                        capture_output=True, text=True, timeout=30,
                    )
                    duration = float(ffprobe_result.stdout.strip())
                except Exception as e:
                    logger.warning("ffprobe не смог определить длину видео: %s", e)
                    duration = 30.0

                timestamps = [
                    0,
                    duration * 0.25,
                    duration * 0.50,
                    duration * 0.75,
                    min(duration * 0.99, duration - 0.1),
                ]

                for i, ts in enumerate(timestamps):
                    frame_path = tmp_dir / f"frame_{i:02d}.jpg"
                    subprocess.run(
                        [
                            "ffmpeg", "-ss", str(ts),
                            "-i", str(video_path),
                            "-frames:v", "1", "-q:v", "2",
                            str(frame_path), "-y",
                        ],
                        capture_output=True, timeout=30,
                    )
                    if frame_path.exists():
                        b64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")
                        images_b64.append({"b64": b64, "detail": "high"})
            else:
                display_url = post.get("displayUrl") or ""
                if display_url:
                    b64 = download_and_encode(display_url, tmp_dir / "thumbnail.jpg")
                    if b64:
                        images_b64.append({"b64": b64, "detail": "high"})
                fallback_thumbnail = True
                mechanic_note      = "(анализ по превью)"
        else:
            display_url = post.get("displayUrl") or ""
            if display_url:
                b64 = download_and_encode(display_url, tmp_dir / "thumbnail.jpg")
                if b64:
                    images_b64.append({"b64": b64, "detail": "high"})
            fallback_thumbnail = True
            mechanic_note      = "(анализ по превью)"

    return {
        "images_b64":         images_b64,
        "fallback_thumbnail": fallback_thumbnail,
        "mechanic_note":      mechanic_note,
    }


# ---------------------------------------------------------------------------
# GPT analysis
# ---------------------------------------------------------------------------

def _build_system_prompt(kate_ctx: dict) -> str:
    kate_bio          = kate_ctx.get("kate_bio", "")
    kate_avg_err      = kate_ctx.get("kate_avg_err", "н/д")
    kate_recent_posts = kate_ctx.get("kate_recent_posts", "данные недоступны")

    return f"""\
Ты аналитик контента Instagram. Анализируешь посты конкурентов SMM-эксперта.
Все значения полей пиши на русском языке.

Контекст об эксперте (используй для поля what_to_test):
Имя: Кейт Семёнова (@kate.jet)
Bio: {kate_bio}
Ниша: системный SMM, обучение специалистов
Позиционирование: Ex-Head of SMM Refocus, выручка $1 млн
Продукт: курс по системному SMM
Аудитория: SMM-специалисты, маркетологи
Средний ERR Кейт: {kate_avg_err}%
Последние 10 постов Кейт:
{kate_recent_posts}

Отвечай ТОЛЬКО валидным JSON. Никакого текста до или после JSON."""


def _build_visual_context(post_type: str, media_result: dict) -> str:
    n      = len(media_result["images_b64"])
    is_fbt = media_result["fallback_thumbnail"]

    if post_type == "photo":
        return "К посту прикреплено 1 фото. Учитывай визуал: текст на изображении, стиль, эмоциональный посыл."
    elif post_type == "carousel":
        return (
            f"К посту прикреплена карусель из {n} слайдов (показаны по порядку). "
            "Проанализируй: текст на каждом слайде, нарратив последовательности, визуальный стиль."
        )
    elif post_type == "video":
        if is_fbt:
            return "К посту прикреплено видео (показан только превью-кадр). Проанализируй то что видно."
        return (
            "К посту прикреплено видео. Показаны 5 кадров равномерно: первый=начало, последний=конец. "
            "Проанализируй: что происходит, текст на экране, развитие сюжета."
        )
    return ""


def _build_user_prompt(post_data: dict, visual_context: str, metrics: dict, avg_err: float, used_tactics: list) -> str:
    username      = post_data["username"]
    post_type     = post_data["post_type"]
    timestamp     = post_data["timestamp"]
    caption       = post_data["caption"]
    err           = metrics["err"]
    err_above_avg = metrics["err_above_avg"]

    used_tactics_block = ""
    if used_tactics:
        used_tactics_str = "\n".join(f"- {t}" for t in used_tactics)
        used_tactics_block = f"\nУже предложенные тактики для предыдущих постов этого конкурента — НЕ повторяй их:\n{used_tactics_str}\n"

    return f"""\
Проанализируй пост конкурента.

Конкурент: {username}
Тип поста: {post_type}
Дата: {timestamp}

{visual_context}

Caption:
{caption}

Метрики: ERR: {err}%, Средний ERR конкурента: {avg_err}%, ERR выше среднего: {err_above_avg}

Верни JSON со всеми полями (каждое обязательно, значения на русском):

"title" — первая строка caption или текст на обложке если информативнее
"topic" — главная тема одной строкой
"mechanic" — разбор ошибки / кейс / чек-лист / миф / продуктовый пост / личная история / факт / анонс / другое
"summary" — о чём пост, 1-2 предложения
"hook" — первый абзац caption дословно до первого переноса строки
"structure" — X → Y → Z максимум 4 элемента
"selling_insert" — фраза к покупке; "не найдено" если нет
"cta" — точная CTA-фраза; "не найдено" если нет
"cta_destination" — директ / комментарии / бот / сайт / ссылка в bio / "не найдено"
"has_lead_magnet" — да / нет
"lead_magnet_name" — название; "" если нет
"lead_magnet_how" — через коммент / в директ / по ссылке; "" если нет
"what_worked" — для ВСЕХ постов: опиши какие приёмы, триггеры, формулировки, структура, конфликт, инсайт, подача или механики могли повлиять на реакцию аудитории. Если ERR выше среднего — объясни что сработало хорошо и почему. Если ERR ниже среднего — объясни что могло ограничить реакцию и что можно было усилить. Минимум 3-4 конкретных наблюдения.
{used_tactics_block}"what_to_test" — одна конкретная тактика для Кейт которую она ещё НЕ использует. Называй точный формат, механику или хук — например: «рубрика с еженедельным фактом», «хук с провокационным вопросом без ответа», «CTA через ключевое слово в комментарии». Не повторяй рекомендацию которую уже дал для другого поста этого же конкурента. Не предлагай «карусель с кейсами» и «личные истории» если они уже есть в последних 10 постах Кейт. Одно предложение, конкретно."""


def analyze_with_gpt(
    post_data: dict,
    images_b64: list,
    kate_context: dict,
    metrics: dict,
    avg_err: float,
    used_tactics: list,
) -> Optional[dict]:
    import openai

    client      = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    url         = post_data.get("url", "?")
    system_msg  = _build_system_prompt(kate_context)
    post_type   = post_data.get("post_type", "")
    visual_ctx  = _build_visual_context(post_type, {"images_b64": images_b64,
                                                     "fallback_thumbnail": metrics.get("fallback_thumbnail", False)})
    user_prompt = _build_user_prompt(post_data, visual_ctx, metrics, avg_err, used_tactics)

    content: list[dict] = [{"type": "text", "text": user_prompt}]
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url":    f"data:image/jpeg;base64,{img['b64']}",
                "detail": img["detail"],
            },
        })

    raw = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=GPT_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": content},
                ],
                max_tokens=1200,
                temperature=0,
            )
            raw = response.choices[0].message.content or ""
            break
        except (openai.RateLimitError, openai.APIError) as e:
            logger.warning("Attempt %d/3 for %s: %s", attempt + 1, url, e)
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
            else:
                logger.error("Failed after 3 attempts: %s", url)
                return None

    if raw is None:
        return None

    # Strip markdown fences if present
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines    = stripped.splitlines()
        stripped = "\n".join(ln for ln in lines if not ln.startswith("```")).strip()

    try:
        return json.loads(stripped)
    except Exception:
        logger.error("JSON parse failed for %s: %s", url, stripped[:300])
        return None


# ---------------------------------------------------------------------------
# Output builders
# ---------------------------------------------------------------------------

def _postprocess_result(result: dict, post_type: str, media_result: dict, err_above_avg: str = "") -> None:
    """Apply defaults and mechanic notes in-place."""
    result.setdefault("title",            "")
    result.setdefault("topic",            "")
    result.setdefault("mechanic",         "")
    result.setdefault("summary",          "")
    result.setdefault("hook",             "")
    result.setdefault("structure",        "")
    result.setdefault("selling_insert",   "не найдено")
    result.setdefault("cta",              "не найдено")
    result.setdefault("cta_destination",  "не найдено")
    result.setdefault("has_lead_magnet",  "нет")
    result.setdefault("lead_magnet_name", "")
    result.setdefault("lead_magnet_how",  "")
    result.setdefault("what_worked",      "")
    result.setdefault("what_to_test",     "")

    # Ensure no-CTA fields not empty-string when "не найдено" expected
    for f in ("selling_insert", "cta", "cta_destination"):
        if not result[f]:
            result[f] = "не найдено"

    mechanic = result.get("mechanic") or ""
    note     = media_result.get("mechanic_note", "")
    if note and note not in mechanic:
        result["mechanic"] = f"{mechanic} {note}".strip()


def _build_row(
    username: str,
    post: dict,
    m: dict,
    avg_err: float,
    result: dict,
) -> dict:
    url   = m["url"]
    title = result.get("title") or ""
    return {
        "Дата выгрузки":                    datetime.utcnow().strftime("%d.%m.%Y"),
        "post_type":                         m["post_type"],  # техническое поле — не для Sheets
        "Конкурент":                        username,
        "Ссылка на пост + заголовок":       f"{url} | {title}",
        "Тема поста":                       result.get("topic", ""),
        "Механика подачи":                  result.get("mechanic", ""),
        "Кратко о чем пост":                result.get("summary", ""),
        "Хук / первый абзац":               result.get("hook", ""),
        "Структура поста":                  result.get("structure", ""),
        "Продающая вставка":                result.get("selling_insert", "не найдено"),
        "Какой CTA":                        result.get("cta", "не найдено"),
        "Куда ведет CTA":                   result.get("cta_destination", "не найдено"),
        "Есть лид-магнит":                  result.get("has_lead_magnet", "нет"),
        "Какой лид-магнит":                 result.get("lead_magnet_name", ""),
        "Как получить?":                    result.get("lead_magnet_how", ""),
        "Просмотры":                        m["views"],
        "Лайки":                            m["likes"],
        "Комментарии":                      m["comments"],
        "Репосты":                          m["reposts"],
        "ERR":                              str(m["err"]).replace(".", ",") + "%",
        "Средний ERR":                      str(avg_err).replace(".", ",") + "%",
        "ERR выше среднего?":               m["err_above_avg"],
        "Что могло сработать":              result.get("what_worked", ""),
        "Что можно протестировать у себя":  result.get("what_to_test", ""),
    }


def save_output(
    rows: list,
    username: str,
    avg_err: float,
    successful: int,
    failed: int,
) -> Path:
    out_dir  = BASE / "data" / username / "normalized"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "stage5e1_posts_analysis.json"

    payload = {
        "rows": rows,
        "meta": {
            "account":       username,
            "total":         len(rows),
            "successful":    successful,
            "failed":        failed,
            "avg_err":       avg_err,
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Read accounts.json before argument parsing (needed for --refresh-days default)
    accounts_config  = _load_accounts_config()
    default_refresh  = accounts_config.get("posts_refresh_days")  # None if absent

    parser = argparse.ArgumentParser(
        description="Stage 5E-1: Posts Analyzer (download + GPT + сохранение)"
    )
    parser.add_argument("--account",       required=True,       help="Instagram username (обязательный)")
    parser.add_argument("--limit",         type=int, default=5, help="Анализировать первые N постов (default: 5)")
    parser.add_argument("--dry-run",       action="store_true", help="Полный анализ без удаления tmp и без записи в Sheets")
    parser.add_argument("--metrics-only",  action="store_true", help="Только метрики без GPT")
    parser.add_argument("--download-only", action="store_true", help="Скачать медиа без GPT-анализа")
    parser.add_argument(
        "--post-types",
        default=None,
        help="Типы постов через запятую: photo,carousel,video. По умолчанию — все типы.",
    )
    parser.add_argument(
        "--refresh-days",
        type=lambda x: None if str(x).lower() == "none" else int(x),
        default=default_refresh,
        help=(
            "Переанализировать если пост старше N дней. "
            "0 = всегда, none = никогда (только новые). "
            "По умолчанию читается из data/accounts.json → posts_refresh_days."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    refresh_days  = args.refresh_days   # int | None
    allowed_types = (
        {t.strip() for t in args.post_types.split(",")}
        if args.post_types else None
    )

    # --- Dependency checks ---
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE / ".env", override=True)

    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY не найден")

    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0:
        sys.exit("ffmpeg не найден. Установите: brew install ffmpeg")

    # --- Load existing results ---
    existing_path = BASE / "data" / args.account / "normalized" / "stage5e1_posts_analysis.json"
    existing_rows: list = []
    url_to_rows: dict[str, list] = {}
    if existing_path.exists():
        try:
            existing      = json.loads(existing_path.read_text(encoding="utf-8"))
            existing_rows = existing.get("rows") or []
            for row in existing_rows:
                url = row.get("Ссылка на пост + заголовок", "").split(" | ")[0]
                if url:
                    url_to_rows.setdefault(url, []).append(row)
        except Exception as e:
            print(f"[warn] Не удалось прочитать существующий вывод: {e}")

    # --- Load data ---
    all_posts, _source_label, _url_to_raw = load_posts_unified(args.account)

    prof_path = BASE / "data" / args.account / "normalized" / "profile_summary.json"
    followers = 0
    if prof_path.exists():
        try:
            prof      = json.loads(prof_path.read_text(encoding="utf-8"))
            followers = int(_unwrap(prof, "followers_count") or 0)
        except Exception:
            pass

    # --- --metrics-only ---
    if args.metrics_only:
        posts    = all_posts[:args.limit] if args.limit else all_posts
        metrics  = compute_metrics(posts, followers)
        avg_err  = round(statistics.mean(m["err"] for m in metrics), 2) if metrics else 0.0
        kate_ctx = load_kate_context()
        print(f"=== Stage 5E-1: Posts Metrics | @{args.account} ===\n")
        for m in metrics:
            print(
                f"  {m['post_type']:10} | ERR {m['err']:6.2f}% | {m['likes']:5} likes | "
                f"{m['comments']:4} comm | {m['url']}"
            )
        print(f"\n  avg_err: {avg_err}%  |  followers: {followers}")
        print(f"\n  Kate bio: {kate_ctx['kate_bio'][:80]}...")
        print(f"  Kate avg_err: {kate_ctx['kate_avg_err']}%")
        print(f"  Kate posts:\n{kate_ctx['kate_recent_posts']}")
        sys.exit(0)

    # --- --download-only ---
    if args.download_only:
        posts   = all_posts[:args.limit] if args.limit else all_posts
        metrics = compute_metrics(posts, followers)
        print(f"=== Stage 5E-1: Download Only | @{args.account} ===\n")
        for post, m in zip(posts, metrics):
            result = download_media(post, m["post_type"], args.account)
            n_imgs = len(result["images_b64"])
            note   = f"  [{result['mechanic_note']}]" if result["mechanic_note"] else ""
            print(f"  {m['post_type']:10} | {n_imgs} images{note} | {m['url']}")
        sys.exit(0)

    # --- Full run or dry-run ---
    is_dry = args.dry_run

    print(f"=== Stage 5E-1: Posts Analyzer | @{args.account} | {'DRY-RUN' if is_dry else 'FULL RUN'} ===")
    types_label = ", ".join(sorted(allowed_types)) if allowed_types else "все"
    print(f"  post-types: {types_label} | refresh-days: {refresh_days} | limit: {args.limit}")
    print(f"  Источник: {_source_label}")
    if existing_rows:
        print(f"  [resume] {len(existing_rows)} строк уже есть в базе\n")
    else:
        print()

    # --- Filter: build posts_to_analyze ---
    posts_to_analyze: list = []
    for p in all_posts:
        url       = p.get("url") or ""
        raw_type  = p.get("type") or "Image"
        post_type = _post_type(raw_type)

        # a) Type filter
        if allowed_types and post_type not in allowed_types:
            print(f"  [skip-type] {post_type} | {url}")
            continue

        # b) Existing rows for this URL
        rows_for_url = url_to_rows.get(url, [])

        # c) Refresh logic
        if rows_for_url:
            if refresh_days is None:
                print(f"  [skip] уже есть | {url}")
                continue
            elif refresh_days == 0:
                pass  # always re-analyze
            else:
                # Compute days since last analysis
                dated = [
                    r for r in rows_for_url
                    if "Дата выгрузки" in r and r["Дата выгрузки"]
                ]
                if dated:
                    try:
                        last_date  = max(
                            datetime.strptime(r["Дата выгрузки"], "%d.%m.%Y") for r in dated
                        )
                        days_since = (datetime.utcnow() - last_date).days
                    except ValueError:
                        days_since = 9999
                else:
                    days_since = 9999  # no date field → treat as very old

                if days_since <= refresh_days:
                    print(f"  [skip] свежий ({days_since}d) | {url}")
                    continue
                # else days_since > refresh_days → re-analyze

        # d) New post or re-analysis → schedule
        posts_to_analyze.append(p)
        if args.limit and len(posts_to_analyze) >= args.limit:
            break

    # Warn if fewer than requested
    if args.limit and len(posts_to_analyze) < args.limit:
        n = len(posts_to_analyze)
        print(f"\n  [warn] Найдено только {n} из {args.limit} запрошенных")

    if not posts_to_analyze:
        print("\n[OK] Нет постов для анализа.")
        out_path = save_output(existing_rows, args.account, 0.0, 0, 0)
        print(f"[OK] Сохранено: {out_path.relative_to(BASE)}")
        sys.exit(0)

    # Per-post ERR; pre_avg_err used only as GPT prompt context
    metrics     = compute_metrics(posts_to_analyze, followers)
    pre_avg_err = round(statistics.mean(m["err"] for m in metrics), 2) if metrics else 0.0
    kate_ctx    = load_kate_context()

    total      = len(posts_to_analyze)
    successes: list = []  # (post, m, result, media)
    failed     = 0

    print()
    used_tactics: list = []
    for i, (post, m) in enumerate(zip(posts_to_analyze, metrics)):
        print(f"[{i+1}/{total}] {m['post_type']} | {m['url']}")

        # Download media
        media = download_media(post, m["post_type"], args.account)
        n_img = len(media["images_b64"])
        print(f"  media: {n_img} images  {media['mechanic_note'] or ''}")

        # GPT analysis
        post_data = {
            "username":  args.account,
            "url":       m["url"],
            "post_type": m["post_type"],
            "timestamp": post.get("timestamp") or "",
            "caption":   m["caption"],
        }
        m_with_extra = {**m, "fallback_thumbnail": media["fallback_thumbnail"]}

        result = analyze_with_gpt(post_data, media["images_b64"], kate_ctx, m_with_extra, pre_avg_err, used_tactics)
        if result is None:
            print(f"  GPT: FAILED")
            failed += 1
        else:
            _postprocess_result(result, m["post_type"], media, m["err_above_avg"])
            tactic = result.get("what_to_test", "")
            if tactic:
                used_tactics.append(tactic)
            successes.append((post, m, result, media))
            print(f"  GPT: OK  mechanic={result.get('mechanic', '')[:50]}")

        # Cleanup tmp (only in full run)
        if not is_dry:
            post_id  = post.get("id") or post.get("shortCode") or "unknown"
            tmp_post = BASE / "data" / args.account / "tmp" / "posts" / str(post_id)
            if tmp_post.exists():
                shutil.rmtree(tmp_post)

    # avg_err and err_above_avg computed from successful posts only
    successful = len(successes)
    avg_err    = round(statistics.mean(m["err"] for _, m, _, _ in successes), 2) if successes else 0.0
    rows: list = []
    for post, m, result, _media in successes:
        m["err_above_avg"] = "да" if m["err"] > avg_err else "нет"
        rows.append(_build_row(args.account, post, m, avg_err, result))

    # Merge: drop existing rows for re-analyzed URLs, then append new rows
    reanalyzed_urls = {
        row.get("Ссылка на пост + заголовок", "").split(" | ")[0]
        for row in rows
    }
    filtered_existing = [
        r for r in existing_rows
        if r.get("Ссылка на пост + заголовок", "").split(" | ")[0] not in reanalyzed_urls
    ]
    all_rows = filtered_existing + rows
    out_path = save_output(all_rows, args.account, avg_err, successful, failed)
    print(f"\n[OK] Сохранено: {out_path.relative_to(BASE)}")

    # Summary
    if is_dry:
        print("\n=== DRY-RUN Preview (первые 2 новые строки) ===")
        for row in rows[:2]:
            preview = {k: str(v)[:80] for k, v in row.items()}
            print(json.dumps(preview, ensure_ascii=False, indent=2))
        tmp_path = f"data/{args.account}/tmp/posts/"
        print(f"\nУспешно: {successful}/{total} | avg_err: {avg_err}% | tmp: {tmp_path}")
    else:
        print(f"Успешно: {successful}/{total} | avg_err: {avg_err}%")


if __name__ == "__main__":
    main()
