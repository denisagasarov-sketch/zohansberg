"""Stage 5A-2G: Landing Page Analyzer v2.

Two-pass analysis via Playwright scroll + OpenAI:
  Pass 1 (Vision, gpt-4o): up to 3 selected screenshots → visual structure,
      main heading (largest text), CTA buttons, blocks in order.
  Pass 2 (Text,   gpt-4o): full page inner_text → all numbers/social proof,
      audience pains, arguments, block structure detail.
  Merge: Vision wins on visual-structure fields; Text wins on extraction fields;
         shared fields prefer whichever has data_status=ok.

Usage:
    python3 scripts/stage5a2g_landing_analyzer.py --dry-run
    python3 scripts/stage5a2g_landing_analyzer.py
    python3 scripts/stage5a2g_landing_analyzer.py --url "https://example.com"
"""

import argparse
import base64
import hashlib
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
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"

STAGE5A2F_PATH = NORM_DIR / "stage5a2f_link_destination.json"
OUTPUT_PATH    = NORM_DIR / "stage5a2g_landing_analysis.json"
SCREENSHOT_DIR = BASE / "output" / ACCOUNT / "stage5a2g_screenshots"

STAGE             = "stage5a2g"
PROMPT_VERSION    = "v2"
DEFAULT_MODEL     = "gpt-4o"
MAX_SCREENSHOTS   = 5
MAX_TEXT_CHARS    = 15000
MAX_TOKENS_VISION = 1200
MAX_TOKENS_TEXT   = 1500

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_ALL_FIELDS = [
    "chto_prodayut",
    "pervye_3_ekrana",
    "glavnyy_zagolovok",
    "podzagolovok",
    "dlya_kogo",
    "obeshchanie_rezultata",
    "glavnyy_cta",
    "sots_dokazatelstva",
    "boli",
    "argumenty",
    "bloki_dalshe",
]

# Vision pass: authoritative on visual/positional fields
_VISION_AUTHORITATIVE = frozenset([
    "pervye_3_ekrana",
    "glavnyy_zagolovok",
    "podzagolovok",
    "glavnyy_cta",
])

# Text pass: authoritative on extraction fields
_TEXT_AUTHORITATIVE = frozenset([
    "sots_dokazatelstva",
    "boli",
    "argumenty",
])

# Shared fields (not in either authoritative set): prefer ok status, text wins tie
_SHARED_FIELDS = frozenset(_ALL_FIELDS) - _VISION_AUTHORITATIVE - _TEXT_AUTHORITATIVE


# ---------------------------------------------------------------------------
# Input loader
# ---------------------------------------------------------------------------

def load_input() -> tuple[str, str, str | None]:
    """Return (url_clean, destination_type, error_or_None)."""
    if not STAGE5A2F_PATH.exists():
        return "", "неизвестно", f"{STAGE5A2F_PATH.relative_to(BASE)} not found"
    try:
        data = json.loads(STAGE5A2F_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return "", "неизвестно", f"Failed to parse stage5a2f_link_destination.json: {e}"

    url   = data.get("url_clean") or data.get("url_input") or ""
    dtype = (data.get("result") or {}).get("destination_type") or "неизвестно"
    if not url:
        return "", dtype, "url_clean is empty in stage5a2f_link_destination.json"
    return url, dtype, None


# ---------------------------------------------------------------------------
# Playwright: scroll + multi-screenshot + text extraction
# ---------------------------------------------------------------------------

def _screenshot_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def fetch_with_playwright(url: str) -> dict:
    """
    Fetch page via Playwright headless Chromium.
    Scrolls one viewport at a time, takes screenshot at each position.
    Stops when: MAX_SCREENSHOTS reached, hash unchanged, or scroll stuck.
    Returns content dict with screenshots list and full_text.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "fetch_success": False,
            "fetch_error":   "playwright not installed — run: pip install playwright && playwright install chromium",
            "screenshots":   [],
            "full_text":     "",
            "text_length":   0,
            "is_spa":        False,
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()
            page.set_default_timeout(30000)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            screenshots = []
            prev_hash   = None

            for i in range(MAX_SCREENSHOTS):
                path = SCREENSHOT_DIR / f"screen_{i + 1}.png"
                page.screenshot(path=str(path), full_page=False)

                h = _screenshot_hash(path)
                if h == prev_hash:
                    path.unlink(missing_ok=True)
                    print(f"  [scroll] Screen {i + 1}: identical to previous — stopping")
                    break

                screenshots.append(path)
                prev_hash = h
                print(f"  [scroll] Screen {i + 1} saved: {path.name}")

                if i + 1 == MAX_SCREENSHOTS:
                    break

                scroll_before = page.evaluate("window.scrollY")
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    page.wait_for_timeout(800)

                scroll_after = page.evaluate("window.scrollY")
                if scroll_after == scroll_before:
                    print(f"  [scroll] Scroll {i + 1}: no progress — stopping")
                    break

            # Extract text after scrolling (inner_text is position-independent)
            full_text = page.inner_text("body")[:MAX_TEXT_CHARS]
            is_spa    = len(full_text) < 200
            if is_spa:
                print("  [WARN] Page text < 200 chars — SPA likely; Vision-only mode")

            browser.close()

        return {
            "fetch_success": True,
            "screenshots":   screenshots,
            "full_text":     full_text,
            "text_length":   len(full_text),
            "is_spa":        is_spa,
        }

    except Exception as e:
        print(f"[ERROR] Playwright fetch failed: {e}")
        return {
            "fetch_success": False,
            "fetch_error":   str(e),
            "screenshots":   [],
            "full_text":     "",
            "text_length":   0,
            "is_spa":        False,
        }


# ---------------------------------------------------------------------------
# Screenshot selection + encoding
# ---------------------------------------------------------------------------

def _select_screenshots(screenshots: list[Path]) -> list[Path]:
    """Return up to 3 screenshots: first, middle, last (deduplicated)."""
    n = len(screenshots)
    if n == 0:
        return []
    if n <= 3:
        return list(screenshots)
    candidates = [screenshots[0], screenshots[n // 2], screenshots[-1]]
    seen, result = set(), []
    for p in candidates:
        if p not in seen:
            result.append(p)
            seen.add(p)
    return result


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_VISION = """\
Ты — аналитик маркетинговых лендингов. Перед тобой скриншоты лендинга в порядке прокрутки.
Анализируй ВИЗУАЛЬНУЮ структуру: что ты ВИДИШЬ — размер текста, расположение элементов, кнопки.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

chto_prodayut: Что продают — из заголовка, названия, CTA.
pervye_3_ekrana: Что видит пользователь в первых 3 экранах — перечисли элементы по порядку.
glavnyy_zagolovok: ТОЧНАЯ ЦИТАТА самого крупного текста на первом экране (hero h1). Дословно, не пересказывай.
podzagolovok: Текст сразу под главным заголовком — дословно.
dlya_kogo: Явное указание аудитории. Если не названа явно — пиши "аудитория не названа".
obeshchanie_rezultata: Что конкретно обещают. Формат: "Core Job: ...; Big Job: ...".
glavnyy_cta: Точный текст самой заметной кнопки или призыва к действию.
bloki_dalshe: Все видимые блоки по порядку. Формат: "1. Название — зачем; 2. Название — зачем; ..."

ПРАВИЛА:
1. Только то что ВИДНО на скриншотах. Не додумывай.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.

ФОРМАТ (строго JSON):
{
  "chto_prodayut":         {"value": "...", "data_status": "ok|not_found"},
  "pervye_3_ekrana":       {"value": "...", "data_status": "ok|not_found"},
  "glavnyy_zagolovok":     {"value": "...", "data_status": "ok|not_found"},
  "podzagolovok":          {"value": "...", "data_status": "ok|not_found"},
  "dlya_kogo":             {"value": "...", "data_status": "ok|not_found"},
  "obeshchanie_rezultata": {"value": "...", "data_status": "ok|not_found"},
  "glavnyy_cta":           {"value": "...", "data_status": "ok|not_found"},
  "bloki_dalshe":          {"value": "...", "data_status": "ok|not_found"}
}"""

SYSTEM_TEXT = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Извлекай из ТЕКСТА: все цифры, все перечисления, все упоминания болей и аргументов.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

chto_prodayut: Что продают.
dlya_kogo: Явное указание аудитории. Если не названа — "аудитория не названа".
obeshchanie_rezultata: Обещание результата. Формат: "Core Job: ...; Big Job: ...".
sots_dokazatelstva: ВСЕ социальные доказательства — любые цифры (N клиентов, N лет, N% результат),
  отзывы, кейсы, логотипы, сертификаты. Перечисли через «; ». Не пропускай ни одну цифру.
  Если нет ни одного — пустая строка.
boli: Боли и проблемы аудитории которые упоминает лендинг. Перечисли через «; ».
argumenty: Аргументы в пользу продукта (почему выбрать именно их). Перечисли через «; ».
bloki_dalshe: Все смысловые блоки страницы по порядку.
  Формат: "1. Блок — зачем; 2. Блок — зачем; ..."

ПРАВИЛА:
1. Только то что явно есть в тексте.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.

ФОРМАТ (строго JSON):
{
  "chto_prodayut":         {"value": "...", "data_status": "ok|not_found"},
  "dlya_kogo":             {"value": "...", "data_status": "ok|not_found"},
  "obeshchanie_rezultata": {"value": "...", "data_status": "ok|not_found"},
  "sots_dokazatelstva":    {"value": "...", "data_status": "ok|not_found"},
  "boli":                  {"value": "...", "data_status": "ok|not_found"},
  "argumenty":             {"value": "...", "data_status": "ok|not_found"},
  "bloki_dalshe":          {"value": "...", "data_status": "ok|not_found"}
}"""


def _user_prompt_vision(url: str, destination_type: str, n_screenshots: int) -> str:
    return (
        f"URL: {url}\n"
        f"Destination type: {destination_type}\n"
        f"Скриншоты: {n_screenshots} шт. в порядке прокрутки.\n\n"
        "Проанализируй визуальную структуру лендинга по скриншотам. Отвечай только JSON."
    )


def _user_prompt_text(url: str, destination_type: str, full_text: str) -> str:
    return (
        f"URL: {url}\n"
        f"Destination type: {destination_type}\n\n"
        f"Текст страницы:\n{full_text}\n\n"
        "Извлеки поля строго по инструкции. Отвечай только JSON."
    )


# ---------------------------------------------------------------------------
# JSON helper
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> tuple[dict | None, str | None]:
    clean = raw.strip()
    if clean.startswith("```"):
        parts = clean.split("```", 2)
        if len(parts) >= 2:
            clean = parts[1]
        if clean.startswith("json"):
            clean = clean[4:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
    try:
        return json.loads(clean), None
    except json.JSONDecodeError as e:
        return None, str(e)


# ---------------------------------------------------------------------------
# OpenAI calls
# ---------------------------------------------------------------------------

def _call_vision(client, url: str, destination_type: str,
                 screenshots: list[Path], model: str) -> dict:
    """Vision pass: send up to 3 selected screenshots to gpt-4o."""
    selected = _select_screenshots(screenshots)
    if not selected:
        return {"status": "skipped", "reason": "no screenshots", "fields": {}, "tokens_used": 0}

    text_part   = {"type": "text", "text": _user_prompt_vision(url, destination_type, len(selected))}
    image_parts = [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_encode_image(p)}"}}
        for p in selected
    ]

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS_VISION,
            messages=[
                {"role": "system", "content": SYSTEM_VISION},
                {"role": "user",   "content": [text_part] + image_parts},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw    = response.choices[0].message.content or ""
        parsed, err = _parse_json(raw)
        tokens = getattr(response.usage, "total_tokens", 0) or 0
        if err:
            return {"status": "parse_error", "error": err, "fields": {}, "tokens_used": tokens}
        return {
            "status":           "ok",
            "fields":           parsed,
            "tokens_used":      tokens,
            "screenshots_used": [p.name for p in selected],
        }
    except Exception as e:
        return {"status": "openai_error", "error": str(e), "fields": {}, "tokens_used": 0}


def _call_text(client, url: str, destination_type: str,
               full_text: str, model: str) -> dict:
    """Text pass: send extracted page text to gpt-4o."""
    if not full_text.strip():
        return {"status": "skipped", "reason": "empty text", "fields": {}, "tokens_used": 0}

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS_TEXT,
            messages=[
                {"role": "system", "content": SYSTEM_TEXT},
                {"role": "user",   "content": _user_prompt_text(url, destination_type, full_text)},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw    = response.choices[0].message.content or ""
        parsed, err = _parse_json(raw)
        tokens = getattr(response.usage, "total_tokens", 0) or 0
        if err:
            return {"status": "parse_error", "error": err, "fields": {}, "tokens_used": tokens}
        return {"status": "ok", "fields": parsed, "tokens_used": tokens}
    except Exception as e:
        return {"status": "openai_error", "error": str(e), "fields": {}, "tokens_used": 0}


# ---------------------------------------------------------------------------
# Field normalization + merge
# ---------------------------------------------------------------------------

def _norm_field(raw: dict, key: str) -> dict:
    entry = raw.get(key)
    if isinstance(entry, dict):
        return {
            "value":       str(entry.get("value") or ""),
            "data_status": entry.get("data_status") or "not_found",
        }
    return {"value": "", "data_status": "not_found"}


def _empty_fields() -> dict:
    return {k: {"value": "", "data_status": "not_found"} for k in _ALL_FIELDS}


def merge_fields(vision_raw: dict, text_raw: dict) -> dict:
    """
    Merge vision and text pass results.
    - Vision-authoritative: vision wins, text as fallback.
    - Text-authoritative:   text wins, vision as fallback.
    - Shared fields:        prefer ok status; text wins tie.
    """
    merged = {}
    for key in _ALL_FIELDS:
        v = _norm_field(vision_raw, key)
        t = _norm_field(text_raw,   key)

        if key in _VISION_AUTHORITATIVE:
            merged[key] = v if v["data_status"] == "ok" else (t if t["data_status"] == "ok" else v)
        elif key in _TEXT_AUTHORITATIVE:
            merged[key] = t if t["data_status"] == "ok" else (v if v["data_status"] == "ok" else t)
        else:
            # shared: prefer ok; text wins tie
            if t["data_status"] == "ok":
                merged[key] = t
            elif v["data_status"] == "ok":
                merged[key] = v
            else:
                merged[key] = t
    return merged


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(url: str, destination_type: str):
    print("[DRY-RUN] Playwright not launched. OpenAI not called. No files written.\n")

    print("=" * 60)
    print("INPUT:")
    print("=" * 60)
    print(f"  url:              {url}")
    print(f"  destination_type: {destination_type}")
    print(f"  max_screenshots:  {MAX_SCREENSHOTS}")
    print(f"  text_chars_limit: {MAX_TEXT_CHARS}")
    print(f"  screenshot_dir:   {SCREENSHOT_DIR.relative_to(BASE)}")
    print()

    print("=" * 60)
    print("SCROLL PLAN:")
    print("=" * 60)
    print("  1. goto(url, wait_until=networkidle)")
    print("  2. wait 2s")
    print("  3. for i in 0..4:")
    print("       screenshot screen_{i+1}.png (viewport only, 1280×900)")
    print("       md5 hash vs previous → stop if identical")
    print("       scrollBy(0, innerHeight)")
    print("       wait_for_load_state(networkidle, timeout=5s) or fallback wait 800ms")
    print("       check scrollY before vs after → stop if stuck")
    print("  4. page.inner_text('body')[:15000]")
    print("     → warn + Vision-only if len < 200 chars (SPA)")
    print()

    print("=" * 60)
    print("VISION PASS — System prompt (gpt-4o):")
    print("=" * 60)
    print(SYSTEM_VISION)
    print()
    print("VISION PASS — User prompt (example, 3 screenshots):")
    print("-" * 40)
    print(_user_prompt_vision(url, destination_type, 3))
    print("[+ 3 base64-encoded PNG images: first, middle, last]")
    print()

    print("=" * 60)
    print("TEXT PASS — System prompt (gpt-4o):")
    print("=" * 60)
    print(SYSTEM_TEXT)
    print()
    print("TEXT PASS — User prompt (example):")
    print("-" * 40)
    print(_user_prompt_text(url, destination_type, "(полный текст страницы — до 15000 символов)"))
    print()

    print("=" * 60)
    print("MERGE STRATEGY:")
    print("=" * 60)
    print(f"  Vision-authoritative: {sorted(_VISION_AUTHORITATIVE)}")
    print(f"  Text-authoritative:   {sorted(_TEXT_AUTHORITATIVE)}")
    print(f"  Shared (prefer ok, text wins tie): {sorted(_SHARED_FIELDS)}")
    print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"max_tokens:     vision={MAX_TOKENS_VISION}  text={MAX_TOKENS_TEXT}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2G v2: Landing Analyzer — Playwright scroll + dual-pass OpenAI"
    )
    parser.add_argument("--dry-run", action="store_true",
        help="Show plan and prompts; do NOT launch Playwright or call OpenAI")
    parser.add_argument("--url", default=None,
        help="Analyze this URL instead of reading from stage5a2f_link_destination.json")
    parser.add_argument("--model", default=DEFAULT_MODEL,
        help=f"OpenAI model (default: {DEFAULT_MODEL})")
    parser.add_argument("--account", default="vlada_kliuiko")
    args = parser.parse_args()

    # Resolve input
    if args.url:
        url, destination_type, url_source = args.url, "неизвестно", "--url flag"
    else:
        url, destination_type, err = load_input()
        url_source = "stage5a2f_link_destination.json"
        if err:
            if args.dry_run:
                print(f"[DRY-RUN] {err}")
                url, destination_type = "(URL not available — stage5a2f absent)", "неизвестно"
            else:
                if OUTPUT_PATH.exists():
                    print(f"[INFO] {err} — reusing existing {OUTPUT_PATH.name}")
                    sys.exit(0)
                print(f"[ERROR] {err}")
                sys.exit(1)

    print(f"URL source:       {url_source}")
    print(f"URL:              {url}")
    print(f"Destination type: {destination_type}")

    if args.dry_run:
        run_dry_run(url, destination_type)
        return

    # Load env / API key
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

    # Fetch page
    print("Fetching page with Playwright (scroll mode)...")
    content = fetch_with_playwright(url)

    fetch_success = content.get("fetch_success", False)
    screenshots   = content.get("screenshots", [])
    full_text     = content.get("full_text", "")
    is_spa        = content.get("is_spa", False)

    print(f"  Screenshots taken: {len(screenshots)}")
    print(f"  Text length:       {len(full_text)} chars" + (" [SPA warning]" if is_spa else ""))

    if not fetch_success:
        print("[WARN] Playwright fetch failed — proceeding with empty content")

    # Vision pass
    if screenshots:
        selected = _select_screenshots(screenshots)
        print(f"Calling OpenAI Vision ({args.model}) — {len(selected)} screenshot(s)...")
        vision_result = _call_vision(client, url, destination_type, screenshots, args.model)
        print(f"  Vision: {vision_result['status']}  tokens: {vision_result.get('tokens_used', 0)}")
    else:
        print("[WARN] No screenshots — Vision pass skipped")
        vision_result = {"status": "skipped", "fields": {}, "tokens_used": 0}

    # Text pass
    if full_text.strip() and not is_spa:
        print(f"Calling OpenAI Text ({args.model}) — {len(full_text)} chars...")
        text_result = _call_text(client, url, destination_type, full_text, args.model)
        print(f"  Text:   {text_result['status']}  tokens: {text_result.get('tokens_used', 0)}")
    else:
        reason = "SPA page" if is_spa else "empty text"
        print(f"[WARN] Text pass skipped ({reason}) — Vision-only")
        text_result = {"status": "skipped", "reason": reason, "fields": {}, "tokens_used": 0}

    # Merge
    fields       = merge_fields(vision_result.get("fields") or {}, text_result.get("fields") or {})
    total_tokens = (vision_result.get("tokens_used") or 0) + (text_result.get("tokens_used") or 0)

    output = {
        "account":           ACCOUNT,
        "stage":             STAGE,
        "prompt_version":    PROMPT_VERSION,
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "url":               url,
        "destination_type":  destination_type,
        "fetch_success":     fetch_success,
        "text_length":       len(full_text),
        "is_spa":            is_spa,
        "screenshots_taken": len(screenshots),
        "screenshots_dir":   str(SCREENSHOT_DIR.relative_to(BASE)),
        "vision_status":     vision_result.get("status"),
        "text_status":       text_result.get("status"),
        "tokens_used":       total_tokens,
        "fields":            fields,
    }
    if content.get("fetch_error"):
        output["fetch_error"] = content["fetch_error"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    print("\n=== Field Summary ===")
    labels = {
        "chto_prodayut":         "Что продают",
        "glavnyy_zagolovok":     "Главный заголовок",
        "dlya_kogo":             "Для кого",
        "obeshchanie_rezultata": "Обещание результата",
        "glavnyy_cta":           "Главный CTA",
        "sots_dokazatelstva":    "Соцдоказательства",
        "boli":                  "Боли",
        "argumenty":             "Аргументы",
    }
    for key, label in labels.items():
        f   = fields.get(key, {})
        val = (f.get("value") or "")[:80] or "(empty)"
        print(f"  {label:<25}: [{f.get('data_status', '?')}] {val}")


if __name__ == "__main__":
    main()
