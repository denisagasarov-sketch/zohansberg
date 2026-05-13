"""Stage 5B-2V: Highlights Visual Analyzer.

Reads stories from data/raw/stage5b0_highlight_{id}_raw.json.
Reads highlight index from data/raw/stage5b1_highlights_index_raw.json.
Sends up to 5 available imageUrls per highlight to OpenAI Vision (gpt-4o).
Extracts 5 semantic fields per highlight.

Usage:
    python3 scripts/stage5b2v_highlights_visual_analyzer.py --dry-run
    python3 scripts/stage5b2v_highlights_visual_analyzer.py --dry-run --highlight-id 17874797856565339
    python3 scripts/stage5b2v_highlights_visual_analyzer.py --highlight-id 17874797856565339
    python3 scripts/stage5b2v_highlights_visual_analyzer.py
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE     = Path(__file__).parent.parent
RAW_DIR  = BASE / "data" / "raw"
NORM_DIR = BASE / "data" / "normalized"

INDEX_RAW_PATH = RAW_DIR / "stage5b1_highlights_index_raw.json"
OUTPUT_PATH    = NORM_DIR / "stage5b2v_highlights_visual.json"

ACCOUNT        = "vlada_kliuiko"
STAGE          = "stage5b2v"
PROMPT_VERSION = "v1"
DEFAULT_MODEL  = "gpt-4o"

STORIES_PER_HIGHLIGHT  = 5   # max stories to select per highlight
MIN_AVAILABLE_IMAGES   = 2   # skip Vision if fewer available after HEAD checks
IMAGE_DETAIL           = "low"
MAX_TOKENS             = 500

# IDs requested for analysis
TARGET_HIGHLIGHT_IDS = [
    "17874797856565339",  # отзывы курс (57 stories)
    "18110898391654002",  # GEO (17 stories)
]


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик Instagram-контента. Тебе показывают несколько кадров из одного highlight Instagram-аккаунта.
Твоя задача — проанализировать все кадры вместе и извлечь 5 полей. Отвечай строго в JSON, без текста вне JSON.

ПРАВИЛА:
1. Отвечай только на русском языке.
2. Не додумывай — только то, что явно видно на кадрах.
3. Если поле не определяется по кадрам — data_status: "not_found", value: "".
4. Добавляй notes с кратким объяснением (1 предложение).

ПОЛЯ:

tema (Тема highlight):
  Что это за контент. Выбери одно:
  отзывы / обучение / кейсы / знакомство / продукт / разборы / инструменты / гео-продвижение
  Если не подходит ни одно — предложи своё на русском.

zadacha (Задача highlight):
  Зачем этот highlight в профиле. Выбери одно:
  доверие / прогрев / лидогенерация / социальное доказательство / обучение
  Если не подходит — предложи своё на русском.

chto_vnutri (Что внутри кратко):
  Одно полноценное предложение на русском — что показывают в этих кадрах.
  НЕ список тегов. НЕ перечисление через запятую.
  Пример OK: "Студенты курса делятся результатами и благодарят автора."
  Пример НЕЛЬЗЯ: "отзывы, маркетинг, успех, клиент"

mekhanika (Механика подачи):
  Как подан контент. Выбери одно:
  кейс / отзыв / обучение / чек-лист / разбор ошибки / обзор инструмента / до-после
  Если не подходит — предложи своё на русском.

cta (Куда ведет CTA):
  Если на кадрах виден явный призыв к действию — куда он ведет:
  директ / бот / сайт / курс / лид-магнит
  Если CTA не виден — data_status: "not_found", value: "".

ФОРМАТ ОТВЕТА (строго JSON, никакого текста вне JSON):
{
  "tema":        {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "zadacha":     {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "chto_vnutri": {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "mekhanika":   {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "cta":         {"value": "...", "data_status": "ok|not_found", "notes": "..."}
}\
"""


def build_user_prompt(title: str, n: int) -> str:
    return (
        f"Highlight: {title}\n"
        f"Проанализируй эти {n} кадров из highlight и извлеки 5 полей строго по инструкции.\n"
        "Отвечай только JSON."
    )


# ---------------------------------------------------------------------------
# Index loader
# ---------------------------------------------------------------------------

def load_index() -> tuple[list, str | None]:
    """Return (highlights_list, error_or_None).

    Tries multiple formats:
      - list of items directly
      - {"highlights": [...]} wrapper
      - {"items": [...]} wrapper
    Each item expected to have 'id' and 'title'.
    """
    if not INDEX_RAW_PATH.exists():
        return [], f"{INDEX_RAW_PATH.relative_to(BASE)} not found"
    try:
        raw = json.loads(INDEX_RAW_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"Failed to parse {INDEX_RAW_PATH.name}: {e}"

    if isinstance(raw, list):
        return raw, None
    if isinstance(raw, dict):
        for key in ("highlights", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key], None
    return [], f"Unexpected format in {INDEX_RAW_PATH.name} — expected list or dict with 'highlights' key"


def build_highlight_meta(index_items: list) -> dict[str, dict]:
    """Return {highlight_id: {title, position}} from index."""
    meta = {}
    for pos, item in enumerate(index_items, start=1):
        raw_id = item.get("id")
        if raw_id is None:
            continue
        hid = str(raw_id)
        # title may be a plain string or a field-wrapper dict
        title_raw = item.get("title", "")
        if isinstance(title_raw, dict):
            title = title_raw.get("value") or ""
        else:
            title = str(title_raw) if title_raw else ""
        meta[hid] = {"title": title, "position": pos}
    return meta


# ---------------------------------------------------------------------------
# Stories loader
# ---------------------------------------------------------------------------

def load_stories(highlight_id: str) -> tuple[list, str | None]:
    """Return (stories_list, error_or_None) from stage5b0 raw file."""
    path = RAW_DIR / f"stage5b0_highlight_{highlight_id}_raw.json"
    if not path.exists():
        return [], f"{path.relative_to(BASE)} not found"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return [], f"Failed to parse {path.name}: {e}"

    if isinstance(raw, list):
        return raw, None
    if isinstance(raw, dict):
        for key in ("stories", "items", "data"):
            if isinstance(raw.get(key), list):
                return raw[key], None
    return [], f"Unexpected format in {path.name}"


def select_image_urls(stories: list, max_n: int = STORIES_PER_HIGHLIGHT) -> list[str]:
    """Pick up to max_n imageUrls from stories, skipping items without one."""
    urls = []
    for item in stories:
        url = item.get("imageUrl") or ""
        if url:
            urls.append(url)
        if len(urls) >= max_n:
            break
    return urls


# ---------------------------------------------------------------------------
# URL availability check
# ---------------------------------------------------------------------------

def check_url_available(url: str, timeout: int = 8) -> tuple[bool, int | None]:
    """HEAD request to verify URL. Returns (ok, status_code)."""
    try:
        req = Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req, timeout=timeout) as resp:
            return resp.status == 200, resp.status
    except URLError as e:
        return False, None
    except Exception:
        return False, None


def filter_available_urls(urls: list[str]) -> list[str]:
    """Filter URLs to those returning HTTP 200. Logs unavailable ones."""
    available = []
    for url in urls:
        ok, code = check_url_available(url)
        if ok:
            available.append(url)
        else:
            status_str = str(code) if code is not None else "no response"
            print(f"[WARN] imageUrl unavailable (status {status_str}): {url[:80]}")
    return available


# ---------------------------------------------------------------------------
# OpenAI Vision call
# ---------------------------------------------------------------------------

def call_vision(client, highlight_id: str, title: str,
                image_urls: list[str], model: str) -> dict:
    """Call OpenAI Vision API. Returns result dict."""
    user_prompt = build_user_prompt(title, len(image_urls))

    image_content = [
        {"type": "image_url", "image_url": {"url": u, "detail": IMAGE_DETAIL}}
        for u in image_urls
    ]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
                *image_content,
            ],
        },
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=MAX_TOKENS,
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        try:
            parsed = json.loads(raw)
            return {
                "status": "ok",
                "fields": parsed,
                "tokens_used": response.usage.total_tokens,
            }
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON for highlight {highlight_id}: {e}")
            return {
                "status": "parse_error",
                "parse_error": True,
                "raw_response": raw[:300],
            }
    except Exception as e:
        print(f"[ERROR] OpenAI Vision call failed for highlight {highlight_id}: {e}")
        return {"status": "openai_error", "error": str(e)}


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

_FIELD_KEYS = ("tema", "zadacha", "chto_vnutri", "mekhanika", "cta")


def build_highlight_result(highlight_id: str, meta: dict, stories: list,
                           image_urls: list[str], vision_result: dict,
                           skipped: bool = False, skip_reason: str = "") -> dict:
    base = {
        "highlight_id":     highlight_id,
        "title":            meta.get("title", ""),
        "position":         meta.get("position"),
        "stories_total":    len(stories),
        "stories_selected": len(image_urls),
        "imageUrls_used":   image_urls,
        "skipped":          skipped,
    }
    if skipped:
        base["skip_reason"] = skip_reason
        return base

    if vision_result.get("status") == "parse_error":
        base["parse_error"]   = True
        base["raw_response"]  = vision_result.get("raw_response", "")
        base["tokens_used"]   = None
        return base

    if vision_result.get("status") == "openai_error":
        base["openai_error"] = vision_result.get("error", "")
        base["tokens_used"]  = None
        return base

    fields_raw = vision_result.get("fields") or {}
    fields = {}
    for key in _FIELD_KEYS:
        raw = fields_raw.get(key) or {}
        if isinstance(raw, dict):
            fields[key] = {
                "value":       raw.get("value", ""),
                "data_status": raw.get("data_status", "not_found"),
                "notes":       raw.get("notes", ""),
            }
        else:
            fields[key] = {"value": str(raw), "data_status": "ok", "notes": ""}

    base["fields"]      = fields
    base["tokens_used"] = vision_result.get("tokens_used")
    return base


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(highlight_ids: list[str], hl_meta: dict, dry_highlight_id: str | None = None):
    print("[DRY-RUN] No HEAD checks. OpenAI not called. No files will be written.\n")

    targets = [dry_highlight_id] if dry_highlight_id else highlight_ids
    for hid in targets:
        meta     = hl_meta.get(hid) or {}
        title    = meta.get("title") or f"highlight_{hid}"
        position = meta.get("position", "?")

        stories, err = load_stories(hid)
        if err:
            print(f"[WARN] {err}")
            stories = []

        image_urls = select_image_urls(stories)
        stories_total = len(stories)

        print("=" * 60)
        print(f"HIGHLIGHT: {title}  (id={hid})")
        print(f"  Position:       {position}")
        print(f"  Stories total:  {stories_total}")
        print(f"  Images selected (would be sent, before HEAD checks): {len(image_urls)}")
        for i, url in enumerate(image_urls, 1):
            print(f"    [{i}] {url[:120]}")
        print()

    print("=" * 60)
    print("SYSTEM PROMPT (будет отправлен в OpenAI Vision):")
    print("=" * 60)
    print(SYSTEM_PROMPT)
    print()

    # Show user prompt example for first target
    first_id = targets[0] if targets else None
    if first_id:
        first_meta   = hl_meta.get(first_id) or {}
        first_title  = first_meta.get("title") or f"highlight_{first_id}"
        first_stories, _ = load_stories(first_id)
        first_urls   = select_image_urls(first_stories)
        example_n    = len(first_urls) if first_urls else STORIES_PER_HIGHLIGHT
        print("=" * 60)
        print(f"USER PROMPT EXAMPLE (для highlight '{first_title}'):")
        print("=" * 60)
        print(build_user_prompt(first_title, example_n))
        print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"detail:         {IMAGE_DETAIL}")
    print(f"max_tokens:     {MAX_TOKENS}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5B-2V: Highlights Visual Analyzer (OpenAI Vision)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show highlights info and prompts; no HEAD checks, no Vision call, no file write",
    )
    parser.add_argument(
        "--highlight-id", metavar="ID",
        help="Analyze only this highlight ID (for testing before full run)",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    # Load index
    index_items, err = load_index()
    if err:
        if args.dry_run:
            print(f"[DRY-RUN][WARN] {err}")
            print("[DRY-RUN] Index unavailable — using target IDs without title/position.\n")
            hl_meta = {}
        else:
            print(f"[ERROR] {err}")
            sys.exit(1)
    else:
        hl_meta = build_highlight_meta(index_items)

    target_ids = TARGET_HIGHLIGHT_IDS
    if args.highlight_id:
        target_ids = [args.highlight_id]

    if args.dry_run:
        run_dry_run(target_ids, hl_meta, dry_highlight_id=args.highlight_id)
        return

    # Load API key
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=BASE / ".env", override=True)
    except ImportError:
        pass

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("[ERROR] OPENAI_API_KEY not set. Add it to .env or environment.")
        sys.exit(1)
    if not api_key.startswith("sk-"):
        print("[ERROR] OPENAI_API_KEY looks invalid (must start with sk-).")
        sys.exit(1)

    try:
        from openai import OpenAI
    except ImportError:
        raise SystemExit("openai not installed — run: pip install openai")

    client = OpenAI(api_key=api_key)

    results = []
    for hid in target_ids:
        meta  = hl_meta.get(hid) or {"title": f"highlight_{hid}", "position": None}
        title = meta.get("title") or f"highlight_{hid}"
        print(f"\nProcessing highlight: {title}  (id={hid})")

        stories, err = load_stories(hid)
        if err:
            print(f"  [WARN] {err} — skipping")
            results.append({
                "highlight_id": hid, "title": title,
                "position": meta.get("position"),
                "skipped": True, "skip_reason": err,
            })
            continue

        candidate_urls = select_image_urls(stories)
        print(f"  Stories total: {len(stories)}, candidate images: {len(candidate_urls)}")

        print("  Checking URL availability...")
        available_urls = filter_available_urls(candidate_urls)
        print(f"  Available images: {len(available_urls)}")

        if len(available_urls) < MIN_AVAILABLE_IMAGES:
            print(f"  [SKIP] Only {len(available_urls)} available — need at least {MIN_AVAILABLE_IMAGES}")
            results.append(build_highlight_result(
                hid, meta, stories, candidate_urls,
                vision_result={},
                skipped=True,
                skip_reason="insufficient_available_images",
            ))
            continue

        print(f"  Calling Vision API with {len(available_urls)} images...")
        vision_result = call_vision(client, hid, title, available_urls, model=args.model)
        result = build_highlight_result(hid, meta, stories, available_urls, vision_result)
        results.append(result)

        tok = result.get("tokens_used")
        if tok:
            print(f"  Tokens used: {tok}")

    output = {
        "account":              ACCOUNT,
        "stage":                STAGE,
        "prompt_version":       PROMPT_VERSION,
        "model":                args.model,
        "generated_at":         datetime.now(timezone.utc).isoformat(),
        "analyzed_highlights":  results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    print("\n=== Summary ===")
    for r in results:
        status = "SKIPPED" if r.get("skipped") else ("PARSE_ERROR" if r.get("parse_error") else "OK")
        print(f"  [{status}] {r.get('title', r['highlight_id'])}")


if __name__ == "__main__":
    main()
