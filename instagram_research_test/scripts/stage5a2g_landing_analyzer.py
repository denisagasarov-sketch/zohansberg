"""Stage 5A-2G: Landing Page Analyzer v3.

Six focused passes via Playwright scroll + OpenAI:
  Pass G1 (Vision, first screenshot only): visual structure, heading, CTA, deadline.
  Pass G2 (Text): positioning — how they describe themselves, audience, core/big job.
  Pass G3 (Text): trust signals — numbers, reviews, cases, media, certificates.
  Pass G4 (Text): pains, objections, FAQ.
  Pass G5 (Text): product description — name, format, duration, contents, pricing options.
  Pass G6 (Text): sales mechanics — how they sell, scarcity, bonuses, final CTA.
  Pass G7 (Text): creative analysis — non-standard elements, unusual naming, formats.
  Each field returns {value, data_status, confidence}.
  Legacy fields (11) are synthesized from new fields for backward compat.

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

STAGE          = "stage5a2g"
PROMPT_VERSION = "v3"
DEFAULT_MODEL  = "gpt-4o"
MAX_SCROLL_SCREENSHOTS = 10   # absolute safety cap (unique screenshots)
MAX_TEXT_CHARS  = 15000

MAX_TOKENS_G1 = 600   # Vision: 5 fields, first screenshot only
MAX_TOKENS_G2 = 800   # Text: positioning (5 fields)
MAX_TOKENS_G3 = 1000  # Text: trust signals (5 fields, potentially verbose)
MAX_TOKENS_G4 = 600   # Text: pains (3 fields)
MAX_TOKENS_G5 = 800   # Text: product (7 fields)
MAX_TOKENS_G6 = 600   # Text: sales (4 fields)
MAX_TOKENS_G7 = 600   # Text: creative analysis (1 field)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# New v3 fields (22 total across 6 groups)
_FIELDS_G1 = ["glavnyy_zagolovok", "podzagolovok", "vizualnyy_obraz", "glavnyy_cta", "est_dedlayn"]
_FIELDS_G2 = ["kak_sebya_nazyvayut", "dlya_kogo", "core_job", "big_job", "unikalnost"]
_FIELDS_G3 = ["cifry", "otzyvy_format", "keysy", "media", "sertifikaty"]
_FIELDS_G4 = ["boli", "vozrazheniya", "est_faq"]
_FIELDS_G5 = ["nazvanie_produkta", "format", "dlitelnost", "chto_vkhodit",
              "est_tarify", "est_rassrochka", "est_garantiya"]
_FIELDS_G6 = ["sposob_prodazhi", "est_ogranichenie", "est_bonusy", "finalnyy_cta"]
_FIELDS_G7 = ["neobychnye_resheniya"]

_ALL_NEW_FIELDS = _FIELDS_G1 + _FIELDS_G2 + _FIELDS_G3 + _FIELDS_G4 + _FIELDS_G5 + _FIELDS_G6 + _FIELDS_G7

# Legacy fields preserved for backward compat with stage5d1
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
    Stops when: 2 consecutive identical hashes, absolute cap of MAX_SCROLL_SCREENSHOTS, or scroll stuck.
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

            # Dismiss cookie banners before scrolling
            for _banner_text in ["Принять все", "Принять", "Accept all", "Accept", "OK"]:
                try:
                    _btn = page.get_by_text(_banner_text, exact=True)
                    if _btn.count() > 0:
                        _btn.first.click()
                        page.wait_for_timeout(500)
                        break
                except Exception:
                    pass

            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            screenshots      = []
            prev_hash        = None
            identical_streak = 0
            attempt          = 0

            while len(screenshots) < MAX_SCROLL_SCREENSHOTS:
                attempt += 1
                path = SCREENSHOT_DIR / f"screen_{attempt}.png"
                page.screenshot(path=str(path), full_page=False)

                h = _screenshot_hash(path)
                if h == prev_hash:
                    path.unlink(missing_ok=True)
                    identical_streak += 1
                    if identical_streak >= 2:
                        print(f"  [scroll] Screen {attempt}: identical x2 — stopping")
                        break
                    print(f"  [scroll] Screen {attempt}: identical (1/2) — skipping, continuing")
                else:
                    screenshots.append(path)
                    prev_hash        = h
                    identical_streak = 0
                    print(f"  [scroll] Screen {len(screenshots)} saved: {path.name}")

                scroll_before = page.evaluate("window.scrollY")
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    page.wait_for_timeout(800)

                scroll_after = page.evaluate("window.scrollY")
                if scroll_after == scroll_before:
                    print(f"  [scroll] Attempt {attempt}: no scroll progress — stopping")
                    break

            # Final screenshot: bottom of page
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1000)
            bottom_path = SCREENSHOT_DIR / "screen_bottom.png"
            page.screenshot(path=str(bottom_path), full_page=False)
            h_bottom = _screenshot_hash(bottom_path)
            if h_bottom != prev_hash:
                screenshots.append(bottom_path)
                print(f"  [scroll] Bottom screenshot saved: {bottom_path.name}")
            else:
                bottom_path.unlink(missing_ok=True)
                print(f"  [scroll] Bottom screenshot: identical to last — skipped")

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
# Image encoding
# ---------------------------------------------------------------------------

def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


# ---------------------------------------------------------------------------
# Prompts — G1 Vision (first screen only)
# ---------------------------------------------------------------------------

SYSTEM_G1_VISION = """\
Ты — аналитик маркетинговых лендингов. Перед тобой скриншот ПЕРВОГО экрана лендинга.
Анализируй только то что ВИДНО — размер текста, расположение, кнопки, изображения.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

glavnyy_zagolovok: ТОЧНАЯ ЦИТАТА самого крупного текста на первом экране (hero h1). Дословно, не пересказывай.
podzagolovok: Текст сразу под главным заголовком — дословно. Если нет — "".
vizualnyy_obraz: Строго в формате "[что изображено], [цвет фона], [главный элемент]".
  Максимум 60 символов. Пример: "две женщины, тёмно-красный фон, шестерёнки".
  Только визуальные факты — не пересказывай текст заголовков.
glavnyy_cta: Точный текст самой заметной кнопки на первом экране — вне cookie-баннеров.
  ИГНОРИРОВАТЬ кнопки cookie-баннеров: "Принять", "Соглашаюсь", "Accept", "OK", "Настроить",
  "Принять все", "Accept all" и любые аналоги. Если главного CTA нет на первом экране — "".
est_dedlayn: Есть ли на первом экране таймер, счётчик, дата окончания или фраза о дедлайне.
  Значение: "да" или "нет".
otzyvy_format: Видны ли на скриншоте блоки с отзывами клиентов. Признаки:
  — фотографии людей с текстом похожим на отзыв или результат
  — карточки с именами, фото, описанием "до/после"
  — видео с кнопкой play на фоне портрета или логотипа
  — скриншоты переписки (мессенджер, email)
  Если блок отзывов виден — укажи формат через «; »: "текст", "видео", "карточки до-после",
  "скриншоты переписки". Если отзывов не видно — data_status "not_found", value "".

ПРАВИЛА:
1. Только то что ВИДНО на скриншоте. Не додумывай.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явно видно, "medium" если надо интерпретировать, "low" если угадываешь.

ФОРМАТ (строго JSON):
{
  "glavnyy_zagolovok": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "podzagolovok":      {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "vizualnyy_obraz":   {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "glavnyy_cta":       {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_dedlayn":       {"value": "да|нет", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "otzyvy_format":     {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


# ---------------------------------------------------------------------------
# Prompts — G2–G6 Text passes
# ---------------------------------------------------------------------------

SYSTEM_G2_POSITIONING = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — извлечь позиционирование продукта.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

kak_sebya_nazyvayut: Как они сами называют свой продукт — точная цитата названия или типа продукта.
dlya_kogo: Явное указание целевой аудитории — цитата из текста.
  Если не названа — "аудитория не названа".
core_job: Ключевой конкретный результат который обещают. Пример: "похудеть на 10 кг за 3 месяца".
  Если не заявлен явно — "".
big_job: Более широкое жизненное изменение которое несёт продукт. Пример: "стать уверенным в себе".
  Если не заявлено — "".
unikalnost: В чём уникальность или отличие от других. Цитата из текста.
  Если не заявлено — "не заявлено".
glavnyy_cta: РЕЗЕРВНОЕ ПОЛЕ — заполнять только если визуальный анализ первого экрана не определил CTA.
  Найди самую заметную кнопку призыва к действию в тексте страницы.
  ИГНОРИРОВАТЬ кнопки cookie-баннеров: "Принять", "Соглашаюсь", "Accept", "OK", "Настроить",
  "Принять все", "Accept all" и любые аналоги.
  Если главного CTA нет — data_status "not_found", value "".

ПРАВИЛА:
1. Только то что явно есть в тексте.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явная цитата, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "kak_sebya_nazyvayut": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "dlya_kogo":           {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "core_job":            {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "big_job":             {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "unikalnost":          {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "glavnyy_cta":         {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


SYSTEM_G3_TRUST = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — извлечь ВСЕ социальные доказательства и доверительные сигналы.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

cifry: ВСЕ конкретные цифры на лендинге — количество клиентов, лет работы, % результата, NPS, оценки.
  Перечисли через «; ». Пример: "1500+ учеников; 7 лет на рынке; 94% завершают курс".
  НЕ пропускай ни одну цифру. Если нет — "".
otzyvy_format: Есть ли блок отзывов на странице. Если да — опиши формат: текст, видео, скриншоты переписки,
  с именами/фото. Если блок отзывов отсутствует явно — data_status "not_found", value "".
  НЕ оставляй value пустым — либо описание формата, либо not_found.
keysy: Есть ли кейсы до/после или истории успеха клиентов. Если да — краткое описание 1-2 кейсов.
  Если кейсов нет явно — data_status "not_found", value "".
  НЕ оставляй value пустым — либо описание кейсов, либо not_found.
media: Упоминания СМИ, подкастов, конференций, публикаций. Перечисли через «; ».
  Если нет — "".
sertifikaty: Сертификаты, дипломы, лицензии, партнёрства с брендами, аккредитации.
  Перечисли через «; ». Если нет — "".

ПРАВИЛА:
1. Только то что явно есть в тексте. НЕ пропускай ни одну цифру или знак доверия.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явная цитата, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "cifry":         {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "otzyvy_format": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "keysy":         {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "media":         {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "sertifikaty":   {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


SYSTEM_G4_PAINS = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — извлечь боли аудитории, обработку возражений и наличие FAQ.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

boli: Боли и проблемы аудитории которые упоминает лендинг. Перечисли через «; ».
  Пример: "нет времени на спорт; не могу похудеть самостоятельно; нет мотивации".
  Если не упомянуто явно — "".
vozrazheniya: Возражения которые лендинг явно обрабатывает — с ответом.
  Формат: "возражение — ответ лендинга". Перечисли через «; ».
  Пример: "дорого — есть рассрочка; нет времени — занятия 20 мин в день".
  Если нет — "".
est_faq: Есть ли блок FAQ или часто задаваемые вопросы на странице. Значение: "да" или "нет".

ПРАВИЛА:
1. Только то что явно есть в тексте.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явная цитата, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "boli":         {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "vozrazheniya": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_faq":      {"value": "да|нет", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


SYSTEM_G5_PRODUCT = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — извлечь описание продукта.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

nazvanie_produkta: Официальное название продукта, курса или программы — точная цитата из текста.
  Ищи рядом со словами "курс", "программа", "интенсив", "марафон", "тренинг", "мастермайнд".
  Пример: если написано "программа «Сильное тело»" — вернуть "Сильное тело".
  Если явного названия нет — data_status "not_found", value "".
  НЕ подставляй главный заголовок страницы вместо названия продукта.
format: Формат продукта — онлайн-курс, живой тренинг, марафон, коучинг, подписка, консультация и т.д.
dlitelnost: Длительность программы — "8 недель", "3 месяца", "1 день".
  Если не указана — "".
chto_vkhodit: Что входит в продукт — модули, уроки, воркбуки, живые встречи, бонусы, материалы.
  Перечисли кратко. Если не раскрыто — "".
est_tarify: Есть ли несколько тарифов или пакетов. Значение: "да" или "нет".
est_rassrochka: Есть ли рассрочка или оплата частями. Значение: "да" или "нет".
est_garantiya: Есть ли гарантия результата или возврата денег. Значение: "да" или "нет".

ПРАВИЛА:
1. Только то что явно есть в тексте.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явная цитата, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "nazvanie_produkta": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "format":            {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "dlitelnost":        {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "chto_vkhodit":      {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_tarify":        {"value": "да|нет", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_rassrochka":    {"value": "да|нет", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_garantiya":     {"value": "да|нет", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


SYSTEM_G6_SALES = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — извлечь механику продаж.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЯ:

sposob_prodazhi: Как продают — прямая продажа на лендинге, запись на консультацию,
  список ожидания, бесплатный вебинар, пробный период и т.д.
est_ogranichenie: Есть ли ограничение по количеству мест, времени или цене. Значение: "да" или "нет".
  Если да — уточни кратко суть ограничения.
est_bonusy: Есть ли бонусы при покупке.
  Если да — перечисли КОНКРЕТНО что входит в бонусы (названия, описания).
  Если написано просто "бонусы" без расшифровки — вернуть "бонусы без расшифровки на странице".
  НЕ придумывай содержимое бонусов. Если бонусов нет — value "нет".
finalnyy_cta: Точный текст последней или финальной кнопки/призыва к действию на странице.
  Не cookie-баннеры. Если не определяется — "".

ПРАВИЛА:
1. Только то что явно есть в тексте.
2. Не определяется → data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явная цитата, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "sposob_prodazhi":  {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_ogranichenie": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "est_bonusy":       {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"},
  "finalnyy_cta":     {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""

SYSTEM_G7_CREATIVE = """\
Ты — аналитик маркетинговых лендингов. Перед тобой текст лендинга (browser inner_text).
Твоя задача — найти нестандартные, интересные или креативные решения.
Отвечай строго в JSON, без текста вне JSON.

ПОЛЕ:

neobychnye_resheniya: Что на этом лендинге сделано интересно, нестандартно или круто
  по сравнению с типичными лендингами онлайн-курсов.
  Искать:
  — нестандартный нейминг блоков (FAQ называется «Мы читаем мысли», поддержка — «Отдел заботы»)
  — юмор и неожиданные формулировки в заголовках и тексте
  — необычный формат отзывов (видео прямо на странице, карточки до/после с конкретными цифрами)
  — нестандартные элементы доверия (публичные провалы, антикейсы, честность о недостатках)
  — интерактивные или редкие технические решения
  — необычная структура или логика подачи материала
  Перечисляй найденное через «; ».
  Если ничего нестандартного нет — data_status "not_found", value "".

ПРАВИЛА:
1. Только то что явно есть в тексте. НЕ додумывай.
2. Не определяется / ничего нестандартного — data_status "not_found", value "".
3. Все ответы на русском.
4. confidence: "high" если явный факт из текста, "medium" если вывод, "low" если предположение.

ФОРМАТ (строго JSON):
{
  "neobychnye_resheniya": {"value": "...", "data_status": "ok|not_found", "confidence": "high|medium|low"}
}"""


_ALL_SYSTEMS = [
    ("G1 Vision", SYSTEM_G1_VISION),
    ("G2 Text — positioning", SYSTEM_G2_POSITIONING),
    ("G3 Text — trust", SYSTEM_G3_TRUST),
    ("G4 Text — pains", SYSTEM_G4_PAINS),
    ("G5 Text — product", SYSTEM_G5_PRODUCT),
    ("G6 Text — sales", SYSTEM_G6_SALES),
    ("G7 Text — creative", SYSTEM_G7_CREATIVE),
]


# ---------------------------------------------------------------------------
# User prompt builders
# ---------------------------------------------------------------------------

def _user_prompt_vision(url: str, destination_type: str) -> str:
    return (
        f"URL: {url}\n"
        f"Destination type: {destination_type}\n\n"
        "Проанализируй ПЕРВЫЙ экран лендинга по скриншоту. Отвечай только JSON."
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
# OpenAI call helpers
# ---------------------------------------------------------------------------

def _call_vision_g1(client, url: str, destination_type: str,
                    screenshots: list[Path], model: str) -> dict:
    """Vision pass G1: send only the first screenshot."""
    if not screenshots:
        return {"status": "skipped", "reason": "no screenshots", "fields": {}, "tokens_used": 0}

    first      = screenshots[0]
    text_part  = {"type": "text", "text": _user_prompt_vision(url, destination_type)}
    image_part = {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{_encode_image(first)}"}}

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS_G1,
            messages=[
                {"role": "system", "content": SYSTEM_G1_VISION},
                {"role": "user",   "content": [text_part, image_part]},
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
            "screenshot_used":  first.name,
        }
    except Exception as e:
        return {"status": "openai_error", "error": str(e), "fields": {}, "tokens_used": 0}


def _call_text_pass(client, system_prompt: str, url: str, destination_type: str,
                    full_text: str, model: str, max_tokens: int) -> dict:
    """Shared text pass helper — one focused OpenAI call per topic group."""
    if not full_text.strip():
        return {"status": "skipped", "reason": "empty text", "fields": {}, "tokens_used": 0}
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
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
# Field normalization
# ---------------------------------------------------------------------------

def _norm_field(raw: dict, key: str) -> dict:
    """Normalize a raw field entry to {value, data_status, confidence}."""
    entry = raw.get(key)
    if isinstance(entry, dict):
        return {
            "value":       str(entry.get("value") or ""),
            "data_status": entry.get("data_status") or "not_found",
            "confidence":  entry.get("confidence") or "low",
        }
    return {"value": "", "data_status": "not_found", "confidence": "low"}


def _collect_fields_new(pass_results: list[dict]) -> dict:
    """Merge all pass results into a single fields_new dict.
    Later passes override earlier ones. Exception: glavnyy_cta uses G1 as
    primary source; G2 is fallback only when G1 returned empty."""
    # Save G1 raw fields for glavnyy_cta priority logic
    g1_raw = (pass_results[0].get("fields") or {}) if pass_results else {}

    merged = {}
    for result in pass_results:
        raw = result.get("fields") or {}
        for key in _ALL_NEW_FIELDS:
            if key in raw:
                merged[key] = _norm_field(raw, key)
    # Ensure all new fields are present
    for key in _ALL_NEW_FIELDS:
        if key not in merged:
            merged[key] = {"value": "", "data_status": "not_found", "confidence": "low"}

    # G1 priority fields: Vision output wins over text passes when non-empty.
    # glavnyy_cta: G1 visual > G2 text fallback
    if "glavnyy_cta" in g1_raw:
        g1_cta = _norm_field(g1_raw, "glavnyy_cta")
        if g1_cta["value"]:
            merged["glavnyy_cta"] = g1_cta
    # otzyvy_format: G1 visual detection wins over G3 text (text can't see popups/visuals)
    if "otzyvy_format" in g1_raw:
        g1_otzyvy = _norm_field(g1_raw, "otzyvy_format")
        if g1_otzyvy["value"]:
            merged["otzyvy_format"] = g1_otzyvy

    return merged


def _map_to_legacy_fields(fields_new: dict) -> dict:
    """Synthesize legacy _ALL_FIELDS from new v3 fields for backward compat."""
    def gv(key: str) -> str:
        return (fields_new.get(key) or {}).get("value", "") or ""

    def gs(key: str) -> str:
        return (fields_new.get(key) or {}).get("data_status", "not_found")

    def mf(val: str) -> dict:
        return {"value": val, "data_status": "ok" if val else "not_found"}

    sots = "; ".join(filter(None, [gv(k) for k in ["cifry", "otzyvy_format", "keysy", "media", "sertifikaty"]]))

    obs_parts = []
    if gv("core_job"): obs_parts.append(f"Core Job: {gv('core_job')}")
    if gv("big_job"):  obs_parts.append(f"Big Job: {gv('big_job')}")
    obs = "; ".join(obs_parts)

    arg = "; ".join(filter(None, [gv("unikalnost"), gv("kak_sebya_nazyvayut")]))

    return {
        "chto_prodayut":         {"value": gv("nazvanie_produkta"), "data_status": gs("nazvanie_produkta")},
        "pervye_3_ekrana":       {"value": gv("vizualnyy_obraz"),    "data_status": gs("vizualnyy_obraz")},
        "glavnyy_zagolovok":     {"value": gv("glavnyy_zagolovok"), "data_status": gs("glavnyy_zagolovok")},
        "podzagolovok":          {"value": gv("podzagolovok"),       "data_status": gs("podzagolovok")},
        "dlya_kogo":             {"value": gv("dlya_kogo"),          "data_status": gs("dlya_kogo")},
        "obeshchanie_rezultata": mf(obs),
        "glavnyy_cta":           {"value": gv("glavnyy_cta"),        "data_status": gs("glavnyy_cta")},
        "sots_dokazatelstva":    mf(sots),
        "boli":                  {"value": gv("boli"),               "data_status": gs("boli")},
        "argumenty":             mf(arg),
        "bloki_dalshe":          {"value": gv("vizualnyy_obraz"),    "data_status": gs("vizualnyy_obraz")},
    }


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
    print(f"  max_screenshots:  {MAX_SCROLL_SCREENSHOTS} (unique; stops on 2x identical hash or no scroll progress)")
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
    print("PASS PLAN (6 passes):")
    print("=" * 60)
    print(f"  G1 Vision  — first screenshot only    — max_tokens={MAX_TOKENS_G1}  — {len(_FIELDS_G1)} fields")
    print(f"  G2 Text    — positioning               — max_tokens={MAX_TOKENS_G2}  — {len(_FIELDS_G2)} fields")
    print(f"  G3 Text    — trust signals             — max_tokens={MAX_TOKENS_G3} — {len(_FIELDS_G3)} fields")
    print(f"  G4 Text    — pains / objections / FAQ  — max_tokens={MAX_TOKENS_G4}  — {len(_FIELDS_G4)} fields")
    print(f"  G5 Text    — product description       — max_tokens={MAX_TOKENS_G5}  — {len(_FIELDS_G5)} fields")
    print(f"  G6 Text    — sales mechanics           — max_tokens={MAX_TOKENS_G6}  — {len(_FIELDS_G6)} fields")
    print(f"  G7 Text    — creative analysis         — max_tokens={MAX_TOKENS_G7}  — {len(_FIELDS_G7)} fields")
    print(f"  TOTAL new fields: {len(_ALL_NEW_FIELDS)}  |  Legacy compat fields: {len(_ALL_FIELDS)}")
    print()

    for label, system in _ALL_SYSTEMS:
        print("=" * 60)
        print(f"SYSTEM PROMPT — {label}:")
        print("=" * 60)
        print(system)
        print()

    print("=" * 60)
    print("USER PROMPT — G1 Vision (example):")
    print("=" * 60)
    print(_user_prompt_vision(url, destination_type))
    print("[+ 1 base64-encoded PNG: first screenshot only]")
    print()

    print("=" * 60)
    print("USER PROMPT — G2–G7 Text (example):")
    print("=" * 60)
    print(_user_prompt_text(url, destination_type, "(полный текст страницы — до 15000 символов)"))
    print()

    print("=" * 60)
    print("LEGACY FIELD MAPPING (fields_new → fields):")
    print("=" * 60)
    mapping_notes = [
        ("chto_prodayut",         "← nazvanie_produkta"),
        ("pervye_3_ekrana",       "← vizualnyy_obraz"),
        ("glavnyy_zagolovok",     "← glavnyy_zagolovok (direct)"),
        ("podzagolovok",          "← podzagolovok (direct)"),
        ("dlya_kogo",             "← dlya_kogo (direct)"),
        ("obeshchanie_rezultata", "← 'Core Job: {core_job}; Big Job: {big_job}'"),
        ("glavnyy_cta",           "← glavnyy_cta (direct)"),
        ("sots_dokazatelstva",    "← join(cifry; otzyvy_format; keysy; media; sertifikaty)"),
        ("boli",                  "← boli (direct)"),
        ("argumenty",             "← join(unikalnost; kak_sebya_nazyvayut)"),
        ("bloki_dalshe",          "← vizualnyy_obraz (reused)"),
    ]
    for field, note in mapping_notes:
        print(f"  {field:<25} {note}")
    print()

    print(f"Model:          {DEFAULT_MODEL}")
    print(f"max_tokens:     G1={MAX_TOKENS_G1}  G2={MAX_TOKENS_G2}  G3={MAX_TOKENS_G3}  G4={MAX_TOKENS_G4}  G5={MAX_TOKENS_G5}  G6={MAX_TOKENS_G6}  G7={MAX_TOKENS_G7}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2G v3: Landing Analyzer — Playwright scroll + 6-pass OpenAI"
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
    if not (api_key.startswith("sk-") or api_key.startswith("sk-proj-")):
        print("[ERROR] OPENAI_API_KEY looks invalid (must start with sk- or sk-proj-).")
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

    # ---- Pass G1: Vision (first screenshot only) ----
    if screenshots:
        print(f"G1 Vision ({args.model}) — first screenshot only...")
        g1 = _call_vision_g1(client, url, destination_type, screenshots, args.model)
        print(f"  G1: {g1['status']}  tokens: {g1.get('tokens_used', 0)}")
    else:
        print("[WARN] No screenshots — G1 Vision skipped")
        g1 = {"status": "skipped", "fields": {}, "tokens_used": 0}

    # ---- Passes G2–G7: Text (skip if SPA or empty) ----
    text_ok = bool(full_text.strip()) and not is_spa
    if not text_ok:
        reason = "SPA page" if is_spa else "empty text"
        print(f"[WARN] Text passes skipped ({reason}) — Vision-only")

    def _text_pass(label: str, system: str, max_tokens: int) -> dict:
        if not text_ok:
            return {"status": "skipped", "reason": "no text", "fields": {}, "tokens_used": 0}
        print(f"{label} ({args.model})...")
        result = _call_text_pass(client, system, url, destination_type, full_text, args.model, max_tokens)
        print(f"  {label}: {result['status']}  tokens: {result.get('tokens_used', 0)}")
        return result

    g2 = _text_pass("G2 Text — positioning",      SYSTEM_G2_POSITIONING, MAX_TOKENS_G2)
    g3 = _text_pass("G3 Text — trust",            SYSTEM_G3_TRUST,       MAX_TOKENS_G3)
    g4 = _text_pass("G4 Text — pains",            SYSTEM_G4_PAINS,       MAX_TOKENS_G4)
    g5 = _text_pass("G5 Text — product",          SYSTEM_G5_PRODUCT,     MAX_TOKENS_G5)
    g6 = _text_pass("G6 Text — sales",            SYSTEM_G6_SALES,       MAX_TOKENS_G6)
    g7 = _text_pass("G7 Text — creative",         SYSTEM_G7_CREATIVE,    MAX_TOKENS_G7)

    # Collect all passes
    all_passes   = [g1, g2, g3, g4, g5, g6, g7]
    fields_new   = _collect_fields_new(all_passes)
    fields       = _map_to_legacy_fields(fields_new)
    total_tokens = sum(p.get("tokens_used") or 0 for p in all_passes)

    pass_statuses = {
        "g1_vision":            g1.get("status"),
        "g2_text_positioning":  g2.get("status"),
        "g3_text_trust":        g3.get("status"),
        "g4_text_pains":        g4.get("status"),
        "g5_text_product":      g5.get("status"),
        "g6_text_sales":        g6.get("status"),
        "g7_text_creative":     g7.get("status"),
    }

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
        "pass_statuses":     pass_statuses,
        "tokens_used":       total_tokens,
        "fields_new":        fields_new,
        "fields":            fields,
    }
    if content.get("fetch_error"):
        output["fetch_error"] = content["fetch_error"]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    print(f"\nTotal tokens used: {total_tokens}")
    print(f"Pass statuses:     {pass_statuses}")

    print("\n=== Key Fields Summary ===")
    summary_keys = [
        ("glavnyy_zagolovok",     "Главный заголовок"),
        ("glavnyy_cta",           "Главный CTA"),
        ("dlya_kogo",             "Для кого"),
        ("core_job",              "Core Job"),
        ("big_job",               "Big Job"),
        ("cifry",                 "Цифры"),
        ("boli",                  "Боли"),
        ("nazvanie_produkta",     "Название продукта"),
        ("sposob_prodazhi",       "Способ продажи"),
        ("finalnyy_cta",          "Финальный CTA"),
    ]
    for key, label in summary_keys:
        f   = fields_new.get(key, {})
        val = (f.get("value") or "")[:80] or "(empty)"
        print(f"  {label:<25}: [{f.get('data_status', '?')}|{f.get('confidence', '?')}] {val}")


if __name__ == "__main__":
    main()
