"""Stage 12: анализ Reels (Vision + Text).

Для каждого Reel выполняет два OpenAI-прохода:
  1. Vision (gpt-4o) — hook + vizual_format из thumbnail.
  2. Text   (gpt-4o) — tema/bol/reshenie/cta/rol_v_voronke/kryuchok/struktura/hook_type
                       из transcript или caption.

Сохраняет normalized/stage5c2_reels_analysis.json.

Использование:
  python3 -m pipeline.stages.analyze_reels --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_reels --account vlada_kliuiko
"""

import argparse
import base64
import json
import logging
from datetime import datetime, timezone

import requests

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
PROMPT_VERSION = "v2"
IMAGE_DETAIL = "low"
MAX_TOKENS_VIS = 300
MAX_TOKENS_TXT = 600
MIN_TRANSCRIPT_WORDS = 20

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.instagram.com/",
}

VISION_SYSTEM = """\
Ты — аналитик Instagram Reels. Тебе показывают обложку (первый кадр) Reel.
Извлеки два поля и верни строго JSON — никакого текста вне JSON.

ПОЛЯ:
1. hook — главный элемент который останавливает скролл. Одна фраза: [что именно] + [почему цепляет].
   Примеры: "крупный красный текст с вопросом — читаешь до конца",
   "лицо с удивлением крупным планом — эмоциональный контакт".
   НЕ описывай всю сцену.
   data_status: "not_found" если: однотонный фон без текста, стандартный пейзаж без людей, логотип.
   ВАЖНО — хэштеги: если на экране написан хэштег (#слово) — НЕ упоминай хэштег.
   Опиши что происходит ВОКРУГ: цвет и текстура фона, есть ли люди или предметы, размер и цвет
   шрифта если текст декоративный.
   Пример: вместо "#маркетинг на красном фоне" пиши "крупный белый текст на ярко-красном фоне —
   контраст останавливает взгляд".
2. vizual_format — один из вариантов:
   "говорящая голова" | "текст на экране" | "скринкаст" | "b-roll" | "анимация" | "смешанный"

ПРАВИЛА:
- vizual_format определяй только по тому, что видно на кадре.
- Поле data_status у vizual_format: "ok" если определён, "not_found" если изображение нечитаемо.

ФОРМАТ (строго):
{
  "hook": {"value": "...", "data_status": "ok|not_found"},
  "vizual_format": {"value": "...", "data_status": "ok"}
}"""

TEXT_SYSTEM = """\
Ты — аналитик Instagram Reels. Тебе дан текст Reel (транскрипт или подпись).
Извлеки поля и верни строго JSON — никакого текста вне JSON.

ПОЛЯ:
1. tema        — о чём Reel, одна строка до 100 символов.
2. bol         — какую боль / проблему аудитории называет. "не найдено" если нет явной боли.
3. reshenie    — какое решение предлагает. "не найдено" если нет.
4. cta         — точный текст призыва к действию (ссылка, "подпишись", "напиши в директ" и т.д.).
                  "не найдено" если CTA нет.
5. rol_v_voronke — роль в воронке, один из вариантов:
   "знакомство" | "доверие" | "прогрев" | "продажа" | "лидогенерация"
6. kryuchok    — триггер из первых секунд который создаёт интригу.
                  НЕ пересказывай содержание ("рассказывает о каблуках" — это пересказ).
                  Пиши сам крючок близко к тексту ("оказывается каблуки носили солдаты" — это крючок).
                  Типы: неожиданный факт / история с неожиданной связью / вопрос без ответа /
                  спорное утверждение. "не найдено" если крючка нет.
7. struktura   — структура Reel в формате X → Y → Z, максимум 3 элемента.
                  Примеры: "факт → история → вывод", "боль → решение → CTA",
                  "вопрос → ответ → CTA", "тезис → аргументы → вывод".
                  Если не подходит ни один — описать своими словами в том же формате через →.
8. hook_type   — тип крючка по transcript, один из вариантов:
                  "вопрос" | "факт" | "история" | "провокация" | "обещание" | "не найдено".
                  Классифицируй по первым секундам транскрипта, независимо от поля kryuchok.
                  "не найдено" если явного крючка нет.

ПРАВИЛА:
- Отвечай только по переданному тексту, не домысливай.
- cta: бери дословно из текста, если есть. Не перефразируй.
- rol_v_voronke: знакомство = представление себя/продукта новой аудитории;
  доверие = кейсы/результаты/экспертиза; прогрев = обучение, польза без продажи;
  продажа = прямое предложение купить; лидогенерация = сбор контактов/заявок.

ФОРМАТ (строго):
{
  "tema":           {"value": "...", "data_status": "ok"},
  "bol":            {"value": "...", "data_status": "ok|not_found"},
  "reshenie":       {"value": "...", "data_status": "ok|not_found"},
  "cta":            {"value": "...", "data_status": "ok|not_found"},
  "rol_v_voronke":  {"value": "...", "data_status": "ok"},
  "kryuchok":       {"value": "...", "data_status": "ok|not_found"},
  "struktura":      {"value": "...", "data_status": "ok"},
  "hook_type":      {"value": "вопрос|факт|история|провокация|обещание|не найдено", "data_status": "ok|not_found"}
}"""


def _vision_user_prompt(position: int) -> str:
    return f"Reel #{position}. Проанализируй обложку и верни JSON с полями hook и vizual_format."


def _text_user_prompt(position: int, source: str, text: str) -> str:
    label = "Транскрипт" if source == "transcript" else "Подпись (caption)"
    return f"Reel #{position}.\n{label}:\n---\n{text}\n---\nИзвлеки поля и верни JSON."


def _fetch_image_as_data_uri(url: str, timeout: int = 10) -> tuple[str, str | None]:
    """Скачивает изображение и возвращает (data_uri, error_or_None).

    Instagram CDN URL-ы подписаны сессией и не могут быть получены серверами OpenAI напрямую.
    """
    try:
        resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return "", f"HTTP {resp.status_code}"
        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(resp.content).decode("ascii")
        return f"data:{content_type};base64,{b64}", None
    except Exception as e:
        return "", str(e)


def _parse_json(raw: str) -> tuple[dict, str | None]:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(ln for ln in lines if not ln.startswith("```")).strip()
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return {}, str(e)


def _word_count(text: str) -> int:
    return len(text.split())


def _pick_text_source(reel: dict) -> tuple[str, str]:
    transcript = (reel.get("transcript") or "").strip()
    caption = (reel.get("caption") or "").strip()
    if transcript and _word_count(transcript) >= MIN_TRANSCRIPT_WORDS:
        return "transcript", transcript
    if caption:
        return "caption", caption
    return "caption", ""


def _not_found_field(reason: str = "no_text") -> dict:
    return {"value": "не найдено", "data_status": "not_found", "skip_reason": reason}


def _truncate_at_word(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > 0 else cut


def _apply_length_limit(field: dict, max_len: int) -> dict:
    if isinstance(field, dict) and field.get("data_status") == "ok":
        val = field.get("value") or ""
        if len(val) > max_len:
            field = dict(field)
            field["value"] = _truncate_at_word(val, max_len)
    return field


def _call_vision(reel: dict, model: str) -> dict:
    position = reel.get("position", 0)
    display_url = (reel.get("thumbnail_url") or "").strip()

    if not display_url:
        return {
            "status": "skipped",
            "skip_reason": "no_thumbnail_url",
            "hook": _not_found_field("no_thumbnail_url"),
            "vizual_format": _not_found_field("no_thumbnail_url"),
            "tokens_used": 0,
        }

    data_uri, fetch_err = _fetch_image_as_data_uri(display_url)
    if fetch_err:
        return {
            "status": "fetch_error",
            "skip_reason": fetch_err,
            "hook": _not_found_field("fetch_error"),
            "vizual_format": _not_found_field("fetch_error"),
            "tokens_used": 0,
        }

    try:
        messages = [
            {"role": "system", "content": VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri, "detail": IMAGE_DETAIL},
                    },
                    {"type": "text", "text": _vision_user_prompt(position)},
                ],
            },
        ]
        raw_text = chat(messages, model=model, max_tokens=MAX_TOKENS_VIS)
        parsed, err = _parse_json(raw_text)
        if err:
            return {
                "status": "parse_error",
                "raw_response": raw_text[:300],
                "hook": _not_found_field("parse_error"),
                "vizual_format": _not_found_field("parse_error"),
                "tokens_used": 0,
            }
        hook = _apply_length_limit(parsed.get("hook", _not_found_field("missing_key")), 120)
        if "#" in (hook.get("value") or ""):
            hook = _not_found_field("hashtag_in_hook")
        return {
            "status": "ok",
            "hook": hook,
            "vizual_format": parsed.get("vizual_format", _not_found_field("missing_key")),
            "tokens_used": 0,
        }
    except Exception as e:
        return {
            "status": "openai_error",
            "error": str(e),
            "hook": _not_found_field("openai_error"),
            "vizual_format": _not_found_field("openai_error"),
            "tokens_used": 0,
        }


def _call_text(reel: dict, model: str) -> dict:
    position = reel.get("position", 0)
    source, text = _pick_text_source(reel)

    empty = {
        "status": "skipped",
        "skip_reason": "no_text",
        "source": source,
        "tema": _not_found_field("no_text"),
        "bol": _not_found_field("no_text"),
        "reshenie": _not_found_field("no_text"),
        "cta": _not_found_field("no_text"),
        "rol_v_voronke": _not_found_field("no_text"),
        "kryuchok": _not_found_field("no_text"),
        "struktura": _not_found_field("no_text"),
        "hook_type": _not_found_field("no_text"),
        "tokens_used": 0,
    }

    if not text:
        return empty

    try:
        messages = [
            {"role": "system", "content": TEXT_SYSTEM},
            {"role": "user", "content": _text_user_prompt(position, source, text)},
        ]
        raw_text = chat(messages, model=model, max_tokens=MAX_TOKENS_TXT)
        parsed, err = _parse_json(raw_text)
        if err:
            return {
                "status": "parse_error",
                "raw_response": raw_text[:300],
                "source": source,
                "tema": _not_found_field("parse_error"),
                "bol": _not_found_field("parse_error"),
                "reshenie": _not_found_field("parse_error"),
                "cta": _not_found_field("parse_error"),
                "rol_v_voronke": _not_found_field("parse_error"),
                "kryuchok": _not_found_field("parse_error"),
                "struktura": _not_found_field("parse_error"),
                "hook_type": _not_found_field("parse_error"),
                "tokens_used": 0,
            }
        kryuchok = _apply_length_limit(
            parsed.get("kryuchok", _not_found_field("missing_key")), 100
        )
        return {
            "status": "ok",
            "source": source,
            "tema": parsed.get("tema", _not_found_field("missing_key")),
            "bol": parsed.get("bol", _not_found_field("missing_key")),
            "reshenie": parsed.get("reshenie", _not_found_field("missing_key")),
            "cta": parsed.get("cta", _not_found_field("missing_key")),
            "rol_v_voronke": parsed.get("rol_v_voronke", _not_found_field("missing_key")),
            "kryuchok": kryuchok,
            "struktura": parsed.get("struktura", _not_found_field("missing_key")),
            "hook_type": parsed.get("hook_type", _not_found_field("missing_key")),
            "tokens_used": 0,
        }
    except Exception as e:
        return {
            "status": "openai_error",
            "error": str(e),
            "source": source,
            "tema": _not_found_field("openai_error"),
            "bol": _not_found_field("openai_error"),
            "reshenie": _not_found_field("openai_error"),
            "cta": _not_found_field("openai_error"),
            "rol_v_voronke": _not_found_field("openai_error"),
            "kryuchok": _not_found_field("openai_error"),
            "struktura": _not_found_field("openai_error"),
            "hook_type": _not_found_field("openai_error"),
            "tokens_used": 0,
        }


def _build_reel_result(reel: dict, vis: dict, txt: dict) -> dict:
    views = reel.get("view_count") or 0
    likes = reel.get("likes_count") or 0
    engagement_rate = f"{(likes / views * 100):.2f}%" if views > 0 else None
    return {
        "position": reel.get("position"),
        "reel_id": reel.get("reel_id"),
        "url": reel.get("url"),
        "view_count": views,
        "likes_count": likes,
        "is_pinned": reel.get("is_pinned"),
        "published_at": reel.get("timestamp"),
        "engagement_rate": engagement_rate,
        "vision_status": vis.get("status"),
        "hook": vis.get("hook"),
        "vizual_format": vis.get("vizual_format"),
        "text_status": txt.get("status"),
        "text_source": txt.get("source"),
        "tema": txt.get("tema"),
        "bol": txt.get("bol"),
        "reshenie": txt.get("reshenie"),
        "cta": txt.get("cta"),
        "rol_v_voronke": txt.get("rol_v_voronke"),
        "kryuchok": txt.get("kryuchok"),
        "struktura": txt.get("struktura"),
        "hook_type": txt.get("hook_type"),
    }


def _load_reels(username: str) -> list[dict]:
    input_path = normalized(username, "stage5c1_reels_index.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Не найден {input_path}. Сначала запустите collect_reels (stage 11)."
        )
    data = json.loads(input_path.read_text(encoding="utf-8"))
    reels = data.get("reels", [])
    if not reels:
        raise ValueError("В stage5c1_reels_index.json нет reels")
    return reels


def analyze(username: str, dry_run: bool = False) -> dict:
    """Анализирует Reels через Vision + Text, сохраняет stage5c2_reels_analysis.json."""
    get_account(username)
    reels = _load_reels(username)

    logger.info(
        "[12] analyze_reels | @%s | reels=%d | dry_run=%s",
        username, len(reels), dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] OpenAI не вызывается, файлы не записываются")
        preview = []
        for reel in reels:
            source, text = _pick_text_source(reel)
            thumbnail = (reel.get("thumbnail_url") or "").strip()
            preview.append({
                "position": reel.get("position"),
                "url": reel.get("url"),
                "view_count": reel.get("view_count"),
                "has_thumbnail": bool(thumbnail),
                "text_source": source,
                "text_words": _word_count(text) if text else 0,
            })
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "reels_total": len(reels),
            "planned_vision_calls": sum(1 for r in reels if r.get("thumbnail_url")),
            "planned_text_calls": sum(1 for r in reels if _pick_text_source(r)[1]),
            "actual_vision_calls": 0,
            "actual_text_calls": 0,
            "reels_preview": preview,
        }

    results = []
    ok_count = 0
    skipped_count = 0

    for reel in reels:
        pos = reel.get("position", "?")
        display_url = (reel.get("thumbnail_url") or "").strip()
        source, text = _pick_text_source(reel)

        logger.info(
            "[%s/%d] vision=%s text=%s(%d words)",
            pos, len(reels),
            "ok" if display_url else "skip",
            source, _word_count(text) if text else 0,
        )

        vis = _call_vision(reel, MODEL)
        logger.info("  Vision status: %s", vis["status"])

        txt = _call_text(reel, MODEL)
        logger.info("  Text status: %s", txt["status"])

        result = _build_reel_result(reel, vis, txt)
        results.append(result)

        if vis["status"] == "ok" or txt["status"] == "ok":
            ok_count += 1
        else:
            skipped_count += 1

    output = {
        "account": username,
        "stage": "stage5c2",
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reels_analyzed": len(reels),
        "reels_ok": ok_count,
        "reels_skipped": skipped_count,
        "reels": results,
    }

    output_path = normalized(username, "stage5c2_reels_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Stage 12: Analyze Reels | @{username} ===")
    print(f"Проанализировано: {ok_count}/{len(reels)} | skipped: {skipped_count}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 12: analyze reels (Vision + Text)")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать OpenAI")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
