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
import base64
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE     = Path(__file__).parent.parent
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT  = _args.account
RAW_DIR  = BASE / "data" / ACCOUNT / "raw"
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"

INDEX_RAW_PATH = RAW_DIR / "stage5b1_highlights_index_raw.json"
OUTPUT_PATH    = NORM_DIR / "stage5b2v_highlights_visual.json"
STAGE          = "stage5b2v"
PROMPT_VERSION = "v2"
DEFAULT_MODEL  = "gpt-4o"

STORIES_PER_HIGHLIGHT    = 5   # max stories to select per highlight
MIN_DOWNLOADABLE_IMAGES  = 2   # skip Vision if fewer images downloaded successfully
IMAGE_DETAIL             = "low"
IMAGE_MAX_SIDE           = 512  # resize long side to this before base64
MAX_TOKENS             = 500
MAX_TOKENS_TARGETED    = 200   # cover + CTA targeted prompts

# IDs requested for analysis
# Leave empty to process all highlights from stage5b1 index (default for pipeline).
# Populate to restrict to specific IDs for one-off runs.
TARGET_HIGHLIGHT_IDS: list[str] = []


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
  Как подан контент. Выбери одно из списка:
  скрин / видео / репост сторис / сторис ученика / кейс / результат / переписка / продажа через отзыв
  Агент выбирает из этого списка — не пишет общее слово типа "отзыв" или "контент".
  Если не подходит ни одно — предложи своё на русском.

cta (Куда ведет CTA):
  Ищи CTA в ПОСЛЕДНИХ кадрах highlight — там чаще всего находится призыв к действию.
  Фиксируй CTA даже если highlight выглядит как "просто доверие" или "просто отзывы".
  Если на кадрах виден явный призыв к действию — куда он ведет:
  директ / бот / сайт / курс / лид-магнит
  Если CTA не виден нигде — data_status: "not_found", value: "".

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
    """Return (stories_list, error_or_None) from stage5b2 raw file."""
    path = RAW_DIR / f"stage5b2_stories_{highlight_id}_raw.json"
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
    """Pick up to max_n image URLs from stories.

    Checks multiple field names to handle different Apify actor schemas:
      - imageUrl   (singhera07 actor)
      - mediaUrl   (automation-lab actor)
      - thumbnailUrl (automation-lab actor fallback)
    """
    urls = []
    for item in stories:
        url = (item.get("imageUrl") or
               item.get("mediaUrl") or
               item.get("thumbnailUrl") or "")
        if url:
            urls.append(url)
        if len(urls) >= max_n:
            break
    return urls


# ---------------------------------------------------------------------------
# Image download + base64 encoding
# ---------------------------------------------------------------------------

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36"
    )
}

STALE_PATH = NORM_DIR / "stale_highlights.json"


def check_url_alive(url: str, timeout: int = 3) -> bool:
    """HEAD-request the URL; return True only on HTTP 200."""
    import requests
    try:
        resp = requests.head(
            url, timeout=timeout,
            headers=_DOWNLOAD_HEADERS, allow_redirects=True,
        )
        return resp.status_code == 200
    except Exception:
        return False


def download_as_base64(url: str, pil_image_cls, timeout: int = 10) -> str | None:
    """Download image URL, resize to IMAGE_MAX_SIDE, return base64 data URI or None."""
    import requests  # imported lazily; only called in non-dry-run mode

    try:
        resp = requests.get(url, timeout=timeout, headers=_DOWNLOAD_HEADERS)
    except Exception as e:
        print(f"[WARN] Failed to download image (network error): {url[:80]} — {e}")
        return None

    if resp.status_code != 200:
        print(f"[WARN] Failed to download image (status {resp.status_code}): {url[:80]}")
        return None

    content_type = resp.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        print(f"[WARN] Non-image content-type for {url[:80]}: {content_type}")
        return None

    try:
        img = pil_image_cls.open(io.BytesIO(resp.content))
        img = img.convert("RGB")

        w, h   = img.size
        factor = IMAGE_MAX_SIDE / max(w, h)
        if factor < 1.0:
            img = img.resize((int(w * factor), int(h * factor)))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        print(f"[WARN] Failed to process image {url[:80]}: {e}")
        return None


def prepare_images(candidate_urls: list[str],
                   pil_image_cls) -> tuple[list[str], list[str]]:
    """Download + encode all candidate URLs.

    Returns (original_urls, data_uris) — parallel lists with only successful downloads.
    """
    original_urls: list[str] = []
    data_uris:     list[str] = []
    for url in candidate_urls:
        data_uri = download_as_base64(url, pil_image_cls)
        if data_uri:
            original_urls.append(url)
            data_uris.append(data_uri)
    return original_urls, data_uris


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
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1] if clean.count("```") >= 2 else clean
                if clean.startswith("json"):
                    clean = clean[4:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            parsed = json.loads(clean)
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
# Targeted cover + CTA prompts
# ---------------------------------------------------------------------------

def cta_frame_count(n_images: int) -> int:
    """How many trailing frames to send to the CTA prompt."""
    if n_images < 3:
        return 1
    elif n_images <= 5:
        return 2
    else:
        return 3


def call_cover_vision(client, data_uri: str, model: str) -> dict:
    """Single-frame cover analysis. Returns {status, text, tokens_used}."""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_uri, "detail": IMAGE_DETAIL}},
                    {"type": "text",
                     "text": "Это обложка хайлайта. Что является хуком — заголовок, визуал, текст который цепляет взгляд первым?"},
                ],
            }],
            max_tokens=MAX_TOKENS_TARGETED,
            temperature=0.0,
        )
        return {
            "status":      "ok",
            "text":        (response.choices[0].message.content or "").strip(),
            "tokens_used": response.usage.total_tokens,
        }
    except Exception as e:
        return {"status": "error", "text": "", "tokens_used": 0, "error": str(e)}


def call_cta_vision(client, cta_uris: list, model: str) -> dict:
    """Last-N frames CTA analysis. Returns {status, text, tokens_used}."""
    image_content = [
        {"type": "image_url", "image_url": {"url": u, "detail": IMAGE_DETAIL}}
        for u in cta_uris
    ]
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    *image_content,
                    {"type": "text",
                     "text": "Это финальные кадры хайлайта. Найди CTA — призыв написать в директ, перейти по ссылке, записаться, купить. Если есть — куда ведёт и дословная формулировка?"},
                ],
            }],
            max_tokens=MAX_TOKENS_TARGETED,
            temperature=0.0,
        )
        return {
            "status":      "ok",
            "text":        (response.choices[0].message.content or "").strip(),
            "tokens_used": response.usage.total_tokens,
            "frames_used": len(cta_uris),
        }
    except Exception as e:
        return {"status": "error", "text": "", "tokens_used": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

_FIELD_KEYS = ("tema", "zadacha", "chto_vnutri", "mekhanika", "cta")


def build_highlight_result(highlight_id: str, meta: dict, stories: list,
                           image_urls: list[str], vision_result: dict,
                           cover_result: dict = None,
                           cta_result: dict = None,
                           skipped: bool = False, skip_reason: str = "",
                           stale_urls: bool = False) -> dict:
    base = {
        "highlight_id":     highlight_id,
        "title":            meta.get("title", ""),
        "position":         meta.get("position"),
        "stories_total":    len(stories),
        "stories_selected": len(image_urls),
        "imageUrls_used":   image_urls,
        "skipped":          skipped,
    }
    if stale_urls:
        base["stale_urls"] = True
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

    tokens_general = vision_result.get("tokens_used") or 0
    tokens_cover   = (cover_result or {}).get("tokens_used") or 0
    tokens_cta     = (cta_result or {}).get("tokens_used") or 0

    base["fields"]      = fields
    base["tokens_used"] = tokens_general + tokens_cover + tokens_cta

    if cover_result is not None:
        base["cover_hook"] = {
            "status": cover_result.get("status"),
            "text":   cover_result.get("text", ""),
        }
    if cta_result is not None:
        base["cta_targeted"] = {
            "status":      cta_result.get("status"),
            "text":        cta_result.get("text", ""),
            "frames_used": cta_result.get("frames_used", 0),
        }

    return base


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(highlight_ids: list[str], hl_meta: dict, dry_highlight_id: str | None = None):
    print("[DRY-RUN] No downloads. No resize. OpenAI not called. No files will be written.\n")

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
        print(f"  Images selected (would be downloaded + encoded): {len(image_urls)}")
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
    parser.add_argument(
        "--account", default="vlada_kliuiko",
        help="Instagram account to process",
    )
    args = parser.parse_args()

    # Load index (non-blocking — falls back to ID as title/position if missing)
    index_items, err = load_index()
    if err:
        prefix = "[DRY-RUN][WARN]" if args.dry_run else "[WARN]"
        print(f"{prefix} {err}")
        print(f"{prefix} Using target IDs without title/position.\n")
        hl_meta = {}
    else:
        hl_meta = build_highlight_meta(index_items)

    if args.highlight_id:
        target_ids = [args.highlight_id]
    elif TARGET_HIGHLIGHT_IDS:
        target_ids = TARGET_HIGHLIGHT_IDS
    else:
        target_ids = list(hl_meta.keys())

    if args.dry_run:
        run_dry_run(target_ids, hl_meta, dry_highlight_id=args.highlight_id)
        return

    # Pillow check — only in non-dry-run mode
    try:
        from PIL import Image as PILImage
    except ImportError:
        print("[ERROR] Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

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

    results      = []
    stale_ids_detected: list[str] = []

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

        # Staleness check: HEAD request on first candidate URL (timeout 3 s)
        if candidate_urls:
            alive = check_url_alive(candidate_urls[0])
            if not alive:
                print(f"  [WARN] Stale URL (HEAD 403/error/timeout): {candidate_urls[0][:80]}")
                stale_ids_detected.append(hid)
                results.append(build_highlight_result(
                    hid, meta, stories, candidate_urls,
                    vision_result={},
                    skipped=True,
                    skip_reason="stale_urls",
                    stale_urls=True,
                ))
                continue

        print("  Downloading and encoding images...")
        original_urls, data_uris = prepare_images(candidate_urls, PILImage)
        print(f"  Successfully encoded: {len(data_uris)}/{len(candidate_urls)}")

        if len(data_uris) < MIN_DOWNLOADABLE_IMAGES:
            print(
                f"  [WARN] Highlight {hid}: insufficient downloadable images, skipping Vision call"
            )
            results.append(build_highlight_result(
                hid, meta, stories, candidate_urls,
                vision_result={},
                skipped=True,
                skip_reason="insufficient_downloadable_images",
            ))
            continue

        print(f"  Calling Vision API with {len(data_uris)} base64 images...")
        vision_result = call_vision(client, hid, title, data_uris, model=args.model)

        # Cover (first frame) → hook analysis
        cover_result = None
        if data_uris:
            print(f"  Calling cover prompt (1 frame)...")
            cover_result = call_cover_vision(client, data_uris[0], model=args.model)

        # CTA (last N frames) → CTA analysis
        cta_result = None
        if data_uris:
            n_cta = cta_frame_count(len(data_uris))
            cta_uris = data_uris[-n_cta:]
            print(f"  Calling CTA prompt ({n_cta} frame(s))...")
            cta_result = call_cta_vision(client, cta_uris, model=args.model)

        result = build_highlight_result(
            hid, meta, stories, original_urls, vision_result,
            cover_result=cover_result,
            cta_result=cta_result,
        )
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

    # Save or clear stale_highlights.json
    if stale_ids_detected:
        print(f"\n[WARN] Stale URLs detected in {len(stale_ids_detected)} highlight(s):")
        for r in results:
            if r.get("stale_urls"):
                print(f"  - {r.get('title', r['highlight_id'])} "
                      f"(pos {r.get('position', '?')}, id={r['highlight_id']})")
        STALE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STALE_PATH.write_text(json.dumps({
            "account":             ACCOUNT,
            "stale_highlight_ids": stale_ids_detected,
            "generated_at":        datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Saved: {STALE_PATH.relative_to(BASE)}")
        print(f"  Re-collect: python scripts/stage5b2_run_local.py "
              f"--account {ACCOUNT} --refresh-stale")
    elif STALE_PATH.exists():
        STALE_PATH.unlink()
        print(f"[OK] {STALE_PATH.relative_to(BASE)} cleared (no stale URLs)")

    print("\n=== Summary ===")
    for r in results:
        if r.get("stale_urls"):
            status = "STALE"
        elif r.get("skipped"):
            status = "SKIPPED"
        elif r.get("parse_error"):
            status = "PARSE_ERROR"
        else:
            status = "OK"
        print(f"  [{status}] {r.get('title', r['highlight_id'])}")


if __name__ == "__main__":
    main()
