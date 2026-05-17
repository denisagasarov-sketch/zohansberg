"""Stage 5C-2: Reels Analyzer.

Reads data/{account}/normalized/stage5c1_reels_index.json.
For each Reel, runs two OpenAI passes:
  1. Vision (gpt-4o)  — hook + vizual_format from thumbnail (displayUrl passed directly).
  2. Text   (gpt-4o)  — tema/bol/reshenie/cta/rol_v_voronke from transcript or caption.

Saves to data/{account}/normalized/stage5c2_reels_analysis.json.

Usage:
    python scripts/stage5c2_reels_analyzer.py --dry-run
    python scripts/stage5c2_reels_analyzer.py --account vlada_kliuiko
    python scripts/stage5c2_reels_analyzer.py --account vlada_kliuiko --model gpt-4o-mini
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent

# Resolve --account early so module-level paths are correct.
_ap = argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_early, _ = _ap.parse_known_args()
ACCOUNT  = _early.account
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"

INPUT_PATH  = NORM_DIR / "stage5c1_reels_index.json"
OUTPUT_PATH = NORM_DIR / "stage5c2_reels_analysis.json"

STAGE          = "stage5c2"
PROMPT_VERSION = "v2"
DEFAULT_MODEL  = "gpt-4o"
IMAGE_DETAIL   = "low"
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


def _fetch_image_as_data_uri(url: str, timeout: int = 10) -> tuple[str, str | None]:
    """Download image and return (data_uri, error_or_None)."""
    try:
        import requests
    except ImportError:
        return "", "requests not installed"
    try:
        resp = requests.get(url, headers=_DOWNLOAD_HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return "", f"HTTP {resp.status_code}"
        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(resp.content).decode("ascii")
        return f"data:{content_type};base64,{b64}", None
    except Exception as e:
        return "", str(e)


# ---------------------------------------------------------------------------
# Prompts — Vision
# ---------------------------------------------------------------------------

VISION_SYSTEM = """\
Ты — аналитик Instagram Reels. Тебе показывают обложку (первый кадр) Reel.
Извлеки два поля и верни строго JSON — никакого текста вне JSON.

ПОЛЯ:
1. hook — главный элемент который останавливает скролл. Одна фраза: [что именно] + [почему цепляет].
   Примеры: "крупный красный текст с вопросом — читаешь до конца",
   "лицо с удивлением крупным планом — эмоциональный контакт".
   НЕ описывай всю сцену.
   data_status: "not_found" если: однотонный фон без текста, стандартный пейзаж без людей, логотип.
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


def vision_user_prompt(position: int) -> str:
    return (
        f"Reel #{position}. Проанализируй обложку и верни JSON с полями hook и vizual_format."
    )


# ---------------------------------------------------------------------------
# Prompts — Text
# ---------------------------------------------------------------------------

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


def text_user_prompt(position: int, source: str, text: str) -> str:
    label = "Транскрипт" if source == "transcript" else "Подпись (caption)"
    return (
        f"Reel #{position}.\n"
        f"{label}:\n"
        f"---\n"
        f"{text}\n"
        f"---\n"
        "Извлеки поля и верни JSON."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> tuple[dict, str | None]:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            ln for ln in lines
            if not ln.startswith("```")
        ).strip()
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return {}, str(e)


def _word_count(text: str) -> int:
    return len(text.split())


def _pick_text_source(reel: dict) -> tuple[str, str]:
    """Return (source_label, text).

    Prefer transcript when it has >= MIN_TRANSCRIPT_WORDS (meaningful speech).
    Fall back to caption regardless of length — even a short caption is worth analyzing.
    """
    transcript = (reel.get("transcript") or "").strip()
    caption    = (reel.get("caption")    or "").strip()

    if transcript and _word_count(transcript) >= MIN_TRANSCRIPT_WORDS:
        return "transcript", transcript
    if caption:
        return "caption", caption
    return "caption", ""


def _not_found_field(reason: str = "no_text") -> dict:
    return {"value": "не найдено", "data_status": "not_found", "skip_reason": reason}


def _truncate_at_word(text: str, max_len: int) -> str:
    """Trim to max_len chars, cutting at the last space to avoid mid-word breaks."""
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    last_space = cut.rfind(" ")
    return cut[:last_space] if last_space > 0 else cut


def _apply_length_limit(field: dict, max_len: int) -> dict:
    """Truncate field value in-place if data_status==ok and value exceeds max_len."""
    if isinstance(field, dict) and field.get("data_status") == "ok":
        val = field.get("value") or ""
        if len(val) > max_len:
            field = dict(field)  # don't mutate parsed dict
            field["value"] = _truncate_at_word(val, max_len)
    return field


# ---------------------------------------------------------------------------
# OpenAI calls
# ---------------------------------------------------------------------------

def call_vision(client, reel: dict, model: str) -> dict:
    """Returns {status, hook, vizual_format, tokens_used}.

    Instagram CDN URLs are session-signed and can't be fetched by OpenAI servers.
    We download the image locally and pass it as a base64 data URI.
    """
    position    = reel.get("position", 0)
    display_url = (reel.get("thumbnail_url") or "").strip()

    if not display_url:
        return {
            "status":       "skipped",
            "skip_reason":  "no_thumbnail_url",
            "hook":         _not_found_field("no_thumbnail_url"),
            "vizual_format":_not_found_field("no_thumbnail_url"),
            "tokens_used":  0,
        }

    data_uri, fetch_err = _fetch_image_as_data_uri(display_url)
    if fetch_err:
        return {
            "status":       "fetch_error",
            "skip_reason":  fetch_err,
            "hook":         _not_found_field("fetch_error"),
            "vizual_format":_not_found_field("fetch_error"),
            "tokens_used":  0,
        }

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS_VIS,
            messages=[
                {"role": "system", "content": VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri, "detail": IMAGE_DETAIL},
                        },
                        {"type": "text", "text": vision_user_prompt(position)},
                    ],
                },
            ],
        )
        raw    = response.choices[0].message.content or ""
        tokens = getattr(response.usage, "total_tokens", 0)
        parsed, err = _parse_json(raw)
        if err:
            return {
                "status":        "parse_error",
                "raw_response":  raw[:300],
                "hook":          _not_found_field("parse_error"),
                "vizual_format": _not_found_field("parse_error"),
                "tokens_used":   tokens,
            }
        hook = _apply_length_limit(
            parsed.get("hook", _not_found_field("missing_key")), 80
        )
        return {
            "status":        "ok",
            "hook":          hook,
            "vizual_format": parsed.get("vizual_format", _not_found_field("missing_key")),
            "tokens_used":   tokens,
        }
    except Exception as e:
        return {
            "status":        "openai_error",
            "error":         str(e),
            "hook":          _not_found_field("openai_error"),
            "vizual_format": _not_found_field("openai_error"),
            "tokens_used":   0,
        }


def call_text(client, reel: dict, model: str) -> dict:
    """Returns {status, source, tema, bol, reshenie, cta, rol_v_voronke, tokens_used}."""
    position       = reel.get("position", 0)
    source, text   = _pick_text_source(reel)

    empty_result = {
        "status":        "skipped",
        "skip_reason":   "no_text",
        "source":        source,
        "tema":          _not_found_field("no_text"),
        "bol":           _not_found_field("no_text"),
        "reshenie":      _not_found_field("no_text"),
        "cta":           _not_found_field("no_text"),
        "rol_v_voronke": _not_found_field("no_text"),
        "kryuchok":      _not_found_field("no_text"),
        "struktura":     _not_found_field("no_text"),
        "hook_type":     _not_found_field("no_text"),
        "tokens_used":   0,
    }

    if not text:
        return empty_result

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS_TXT,
            messages=[
                {"role": "system", "content": TEXT_SYSTEM},
                {"role": "user",   "content": text_user_prompt(position, source, text)},
            ],
        )
        raw    = response.choices[0].message.content or ""
        tokens = getattr(response.usage, "total_tokens", 0)
        parsed, err = _parse_json(raw)
        if err:
            return {
                "status":        "parse_error",
                "raw_response":  raw[:300],
                "source":        source,
                "tema":          _not_found_field("parse_error"),
                "bol":           _not_found_field("parse_error"),
                "reshenie":      _not_found_field("parse_error"),
                "cta":           _not_found_field("parse_error"),
                "rol_v_voronke": _not_found_field("parse_error"),
                "kryuchok":      _not_found_field("parse_error"),
                "struktura":     _not_found_field("parse_error"),
                "hook_type":     _not_found_field("parse_error"),
                "tokens_used":   tokens,
            }
        kryuchok = _apply_length_limit(
            parsed.get("kryuchok", _not_found_field("missing_key")), 100
        )
        return {
            "status":        "ok",
            "source":        source,
            "tema":          parsed.get("tema",          _not_found_field("missing_key")),
            "bol":           parsed.get("bol",           _not_found_field("missing_key")),
            "reshenie":      parsed.get("reshenie",      _not_found_field("missing_key")),
            "cta":           parsed.get("cta",           _not_found_field("missing_key")),
            "rol_v_voronke": parsed.get("rol_v_voronke", _not_found_field("missing_key")),
            "kryuchok":      kryuchok,
            "struktura":     parsed.get("struktura",     _not_found_field("missing_key")),
            "hook_type":     parsed.get("hook_type",     _not_found_field("missing_key")),
            "tokens_used":   tokens,
        }
    except Exception as e:
        return {
            "status":        "openai_error",
            "error":         str(e),
            "source":        source,
            "tema":          _not_found_field("openai_error"),
            "bol":           _not_found_field("openai_error"),
            "reshenie":      _not_found_field("openai_error"),
            "cta":           _not_found_field("openai_error"),
            "rol_v_voronke": _not_found_field("openai_error"),
            "kryuchok":      _not_found_field("openai_error"),
            "struktura":     _not_found_field("openai_error"),
            "hook_type":     _not_found_field("openai_error"),
            "tokens_used":   0,
        }


# ---------------------------------------------------------------------------
# Single-reel result builder
# ---------------------------------------------------------------------------

def build_reel_result(reel: dict, vision: dict, text: dict) -> dict:
    _views = reel.get("view_count") or 0
    _likes = reel.get("likes_count") or 0
    _engagement_rate = f"{(_likes / _views * 100):.2f}%" if _views > 0 else None

    return {
        # Identity & metrics — carried from stage5c1
        "position":         reel.get("position"),
        "reel_id":          reel.get("reel_id"),
        "url":              reel.get("url"),
        "view_count":       _views,
        "likes_count":      _likes,
        "is_pinned":        reel.get("is_pinned"),
        "published_at":     reel.get("timestamp"),
        # Computed metrics
        "engagement_rate":  _engagement_rate,
        # Vision fields
        "vision_status":    vision.get("status"),
        "hook":             vision.get("hook"),
        "vizual_format":    vision.get("vizual_format"),
        # Text fields
        "text_status":      text.get("status"),
        "text_source":      text.get("source"),
        "tema":             text.get("tema"),
        "bol":              text.get("bol"),
        "reshenie":         text.get("reshenie"),
        "cta":              text.get("cta"),
        "rol_v_voronke":    text.get("rol_v_voronke"),
        "kryuchok":         text.get("kryuchok"),
        "struktura":        text.get("struktura"),
        "hook_type":        text.get("hook_type"),
        # Diagnostics
        "tokens_vision":    vision.get("tokens_used", 0),
        "tokens_text":      text.get("tokens_used", 0),
        "tokens_total":     (vision.get("tokens_used") or 0) + (text.get("tokens_used") or 0),
    }


# ---------------------------------------------------------------------------
# Input loader
# ---------------------------------------------------------------------------

def load_reels() -> tuple[list, str | None]:
    if not INPUT_PATH.exists():
        return [], f"{INPUT_PATH.relative_to(BASE)} not found — run stage5c1 first"
    try:
        data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"Failed to parse input JSON: {e}"
    reels = data.get("reels", [])
    if not reels:
        return [], "No reels found in stage5c1_reels_index.json"
    return reels, None


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(limit: int = 0):
    print("[DRY-RUN] No OpenAI calls. No files written.\n")

    reels, err = load_reels()
    if err:
        print(f"[ERROR] {err}")
        sys.exit(1)

    if limit:
        reels = reels[:limit]

    print(f"Input:  {INPUT_PATH.relative_to(BASE)}")
    print(f"Output: {OUTPUT_PATH.relative_to(BASE)}")
    print(f"Reels to analyze: {len(reels)}")
    print(f"Model:            {DEFAULT_MODEL}")
    print()

    for reel in reels:
        pos          = reel.get("position", "?")
        display_url  = reel.get("thumbnail_url") or ""
        source, text = _pick_text_source(reel)

        print(f"{'─'*60}")
        print(f"Reel #{pos}  views={reel.get('view_count')}  url={reel.get('url')}")
        print()

        # Vision
        if display_url:
            print(f"  [VISION] thumbnail_url: {display_url[:80]}...")
            print(f"  [VISION] user prompt:   {vision_user_prompt(pos)}")
        else:
            print(f"  [VISION] SKIP — no thumbnail_url")
        print()

        # Text
        if text:
            preview = text[:150].replace("\n", " ")
            print(f"  [TEXT]  source={source}  words={_word_count(text)}")
            print(f"  [TEXT]  preview: {preview}...")
            print(f"  [TEXT]  user prompt (first line): Reel #{pos}. {source.capitalize()}: [text truncated]")
        else:
            print(f"  [TEXT]  SKIP — no transcript and no caption")
        print()

    calls_per_reel = 2
    total_calls    = len(reels) * calls_per_reel
    est_cost       = round(total_calls * 0.005, 3)  # rough gpt-4o estimate
    print(f"{'='*60}")
    print(f"Estimated calls: {total_calls} ({len(reels)} reels × 2 calls each)")
    print(f"Estimated cost:  ~${est_cost} (rough, varies by transcript length)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5C-2: Reels Analyzer (Vision + Text)"
    )
    parser.add_argument("--account", default="vlada_kliuiko",
                        help="Instagram username")
    parser.add_argument("--model",   default=DEFAULT_MODEL,
                        help=f"OpenAI model (default: {DEFAULT_MODEL})")
    parser.add_argument("--limit",   type=int, default=0,
                        help="Analyze only first N reels (0 = all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompts without calling OpenAI")
    args = parser.parse_args()

    if args.dry_run:
        run_dry_run(limit=args.limit)
        return

    # --- Real run ---
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("openai not installed — run: pip install openai")

    client = OpenAI(api_key=api_key)
    model  = args.model

    reels, err = load_reels()
    if err:
        print(f"[ERROR] {err}", file=sys.stderr)
        sys.exit(1)

    if args.limit:
        reels = reels[:args.limit]

    print(f"=== Stage 5C-2: Reels Analyzer ===")
    print(f"Account: @{ACCOUNT}")
    print(f"Model:   {model}")
    print(f"Reels:   {len(reels)}")
    print()

    results         = []
    total_tokens    = 0
    ok_count        = 0
    skipped_count   = 0

    for reel in reels:
        pos = reel.get("position", "?")
        print(f"[{pos}/{len(reels)}] Reel {reel.get('url', '?')}")

        # Pass 1: Vision
        display_url = (reel.get("thumbnail_url") or "").strip()
        if display_url:
            print(f"  Vision → thumbnail present, calling {model}...")
        else:
            print(f"  Vision → SKIP (no thumbnail_url)")
        vision = call_vision(client, reel, model)
        print(f"  Vision status: {vision['status']}  tokens: {vision.get('tokens_used', 0)}")

        # Pass 2: Text
        source, text = _pick_text_source(reel)
        if text:
            print(f"  Text   → source={source}  words={_word_count(text)}, calling {model}...")
        else:
            print(f"  Text   → SKIP (no transcript/caption)")
        text_result = call_text(client, reel, model)
        print(f"  Text   status: {text_result['status']}  tokens: {text_result.get('tokens_used', 0)}")

        result = build_reel_result(reel, vision, text_result)
        results.append(result)
        total_tokens += result["tokens_total"]

        if vision["status"] == "ok" or text_result["status"] == "ok":
            ok_count += 1
        else:
            skipped_count += 1

    output = {
        "account":        ACCOUNT,
        "stage":          STAGE,
        "prompt_version": PROMPT_VERSION,
        "model":          model,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "reels_analyzed": len(reels),
        "reels_ok":       ok_count,
        "reels_skipped":  skipped_count,
        "total_tokens":   total_tokens,
        "reels":          results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    # Summary
    print()
    print("=== Summary ===")
    for r in results:
        pos     = r.get("position", "?")
        views   = r.get("view_count") or 0
        hook    = (r.get("hook") or {}).get("value", "—")[:60]
        fmt     = (r.get("vizual_format") or {}).get("value", "—")
        tema    = (r.get("tema") or {}).get("value", "—")[:60]
        funnel  = (r.get("rol_v_voronke") or {}).get("value", "—")
        tokens  = r.get("tokens_total", 0)
        print(f"  #{pos:2}  {views:>8} views  [{fmt}]  tok={tokens}")
        print(f"       hook:   {hook}")
        print(f"       tema:   {tema}")
        print(f"       воронка: {funnel}")
        print()

    print(f"  Total tokens: {total_tokens}")
    est_cost = round(total_tokens * 0.000005, 4)
    print(f"  Est. cost:    ~${est_cost}")


if __name__ == "__main__":
    main()
