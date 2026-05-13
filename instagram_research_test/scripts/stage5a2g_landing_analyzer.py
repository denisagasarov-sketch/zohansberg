"""Stage 5A-2G: Landing Page Analyzer.

Reads url_clean and result.destination_type from data/normalized/stage5a2f_link_destination.json,
fetches the page via Playwright, sends content to OpenAI gpt-4o, extracts 11 structural fields.

Usage:
    python3 scripts/stage5a2g_landing_analyzer.py --dry-run
    python3 scripts/stage5a2g_landing_analyzer.py
    python3 scripts/stage5a2g_landing_analyzer.py --url "https://example.com"
"""

import argparse
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

STAGE5A2F_PATH  = NORM_DIR / "stage5a2f_link_destination.json"
OUTPUT_PATH     = NORM_DIR / "stage5a2g_landing_analysis.json"
SCREENSHOT_PATH = str(BASE / "output" / ACCOUNT / "stage5a2g_screenshot.png")
STAGE          = "stage5a2g"
PROMPT_VERSION = "v1"
DEFAULT_MODEL  = "gpt-4o"
MAX_TOKENS     = 1500

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

    url  = data.get("url_clean") or data.get("url_input") or ""
    dtype = (data.get("result") or {}).get("destination_type") or "неизвестно"
    if not url:
        return "", dtype, "url_clean is empty in stage5a2f_link_destination.json"
    return url, dtype, None


# ---------------------------------------------------------------------------
# Playwright page fetch
# ---------------------------------------------------------------------------

def fetch_with_playwright(url: str) -> dict:
    """Fetch page via Playwright headless Chromium. Returns content dict."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "fetch_success": False,
            "fetch_error":   "playwright not installed — run: pip install playwright && playwright install chromium",
        }

    def _clean(texts):
        return [t.strip() for t in texts if t.strip() and len(t.strip()) > 2]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=_UA)
            page    = context.new_page()
            page.set_default_timeout(30000)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            h1_texts  = _clean(page.locator("h1").all_inner_texts())
            h2_texts  = _clean(page.locator("h2").all_inner_texts())
            p_texts   = _clean(page.locator("p").all_inner_texts())[:20]

            all_btns  = page.locator(
                "button, a.btn, [class*='button'], [class*='btn']"
            ).all_inner_texts()
            btn_texts = [t.strip() for t in all_btns if 3 <= len(t.strip()) <= 100][:10]

            full_text = page.inner_text("body")[:8000]

            Path("output").mkdir(exist_ok=True)
            page.screenshot(path=SCREENSHOT_PATH)
            print(f"[INFO] Screenshot saved: {SCREENSHOT_PATH}")

            browser.close()

        return {
            "fetch_success": True,
            "h1_texts":      h1_texts,
            "h2_texts":      h2_texts,
            "p_texts":       p_texts,
            "btn_texts":     btn_texts,
            "full_text":     full_text,
            "text_length":   len(full_text),
        }

    except Exception as e:
        print(f"[ERROR] Playwright fetch failed: {e}")
        return {
            "fetch_success": False,
            "fetch_error":   str(e),
            "h1_texts":      [],
            "h2_texts":      [],
            "p_texts":       [],
            "btn_texts":     [],
            "full_text":     "",
            "text_length":   0,
        }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик маркетинговых лендингов. Тебе дают текст страницы из bio Instagram-аккаунта.
Извлеки структурированные данные для анализа конкурента. Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ ДЛЯ ИЗВЛЕЧЕНИЯ:

chto_prodayut (Что продают):
  Название продукта или услуги. 1-2 слова или короткая фраза.
  Пример: "курс по маркетинговым стратегиям" или "SMM-услуги"

pervye_3_ekrana (Структура первых 3х экранов):
  Кратко опиши что на первых 3 экранах лендинга — что видит пользователь сначала.
  1-3 предложения.

glavnyy_zagolovok (Главный заголовок):
  Точный текст главного h1 или первого крупного заголовка.

podzagolovok (Подзаголовок):
  Текст под главным заголовком.

dlya_kogo (Для кого):
  Явное указание целевой аудитории. Если не указано явно — пустая строка.

obeshchanie_rezultata (Обещание результата):
  Что конкретно обещают получить клиенту.

glavnyy_cta (Главный CTA):
  Точный текст главной кнопки или призыва к действию.

sots_dokazatelstva (Соцдоказательства):
  Цифры, отзывы, кейсы. Кратко перечислить. Если нет — пустая строка.

boli (Какие боли раскрывают):
  Проблемы аудитории которые упоминает лендинг. 1-3 пункта кратко.

argumenty (Какие аргументы используют):
  Почему выбрать именно их. 1-3 пункта кратко.

bloki_dalshe (Какие блоки есть дальше):
  Структура страницы ниже первых экранов. Кратко перечислить блоки.

ПРАВИЛА:
1. Используй только то что явно есть на странице.
2. Не додумывай. Если поле не определяется — пустая строка и data_status: "not_found".
3. Все ответы на русском языке.
4. Отвечай строго в JSON, без текста вне JSON.

ФОРМАТ ОТВЕТА:
{
  "chto_prodayut":         {"value": "...", "data_status": "ok|not_found"},
  "pervye_3_ekrana":       {"value": "...", "data_status": "ok|not_found"},
  "glavnyy_zagolovok":     {"value": "...", "data_status": "ok|not_found"},
  "podzagolovok":          {"value": "...", "data_status": "ok|not_found"},
  "dlya_kogo":             {"value": "...", "data_status": "ok|not_found"},
  "obeshchanie_rezultata": {"value": "...", "data_status": "ok|not_found"},
  "glavnyy_cta":           {"value": "...", "data_status": "ok|not_found"},
  "sots_dokazatelstva":    {"value": "...", "data_status": "ok|not_found"},
  "boli":                  {"value": "...", "data_status": "ok|not_found"},
  "argumenty":             {"value": "...", "data_status": "ok|not_found"},
  "bloki_dalshe":          {"value": "...", "data_status": "ok|not_found"}
}"""


def build_user_prompt(url: str, destination_type: str, content: dict) -> str:
    h1   = content.get("h1_texts") or []
    h2   = content.get("h2_texts") or []
    btns = content.get("btn_texts") or []
    text = content.get("full_text") or ""
    return (
        f"URL: {url}\n"
        f"Destination type: {destination_type}\n\n"
        f"H1: {h1}\n"
        f"H2: {h2}\n"
        f"Buttons/CTA: {btns}\n\n"
        f"Page text (first 8000 chars):\n{text}\n\n"
        "Извлеки 11 полей строго по инструкции. Отвечай только JSON."
    )


# ---------------------------------------------------------------------------
# JSON parse helper
# ---------------------------------------------------------------------------

def _parse_json(raw: str) -> tuple[dict | None, str | None]:
    clean = raw.strip()
    if clean.startswith("```"):
        if clean.count("```") >= 2:
            clean = clean.split("```", 2)[1]
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
# OpenAI call
# ---------------------------------------------------------------------------

def _call_openai(client, url: str, destination_type: str, content: dict, model: str) -> dict:
    user_prompt = build_user_prompt(url, destination_type, content)
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        parsed, err = _parse_json(raw)
        if err:
            return {
                "status":       "parse_error",
                "parse_error":  True,
                "raw_response": raw[:300],
                "tokens_used":  getattr(response.usage, "total_tokens", None),
            }
        return {
            "status":      "ok",
            "fields":      parsed,
            "tokens_used": getattr(response.usage, "total_tokens", None),
        }
    except Exception as e:
        return {"status": "openai_error", "error": str(e)}


# ---------------------------------------------------------------------------
# Field builder
# ---------------------------------------------------------------------------

def _build_fields(raw: dict) -> dict:
    """Normalise OpenAI response into the expected fields structure."""
    fields = {}
    for key in _ALL_FIELDS:
        entry = raw.get(key)
        if isinstance(entry, dict):
            fields[key] = {
                "value":       entry.get("value", ""),
                "data_status": entry.get("data_status", "not_found"),
            }
        else:
            fields[key] = {"value": "", "data_status": "not_found"}
    return fields


def _empty_fields() -> dict:
    return {k: {"value": "", "data_status": "not_found"} for k in _ALL_FIELDS}


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(url: str, destination_type: str):
    print("[DRY-RUN] Playwright not launched. OpenAI not called. No files will be written.\n")

    print("=" * 60)
    print("INPUT:")
    print("=" * 60)
    print(f"  url:              {url}")
    print(f"  destination_type: {destination_type}")
    print()

    print("=" * 60)
    print("SYSTEM PROMPT (будет отправлен в OpenAI):")
    print("=" * 60)
    print(SYSTEM_PROMPT)
    print()

    example_content = {
        "h1_texts":  ["(h1 тексты после Playwright fetch)"],
        "h2_texts":  ["(h2 тексты)"],
        "btn_texts": ["(тексты кнопок)"],
        "full_text": "(полный текст страницы — первые 8000 символов)",
    }
    print("=" * 60)
    print("USER PROMPT (будет отправлен в OpenAI после Playwright fetch):")
    print("=" * 60)
    print(build_user_prompt(url, destination_type, example_content))
    print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"max_tokens:     {MAX_TOKENS}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Screenshot:     {SCREENSHOT_PATH}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2G: Landing Page Analyzer via Playwright + OpenAI"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show URL and prompts; do NOT launch Playwright, call OpenAI, or write output",
    )
    parser.add_argument(
        "--url", default=None,
        help="Analyze this URL instead of reading from stage5a2f_link_destination.json",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {DEFAULT_MODEL})",
    )
    args = parser.parse_args()

    # Resolve input
    if args.url:
        url              = args.url
        destination_type = "неизвестно"
        url_source       = "--url flag"
    else:
        url, destination_type, err = load_input()
        url_source = "stage5a2f_link_destination.json"
        if err:
            if args.dry_run:
                print(f"[DRY-RUN] {err}")
                url              = "(URL not available — stage5a2f absent)"
                destination_type = "неизвестно"
            else:
                print(f"[ERROR] {err}")
                sys.exit(1)

    print(f"URL source:       {url_source}")
    print(f"URL:              {url}")
    print(f"Destination type: {destination_type}")

    if args.dry_run:
        run_dry_run(url, destination_type)
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

    # Fetch page
    print("Fetching page with Playwright...")
    content = fetch_with_playwright(url)

    fetch_success = content.get("fetch_success", False)
    fetch_error   = content.get("fetch_error")
    text_length   = content.get("text_length", 0)

    if not fetch_success:
        print(f"[WARN] Playwright fetch failed — proceeding with empty content")

    # Call OpenAI
    print(f"Calling OpenAI ({args.model}) for landing analysis...")
    ai_result = _call_openai(client, url, destination_type, content, args.model)

    if ai_result["status"] == "openai_error":
        print(f"[ERROR] OpenAI call failed: {ai_result.get('error')}")
        sys.exit(1)

    if ai_result.get("parse_error"):
        print(f"[WARN] JSON parse error — fields will be empty")
        fields      = _empty_fields()
        tokens_used = ai_result.get("tokens_used")
    else:
        fields      = _build_fields(ai_result.get("fields") or {})
        tokens_used = ai_result.get("tokens_used")

    output = {
        "account":          ACCOUNT,
        "stage":            STAGE,
        "prompt_version":   PROMPT_VERSION,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "url":              url,
        "destination_type": destination_type,
        "fetch_success":    fetch_success,
        "text_length":      text_length,
        "screenshot":       SCREENSHOT_PATH if fetch_success else None,
        "tokens_used":      tokens_used,
        "fields":           fields,
    }
    if fetch_error:
        output["fetch_error"] = fetch_error

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
    }
    for key, label in labels.items():
        f   = fields.get(key, {})
        val = (f.get("value") or "")[:80] or "(empty)"
        print(f"  {label:<25}: [{f.get('data_status', '?')}] {val}")


if __name__ == "__main__":
    main()
