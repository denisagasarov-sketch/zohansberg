"""Stage 5A-2F: Link Destination Classifier.

Reads external_url.value from data/normalized/profile_summary.json (or --url flag),
fetches the page, applies heuristics, then calls OpenAI gpt-4o-mini if needed.

Usage:
    python3 scripts/stage5a2f_link_destination_classifier.py --dry-run
    python3 scripts/stage5a2f_link_destination_classifier.py
    python3 scripts/stage5a2f_link_destination_classifier.py --url "https://example.com"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

BASE     = Path(__file__).parent.parent
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT  = _args.account
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"

PROFILE_SUMMARY_PATH = NORM_DIR / "profile_summary.json"
OUTPUT_PATH          = NORM_DIR / "stage5a2f_link_destination.json"
STAGE          = "stage5a2f"
PROMPT_VERSION = "v1"
DEFAULT_MODEL  = "gpt-4o-mini"
MAX_TOKENS     = 200

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}

# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

_HEURISTIC_RULES = [
    ({"taplink.ru", "tap.link"},                           "taplink"),
    ({"forms.gle", "typeform.com", "tally.so"},            "анкета"),
    ({"mssg.me", "linktr.ee", "beacons.ai"},               "мультиссылка"),
]


def _apply_heuristic(final_url: str) -> str | None:
    """Return destination_type string if heuristic matches, else None."""
    parsed = urlparse(final_url)
    domain = parsed.netloc.lower().lstrip("www.")
    path   = parsed.path.lower()

    for domains, dtype in _HEURISTIC_RULES:
        if domain in domains:
            return dtype

    if domain == "t.me":
        return "бот" if "bot" in path else "telegram_канал"

    return None


# ---------------------------------------------------------------------------
# URL utils
# ---------------------------------------------------------------------------

def _clean_url(url: str) -> str:
    """Remove UTM parameters from URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in qs.items() if k.lower() not in _UTM_PARAMS}
    new_query = urlencode(filtered, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


# ---------------------------------------------------------------------------
# Profile URL loader
# ---------------------------------------------------------------------------

def load_url_from_profile() -> tuple[str, str | None]:
    """Return (url, error_or_None)."""
    if not PROFILE_SUMMARY_PATH.exists():
        return "", f"{PROFILE_SUMMARY_PATH.relative_to(BASE)} not found"
    try:
        data = json.loads(PROFILE_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return "", f"Failed to parse profile_summary.json: {e}"

    raw = data.get("external_url", {})
    url = (raw.get("value") if isinstance(raw, dict) else raw) or ""
    if not url:
        return "", "external_url.value is empty in profile_summary.json"
    return url, None


# ---------------------------------------------------------------------------
# Page fetcher
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> dict:
    """Fetch URL and extract title/meta fields. Returns fetch_result dict."""
    import requests
    from html.parser import HTMLParser

    class _MetaParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.title       = ""
            self.description = ""
            self.og_title    = ""
            self.og_desc     = ""
            self._in_title   = False

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "title":
                self._in_title = True
            elif tag == "meta":
                name    = a.get("name", "").lower()
                prop    = a.get("property", "").lower()
                content = a.get("content", "")
                if name == "description":
                    self.description = content
                elif prop == "og:title":
                    self.og_title = content
                elif prop == "og:description":
                    self.og_desc = content

        def handle_endtag(self, tag):
            if tag == "title":
                self._in_title = False

        def handle_data(self, data):
            if self._in_title:
                self.title += data

    try:
        resp = requests.get(
            url, timeout=15, allow_redirects=True,
            headers={"User-Agent": _UA},
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

    final_url  = resp.url
    redirected = (final_url.rstrip("/") != url.rstrip("/"))
    if redirected:
        print(f"[INFO] Redirected: {url} → {final_url}")

    if resp.status_code != 200:
        print(f"[WARN] HTTP {resp.status_code} for {final_url}")
        return {
            "status":      "fetch_failed",
            "fetch_status": resp.status_code,
            "final_url":   final_url,
            "redirected":  redirected,
        }

    parser = _MetaParser()
    try:
        parser.feed(resp.text)
    except Exception:
        pass

    hdrs        = resp.headers
    server_hint = ""
    srv         = hdrs.get("server", "")
    tilda       = hdrs.get("x-tilda-server", "")
    if tilda or "tilda" in srv.lower():
        server_hint = "tilda"
    elif srv:
        server_hint = srv.split("/")[0].lower()

    return {
        "status":       "ok",
        "fetch_status":  resp.status_code,
        "final_url":     final_url,
        "redirected":    redirected,
        "title":         parser.title.strip(),
        "og_title":      parser.og_title.strip(),
        "description":   (parser.description or parser.og_desc).strip(),
        "server_hint":   server_hint,
    }


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик маркетинговых воронок. Тебе дают данные о странице по ссылке из bio Instagram.
Определи тип страницы. Отвечай строго в JSON, без текста вне JSON.

КАТЕГОРИИ (выбери одну):
- лендинг_курса — страница продажи обучающего курса, тренинга, интенсива, наставничества
- лендинг_консультации — страница записи на консультацию, разбор, аудит
- лендинг_агентства — страница услуг компании или агентства (не обучение, а услуги)
- лендинг_продукта — страница продажи физического или цифрового продукта
- taplink — агрегатор ссылок (taplink, linktree и аналоги)
- бот — Telegram-бот
- telegram_канал — Telegram-канал
- анкета — форма записи (Google Forms, Typeform, Tally)
- мультиссылка — другие агрегаторы ссылок
- сайт — корпоративный сайт без явного целевого действия
- неизвестно — недостаточно данных для классификации

ПРАВИЛА:
1. Используй title, description, og:title, og:description для определения типа.
2. Если title/description содержит "курс", "обучение", "тренинг", "интенсив", "научим", "обучим" → лендинг_курса
3. Если title/description содержит "консультац", "разбор", "аудит" → лендинг_консультации
4. Если это страница агентства с описанием услуг (SMM, таргет, маркетинг как услуга) — лендинг_агентства
5. Если страница одновременно продает курс И услуги агентства — выбери лендинг_курса если курс в title/og:title
6. Не додумывай. Если данных недостаточно → неизвестно.

Примеры:
- title "Маркетинговые стратегии", description "Научим делать стратегии уровня топ-агентств" → лендинг_курса
- title "SMM-агентство Elpodium — услуги продвижения" → лендинг_агентства
- title "Запишитесь на консультацию по маркетингу" → лендинг_консультации

ФОРМАТ ОТВЕТА (строго JSON):
{
  "destination_type": "...",
  "confidence": "high|medium|low",
  "reasoning": "1 предложение почему такой тип",
  "data_status": "ok|not_found"
}"""


def build_user_prompt(final_url: str, title: str, og_title: str,
                      description: str, server_hint: str) -> str:
    return (
        f"URL: {final_url}\n"
        f"Title: {title}\n"
        f"OG Title: {og_title}\n"
        f"Description: {description}\n"
        f"Server: {server_hint}\n\n"
        "Определи тип страницы. Отвечай только JSON."
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

def _call_openai(client, fetch: dict, model: str) -> dict:
    user_prompt = build_user_prompt(
        final_url   = fetch.get("final_url", ""),
        title       = fetch.get("title", ""),
        og_title    = fetch.get("og_title", ""),
        description = fetch.get("description", ""),
        server_hint = fetch.get("server_hint", ""),
    )
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
            "result":      parsed,
            "tokens_used": getattr(response.usage, "total_tokens", None),
        }
    except Exception as e:
        return {"status": "openai_error", "error": str(e)}


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(url_input: str):
    print("[DRY-RUN] No HTTP requests made. OpenAI not called. No files will be written.\n")

    url_clean = _clean_url(url_input)

    print("=" * 60)
    print("INPUT URL:")
    print("=" * 60)
    print(f"  url_input: {url_input}")
    print(f"  url_clean: {url_clean}")
    print()

    print("=" * 60)
    print("SYSTEM PROMPT (будет отправлен в OpenAI):")
    print("=" * 60)
    print(SYSTEM_PROMPT)
    print()

    example_prompt = build_user_prompt(
        final_url   = url_clean,
        title       = "(title страницы после fetch)",
        og_title    = "(og:title)",
        description = "(description / og:description)",
        server_hint = "(server header)",
    )
    print("=" * 60)
    print("USER PROMPT (будет отправлен в OpenAI после fetch):")
    print("=" * 60)
    print(example_prompt)
    print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"max_tokens:     {MAX_TOKENS}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2F: Link Destination Classifier"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show URL and prompts; do NOT fetch page, call OpenAI, or write output",
    )
    parser.add_argument(
        "--url", default=None,
        help="Classify this URL instead of reading from profile_summary.json",
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

    # Resolve input URL
    if args.url:
        url_input = args.url
        url_source = "--url flag"
    else:
        url_input, err = load_url_from_profile()
        url_source = "profile_summary.json"
        if err:
            if args.dry_run:
                print(f"[DRY-RUN] {err}")
                url_input = "(URL not available — profile_summary.json absent)"
            else:
                if OUTPUT_PATH.exists():
                    print(f"[INFO] {err} — reusing existing {OUTPUT_PATH.name}")
                    sys.exit(0)
                print(f"[ERROR] {err}")
                sys.exit(1)

    print(f"URL source: {url_source}")
    print(f"URL: {url_input}")

    if args.dry_run:
        run_dry_run(url_input)
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

    client    = OpenAI(api_key=api_key)
    url_clean = _clean_url(url_input)

    # Fetch page
    print("Fetching page...")
    fetch = fetch_page(url_input)

    if fetch.get("status") == "error":
        print(f"[ERROR] Fetch failed: {fetch.get('error')}")
        sys.exit(1)

    fetch_status = fetch.get("fetch_status")
    final_url    = fetch.get("final_url", url_input)
    redirected   = fetch.get("redirected", False)

    if fetch.get("status") == "fetch_failed":
        output = {
            "account":               ACCOUNT,
            "stage":                 STAGE,
            "prompt_version":        PROMPT_VERSION,
            "url_input":             url_input,
            "url_clean":             url_clean,
            "url_final":             final_url,
            "fetch_status":          fetch_status,
            "redirected":            redirected,
            "title":                 "",
            "og_title":              "",
            "description":           "",
            "server_hint":           "",
            "classification_method": None,
            "result": {
                "destination_type": "неизвестно",
                "confidence":       "low",
                "reasoning":        f"HTTP {fetch_status} — page not accessible",
                "data_status":      "fetch_failed",
            },
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[WARN] Written with fetch_failed status: {OUTPUT_PATH.relative_to(BASE)}")
        return

    title       = fetch.get("title", "")
    og_title    = fetch.get("og_title", "")
    description = fetch.get("description", "")
    server_hint = fetch.get("server_hint", "")

    # Heuristic check
    heuristic = _apply_heuristic(final_url)
    if heuristic:
        print(f"[INFO] Heuristic match: {heuristic}")
        classification_method = "heuristic"
        result = {
            "destination_type": heuristic,
            "confidence":       "high",
            "reasoning":        f"Domain matched heuristic rule for {heuristic}",
            "data_status":      "ok",
        }
        tokens_used = None
    else:
        print(f"Calling OpenAI ({args.model}) for classification...")
        ai_result = _call_openai(client, fetch, args.model)

        if ai_result["status"] not in ("ok",):
            print(f"[ERROR] OpenAI call failed: {ai_result.get('error') or ai_result.get('raw_response')}")
            sys.exit(1)

        classification_method = "openai"
        result      = ai_result.get("result", {})
        tokens_used = ai_result.get("tokens_used")

    output = {
        "account":               ACCOUNT,
        "stage":                 STAGE,
        "prompt_version":        PROMPT_VERSION,
        "url_input":             url_input,
        "url_clean":             url_clean,
        "url_final":             final_url,
        "fetch_status":          fetch_status,
        "redirected":            redirected,
        "title":                 title,
        "og_title":              og_title,
        "description":           description,
        "server_hint":           server_hint,
        "classification_method": classification_method,
        "tokens_used":           tokens_used,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "result":                result,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    print("\n=== Classification Result ===")
    print(f"  destination_type:      {result.get('destination_type')}")
    print(f"  confidence:            {result.get('confidence')}")
    print(f"  classification_method: {classification_method}")
    print(f"  reasoning:             {result.get('reasoning', '')[:100]}")


if __name__ == "__main__":
    main()
