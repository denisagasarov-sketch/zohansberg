"""Stage 14: анализ постов (Metrics + Media + GPT).

Читает normalized/stage5e0_posts_index.json и raw/stage5e0_posts_raw.json.
Скачивает медиа (фото/карусель/видео с 5 кадрами ffmpeg), анализирует через GPT-4o.
Сохраняет normalized/stage5e1_posts_analysis.json.

Использование:
  python3 -m pipeline.stages.analyze_posts --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_posts --account vlada_kliuiko
"""

import argparse
import base64
import json
import logging
import shutil
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized, raw

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
FILTER_MODEL = "gpt-4o-mini"
MAX_SLIDES = 10
MAX_CONTENT_BYTES = 200 * 1024 * 1024

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
}

FILTER_SYSTEM_PROMPT = """\
Ты фильтруешь посты Instagram. Отвечай только валидным JSON без текста до или после:
{"is_relevant": true/false, "content_type": "professional|personal|mixed", "reason": "одно слово"}

Правила:
- is_relevant=false: поздравления с праздниками, чистый быт, личные путешествия без экспертной ценности
- is_relevant=true: всё остальное

content_type:
- professional = экспертный контент, кейсы, обучение, продажи, соцдоки, тренды, провокация, разборы
- personal = путешествия, праздники, быт, личные события без экспертного вывода
- mixed = личная история с экспертным выводом или уроком"""

SYSTEM_PROMPT = """\
Ты аналитик контента Instagram. Анализируешь посты конкурентов.
Все значения полей пиши на русском языке.
Отвечай ТОЛЬКО валидным JSON. Никакого текста до или после JSON.

СПРАВОЧНИК МЕХАНИК ПОДАЧИ (используй только эти):
- Обучение / польза — инструкция, как сделать, шаги, разбор
- Кейс / история клиента — имя/ситуация → процесс → результат с цифрой
- Личная история — автор рассказывает про себя, прошедшее время, эмоция+вывод
- Боли аудитории — начинается с проблемы читателя, "знакомо?", симптомы
- Провокация / мнение — спорное утверждение, "все думают X, но на самом деле"
- Разбор ошибки — "не делай", "чаще всего", неправильный путь и почему
- Чек-лист / список — нумерация, тире, карусель с пунктами
- Экспертный факт — цифра или нестандартный факт в первом абзаце
- Продуктовый пост — цена, формат, что входит, как купить
- Анонс / событие — дата, "скоро", "открываю набор"
- Отзыв / соцдок — скриншот или цитата клиента как основа
- Диагностика — "проверь себя", вопросы с вариантами
- Интрига / сериал — обрыв на кульминации, "расскажу в следующий раз"
- За кулисами — процесс изнутри, черновики, рабочие моменты"""

USER_PROMPT_TEMPLATE = """\
Проанализируй пост конкурента.

Конкурент: {username}
Тип поста: {post_type}
Дата: {timestamp}

{visual_context}

Caption:
{caption}

Метрики: ERR: {err}%, Средний ERR конкурента: {avg_err}%, ERR выше среднего: {err_above_avg}

Верни JSON со всеми полями (каждое обязательно, значения на русском):

"title" — текст написанный на обложке поста (первый слайд карусели или единственное фото). Считывать только с изображения через Vision, не из caption. Если на обложке нет текста или пост не содержит изображения — "нет заголовка".
"topic" — главная тема одной строкой
"mechanic" — выбери одну механику из СПРАВОЧНИКА МЕХАНИК ПОДАЧИ выше
"summary" — о чём пост, 1-2 предложения
"hook_type" — тип хука из списка: провокационный вопрос / шок-факт / обещание пользы / интрига и недосказанность / противоречие и антитезис / идентификация с болью / история с поворотом / социальное доказательство / прямой призыв / без хука
"hook_text" — дословно первая строка caption до первого переноса строки (не перефразировать)
"structure" — структура поста в формате: [блок] конкретное содержание → [блок] конкретное содержание → ...
Блоки: проблема / инсайт / история / аргумент / пример / CTA / продажа
Пример: "проблема: таргет не работает без сильного оффера → инсайт: оффер это не скидка, а трансформация → пример: кейс Маши +300к → CTA: напиши в директ"
Не писать абстрактно ("проблема → решение"), всегда конкретное содержание каждого блока.
"selling_insert" — фраза к покупке; "не найдено" если нет
"cta" — точная CTA-фраза; "не найдено" если нет
"cta_destination" — директ / комментарии / бот / сайт / ссылка в bio / "не найдено"
"has_lead_magnet" — да / нет
"lead_magnet_name" — название; "" если нет
"lead_magnet_how" — через коммент / в директ / по ссылке; "" если нет
"rubric" — рубрика поста из списка: Экспертный контент / Кейсы и результаты / Личное и за кулисами / Продажи и анонсы / Соцдоки и отзывы / Тренды и рынок / Провокация и мнение / Обучение и польза / Праздники и поздравления / AI и технологии
"what_worked" — опиши какие приёмы, триггеры, формулировки, структура или механики могли повлиять на реакцию. Минимум 3-4 конкретных наблюдения.
"what_to_test" — одна конкретная тактика для применения. Называй точный формат, механику или хук. Одно предложение."""


def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video", "Image": "photo"}.get(raw_type, "photo")


def _unwrap(obj: dict, *keys):
    for k in keys:
        v = obj.get(k)
        if v is not None:
            return v.get("value") if isinstance(v, dict) else v
    return None


def _parse_json(raw_text: str) -> tuple[dict, str | None]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(ln for ln in lines if not ln.startswith("```")).strip()
    try:
        return json.loads(raw_text), None
    except json.JSONDecodeError as e:
        return {}, str(e)


def _is_relevant(caption: str) -> tuple[bool, str, str]:
    """GPT-4o-mini фильтр мусорных постов.

    Возвращает (is_relevant, content_type, reason).
    content_type: "professional" | "personal" | "mixed"
    """
    snippet = caption[:300]
    messages = [
        {"role": "system", "content": FILTER_SYSTEM_PROMPT},
        {"role": "user", "content": snippet or "(нет caption)"},
    ]
    try:
        raw_text = chat(messages, model=FILTER_MODEL, max_tokens=80)
        parsed, err = _parse_json(raw_text)
        if err:
            return True, "professional", ""
        is_rel      = bool(parsed.get("is_relevant", True))
        content_type = str(parsed.get("content_type", "professional"))
        reason       = str(parsed.get("reason", ""))
        return is_rel, content_type, reason
    except Exception as e:
        logger.warning("Фильтр: ошибка %s — пост не фильтруется", e)
        return True, "professional", ""


def _load_posts_index(username: str) -> tuple[list, dict]:
    """Загружает stage5e0_posts_index.json и raw-данные для URL медиа.

    Returns (posts_unified, url_to_raw)
    """
    index_path = normalized(username, "stage5e0_posts_index.json")
    if not index_path.exists():
        raise FileNotFoundError(
            f"Не найден {index_path}. Сначала запустите collect_posts (stage 13)."
        )
    index = json.loads(index_path.read_text(encoding="utf-8"))
    posts_index = index.get("posts") or []

    url_to_raw: dict[str, dict] = {}
    raw_path = raw(username, "stage5e0_posts_raw.json")
    if raw_path.exists():
        try:
            for item in json.loads(raw_path.read_text(encoding="utf-8")):
                url = item.get("url") or ""
                if not url.startswith("http"):
                    short = item.get("shortCode") or item.get("id") or ""
                    url = f"https://www.instagram.com/p/{short}/" if short else ""
                if url:
                    url_to_raw[url] = item
        except Exception as e:
            logger.warning("Не удалось загрузить stage5e0_posts_raw.json: %s", e)

    _reverse_type = {"carousel": "Sidecar", "video": "Video", "photo": "Image"}
    posts_out = []
    for p in posts_index:
        url = p.get("url") or ""
        raw_item = url_to_raw.get(url, {})
        unified = dict(raw_item)
        if not unified.get("type"):
            unified["type"] = _reverse_type.get(p.get("post_type", "photo"), "Image")
        unified["likesCount"] = p.get("likes", 0)
        unified["commentsCount"] = p.get("comments", 0)
        unified["videoPlayCount"] = p.get("views", 0)
        unified["url"] = url
        unified["shortCode"] = p.get("short_code") or unified.get("shortCode") or ""
        unified["caption"] = raw_item.get("caption") or p.get("caption_preview") or ""
        unified["timestamp"] = p.get("timestamp") or unified.get("timestamp") or ""
        posts_out.append(unified)

    return posts_out, url_to_raw


def _load_followers(username: str) -> int:
    prof_path = normalized(username, "profile_summary.json")
    if not prof_path.exists():
        return 0
    try:
        prof = json.loads(prof_path.read_text(encoding="utf-8"))
        return int(_unwrap(prof, "followers_count") or 0)
    except Exception:
        return 0


def _compute_metrics(posts: list, followers: int) -> list[dict]:
    results = []
    for post in posts:
        raw_type = post.get("type") or "Image"
        raw_likes = int(post.get("likesCount") or 0)
        likes_hidden = raw_likes < 0            # Instagram скрыл лайки (-1)
        likes = None if likes_hidden else raw_likes
        comments = int(post.get("commentsCount") or 0)
        reposts = int(post.get("sharesCount") or 0)
        views = int(post.get("videoPlayCount") or post.get("videoViewCount") or 0)

        # ERR считаем только если лайки известны И есть followers. Иначе — None (н/д).
        if likes_hidden or followers <= 0:
            err = None
        else:
            err = round((likes + comments + reposts) / followers * 100, 2)

        results.append({
            "post_id": post.get("id") or post.get("shortCode") or "",
            "url": post.get("url") or "",
            "raw_type": raw_type,
            "post_type": _post_type(raw_type),
            "caption": post.get("caption") or "(caption отсутствует)",
            "likes": likes,                     # None = скрыто
            "likes_hidden": likes_hidden,
            "comments": comments,
            "reposts": reposts,
            "views": views,
            "err": err,                         # None = н/д
            "err_above_avg": None,
        })

    # Средний ERR — только по постам с известным ERR (None исключаем).
    known = [r["err"] for r in results if r["err"] is not None]
    if known:
        avg = statistics.mean(known)
        for r in results:
            if r["err"] is None:
                r["err_above_avg"] = "н/д"
            else:
                r["err_above_avg"] = "да" if r["err"] > avg else "нет"
    return results


def _download_and_encode(url: str, save_path: Path) -> str | None:
    try:
        resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        content_length = int(resp.headers.get("Content-Length", 0))
        if content_length > MAX_CONTENT_BYTES:
            logger.warning("Пропущен файл >200MB: %s", url[:80])
            return None
        save_path.parent.mkdir(parents=True, exist_ok=True)
        data = resp.content
        save_path.write_bytes(data)
        return base64.b64encode(data).decode("utf-8")
    except Exception as e:
        logger.error("Ошибка скачивания %s: %s", url[:80], e)
        return None


def _download_media(post: dict, post_type: str, tmp_dir: Path) -> tuple[list[dict], str]:
    """Скачивает медиа поста. Возвращает (images_b64, mechanic_note)."""
    images_b64: list[dict] = []
    mechanic_note = ""

    if post_type == "photo":
        url = post.get("displayUrl") or ""
        if url:
            b64 = _download_and_encode(url, tmp_dir / "image.jpg")
            if b64:
                images_b64.append({"b64": b64, "detail": "high"})

    elif post_type == "carousel":
        slide_urls = [
            c.get("displayUrl") for c in post.get("childPosts", [])
            if c.get("displayUrl")
        ]
        if not slide_urls:
            slide_urls = [u for u in post.get("images", []) if u]
        for i, url in enumerate(slide_urls[:MAX_SLIDES]):
            b64 = _download_and_encode(url, tmp_dir / f"slide_{i:02d}.jpg")
            if b64:
                images_b64.append({"b64": b64, "detail": "high"})
        if not images_b64:
            mechanic_note = "(слайды недоступны)"

    elif post_type == "video":
        video_url = post.get("videoUrl") or ""
        if video_url:
            video_path = tmp_dir / "video.mp4"
            b64_video = _download_and_encode(video_url, video_path)
            if b64_video and video_path.exists():
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
                        capture_output=True, text=True, timeout=30,
                    )
                    duration = float(probe.stdout.strip())
                except Exception:
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
                        ["ffmpeg", "-ss", str(ts), "-i", str(video_path),
                         "-frames:v", "1", "-q:v", "2", str(frame_path), "-y"],
                        capture_output=True, timeout=30,
                    )
                    if frame_path.exists():
                        b64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")
                        images_b64.append({"b64": b64, "detail": "high"})
            else:
                display_url = post.get("displayUrl") or ""
                if display_url:
                    b64 = _download_and_encode(display_url, tmp_dir / "thumbnail.jpg")
                    if b64:
                        images_b64.append({"b64": b64, "detail": "high"})
                mechanic_note = "(анализ по превью)"
        else:
            display_url = post.get("displayUrl") or ""
            if display_url:
                b64 = _download_and_encode(display_url, tmp_dir / "thumbnail.jpg")
                if b64:
                    images_b64.append({"b64": b64, "detail": "high"})
            mechanic_note = "(анализ по превью)"

    return images_b64, mechanic_note


def _visual_context(post_type: str, n_images: int, is_fallback: bool) -> str:
    if post_type == "photo":
        return "К посту прикреплено 1 фото. Учитывай визуал: текст на изображении, стиль, эмоциональный посыл."
    elif post_type == "carousel":
        return (
            f"К посту прикреплена карусель из {n_images} слайдов (показаны по порядку). "
            "Проанализируй: текст на каждом слайде, нарратив последовательности, визуальный стиль."
        )
    elif post_type == "video":
        if is_fallback:
            return "К посту прикреплено видео (показан только превью-кадр). Проанализируй то что видно."
        return (
            "К посту прикреплено видео. Показаны 5 кадров равномерно: первый=начало, последний=конец. "
            "Проанализируй: что происходит, текст на экране, развитие сюжета."
        )
    return ""


def _analyze_with_gpt(
    username: str,
    post_type: str,
    timestamp: str,
    caption: str,
    images_b64: list[dict],
    mechanic_note: str,
    metrics: dict,
    avg_err: float,
) -> dict:
    is_fallback = bool(mechanic_note)
    visual_ctx = _visual_context(post_type, len(images_b64), is_fallback)

    user_prompt = USER_PROMPT_TEMPLATE.format(
        username=username,
        post_type=post_type,
        timestamp=timestamp,
        visual_context=visual_ctx,
        caption=caption,
        err=metrics["err"],
        avg_err=avg_err,
        err_above_avg=metrics["err_above_avg"],
    )

    content: list[dict] = [{"type": "text", "text": user_prompt}]
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img['b64']}", "detail": img["detail"]},
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    try:
        raw_text = chat(messages, model=MODEL, max_tokens=1200)
        parsed, err = _parse_json(raw_text)
        if err:
            logger.error("JSON parse failed: %s", raw_text[:200])
            return {}
        return parsed
    except Exception as e:
        logger.error("GPT ошибка: %s", e)
        return {}


def _postprocess(result: dict, mechanic_note: str) -> None:
    result.setdefault("title", "нет заголовка")
    result.setdefault("topic", "")
    result.setdefault("mechanic", "")
    result.setdefault("summary", "")
    result.setdefault("hook_type", "без хука")
    result.setdefault("hook_text", "")
    result.setdefault("structure", "")
    result.setdefault("selling_insert", "не найдено")
    result.setdefault("cta", "не найдено")
    result.setdefault("cta_destination", "не найдено")
    result.setdefault("has_lead_magnet", "нет")
    result.setdefault("lead_magnet_name", "")
    result.setdefault("lead_magnet_how", "")
    result.setdefault("rubric", "")
    result.setdefault("what_worked", "")
    result.setdefault("what_to_test", "")
    for f in ("selling_insert", "cta", "cta_destination"):
        if not result[f]:
            result[f] = "не найдено"
    if not result["title"]:
        result["title"] = "нет заголовка"
    if mechanic_note and mechanic_note not in (result.get("mechanic") or ""):
        result["mechanic"] = f"{result['mechanic']} {mechanic_note}".strip()


def _fmt_err(err) -> str:
    return "н/д" if err is None else (str(err).replace(".", ",") + "%")


def _fmt_likes(likes):
    return "скрыто" if likes is None else likes


def _build_row(username: str, m: dict, avg_err: float, result: dict) -> dict:
    url = m["url"]
    return {
        "Дата выгрузки": datetime.utcnow().strftime("%d.%m.%Y"),
        "post_type": m["post_type"],
        "Конкурент": username,
        "Ссылка на пост": url,
        "Заголовок поста": result.get("title", "нет заголовка"),
        "Тема поста": result.get("topic", ""),
        "Механика подачи": result.get("mechanic", ""),
        "Кратко о чем пост": result.get("summary", ""),
        "Тип хука": result.get("hook_type", "без хука"),
        "Хук / первый абзац": result.get("hook_text", ""),
        "Структура поста": result.get("structure", ""),
        "Продающая вставка": result.get("selling_insert", "не найдено"),
        "Какой CTA": result.get("cta", "не найдено"),
        "Куда ведет CTA": result.get("cta_destination", "не найдено"),
        "Есть лид-магнит": result.get("has_lead_magnet", "нет"),
        "Какой лид-магнит": result.get("lead_magnet_name", ""),
        "Как получить?": result.get("lead_magnet_how", ""),
        "Рубрика": result.get("rubric", ""),
        "Просмотры": m["views"],
        "Лайки": _fmt_likes(m["likes"]),
        "Комментарии": m["comments"],
        "Репосты": m["reposts"],
        "ERR": _fmt_err(m["err"]),
        "Средний ERR": _fmt_err(avg_err),
        "ERR выше среднего?": m["err_above_avg"],
        "Что могло сработать": result.get("what_worked", ""),
        "Что можно протестировать у себя": result.get("what_to_test", ""),
    }


def _build_filtered_row(username: str, m: dict, reason: str) -> dict:
    """Строка таблицы для отфильтрованного поста."""
    return {
        "Дата выгрузки": datetime.utcnow().strftime("%d.%m.%Y"),
        "post_type": m["post_type"],
        "Конкурент": username,
        "Ссылка на пост": m["url"],
        "Заголовок поста": "filtered_out",
        "Тема поста": reason,
        "Механика подачи": "",
        "Кратко о чем пост": "",
        "Тип хука": "",
        "Хук / первый абзац": "",
        "Структура поста": "",
        "Продающая вставка": "",
        "Какой CTA": "",
        "Куда ведет CTA": "",
        "Есть лид-магнит": "",
        "Какой лид-магнит": "",
        "Как получить?": "",
        "Рубрика": "",
        "Просмотры": m["views"],
        "Лайки": _fmt_likes(m["likes"]),
        "Комментарии": m["comments"],
        "Репосты": m["reposts"],
        "ERR": _fmt_err(m["err"]),
        "Средний ERR": "",
        "ERR выше среднего?": "",
        "Что могло сработать": "",
        "Что можно протестировать у себя": "",
    }


def analyze(username: str, dry_run: bool = False, content_filter: str = "all") -> dict:
    """Анализирует посты через GPT-4o, сохраняет stage5e1_posts_analysis.json.

    content_filter:
      "all"          — пропускать всё что is_relevant=true
      "professional" — пропускать только professional и mixed
      "personal"     — пропускать только personal
    """
    get_account(username)
    posts, _url_to_raw = _load_posts_index(username)

    allowed_types = get_account(username).get("posts_sheet_types", ["photo", "carousel"])
    posts = [p for p in posts if _post_type(p.get("type", "Image")) in allowed_types]

    logger.info(
        "[14] analyze_posts | @%s | posts=%d | dry_run=%s",
        username, len(posts), dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] OpenAI не вызывается, файлы не записываются")
        return {"dry_run": True, "posts": []}

    followers = _load_followers(username)
    metrics = _compute_metrics(posts, followers)
    # Средний ERR — только по постам с известным ERR (скрытые лайки → err=None).
    _known_err = [m["err"] for m in metrics if m["err"] is not None]
    avg_err = round(statistics.mean(_known_err), 2) if _known_err else None

    data_dir = normalized(username, "stage5e0_posts_index.json").parent.parent
    tmp_base = data_dir / "tmp" / "posts"

    rows: list[dict] = []
    ok_count = 0
    fail_count = 0
    filtered_count = 0

    for i, (post, m) in enumerate(zip(posts, metrics)):
        pos = i + 1
        logger.info("[%d/%d] %s | %s", pos, len(posts), m["post_type"], m["url"])

        # фильтрация мусора через gpt-4o-mini
        relevant, content_type, reason = _is_relevant(m["caption"])

        # фильтр по is_relevant
        if not relevant:
            logger.info("  FILTERED (мусор): %s", reason)
            filtered_count += 1
            rows.append(_build_filtered_row(username, m, "мусор"))
            continue

        # фильтр по content_filter
        type_allowed = (
            content_filter == "all"
            or (content_filter == "professional" and content_type in ("professional", "mixed"))
            or (content_filter == "personal"     and content_type == "personal")
        )
        if not type_allowed:
            logger.info("  FILTERED (не тот тип): content_type=%s filter=%s", content_type, content_filter)
            filtered_count += 1
            rows.append(_build_filtered_row(username, m, "не тот тип контента"))
            continue

        post_id = post.get("id") or post.get("shortCode") or f"post_{i}"
        tmp_dir = tmp_base / str(post_id)
        tmp_dir.mkdir(parents=True, exist_ok=True)

        images_b64, mechanic_note = _download_media(post, m["post_type"], tmp_dir)
        logger.info("  media: %d images %s", len(images_b64), mechanic_note)

        result = _analyze_with_gpt(
            username=username,
            post_type=m["post_type"],
            timestamp=post.get("timestamp") or "",
            caption=m["caption"],
            images_b64=images_b64,
            mechanic_note=mechanic_note,
            metrics=m,
            avg_err=avg_err,
        )

        if not result:
            result = {}
            fail_count += 1
            result["mechanic"] = "(GPT отказал)"
            logger.warning("  GPT: FAILED")
        else:
            ok_count += 1
            logger.info("  GPT: OK  mechanic=%s", result.get("mechanic", "")[:50])

        _postprocess(result, mechanic_note)
        rows.append(_build_row(username, m, avg_err, result))

        shutil.rmtree(tmp_dir, ignore_errors=True)

    output = {
        "account": username,
        "stage": "stage5e1",
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_filter_applied": content_filter,
        "posts_analyzed": len(posts),
        "posts_ok": ok_count,
        "posts_failed": fail_count,
        "filtered_count": filtered_count,
        "avg_err": avg_err,
        "rows": rows,
    }

    output_path = normalized(username, "stage5e1_posts_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Stage 14: Analyze Posts | @{username} ===")
    print(f"Проанализировано: {ok_count}/{len(posts)} | failed: {fail_count} | filtered: {filtered_count} | avg_err: {avg_err}%")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 14: analyze posts (Metrics + Media + GPT)")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать OpenAI")
    parser.add_argument(
        "--content-filter", default="all",
        choices=["all", "professional", "personal"],
        help="Какой контент анализировать (default: all)",
    )
    args = parser.parse_args()
    analyze(args.account, args.dry_run, content_filter=args.content_filter)
