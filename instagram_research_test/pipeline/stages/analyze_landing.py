"""Stage 5A-2G: многошаговый анализ лендинга из Instagram bio.

Playwright собирает текст и скриншоты страницы. Первый экран анализируется
через Vision, остальные смысловые группы — отдельными текстовыми проходами.

Использование:
  python3 -m pipeline.stages.analyze_landing --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_landing --account vlada_kliuiko
"""

import argparse
import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat, vision
from pipeline.core.paths import normalized, tmp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
PROMPT_VERSION = "v3"
MAX_SCREENSHOTS = 10
MAX_TEXT_CHARS = 15000

PASS_SPECS = (
    ("g2_text_positioning", (
        "kak_sebya_nazyvayut", "dlya_kogo", "core_job", "big_job", "unikalnost",
    )),
    ("g3_text_trust", (
        "cifry", "otzyvy_format", "keysy", "media", "sertifikaty",
    )),
    ("g4_text_pains", ("boli", "vozrazheniya", "est_faq")),
    ("g5_text_product", (
        "nazvanie_produkta", "format", "dlitelnost", "chto_vkhodit",
        "est_tarify", "est_rassrochka", "est_garantiya",
    )),
    ("g6_text_sales", (
        "sposob_prodazhi", "est_ogranichenie", "est_bonusy", "finalnyy_cta",
    )),
    ("g7_text_creative", ("neobychnye_resheniya",)),
)
VISION_FIELDS = (
    "glavnyy_zagolovok", "podzagolovok", "vizualnyy_obraz",
    "glavnyy_cta", "est_dedlayn",
)
ALL_NEW_FIELDS = VISION_FIELDS + tuple(
    field for _, fields in PASS_SPECS for field in fields
)


def _field(value: str = "", status: str = "not_found", confidence: str = "low") -> dict:
    return {
        "value": str(value or ""),
        "data_status": status if status in {"ok", "not_found", "inferred", "not_applicable"}
        else "not_found",
        "confidence": confidence if confidence in {"high", "medium", "low"} else "low",
    }


def _load_input(username: str) -> tuple[str, str]:
    input_path = normalized(username, "stage5a2f_link_destination.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Не найден {input_path}. Сначала запустите classify_profile_link."
        )
    data = json.loads(input_path.read_text(encoding="utf-8"))
    url = data.get("url_clean") or data.get("url_final") or data.get("url_input") or ""
    destination_type = (data.get("result") or {}).get("destination_type") or "неизвестно"
    if not url:
        raise ValueError("В stage5a2f_link_destination.json отсутствует URL")
    return url, destination_type


def _fetch_page(username: str, url: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise RuntimeError(
            "playwright не установлен: pip install playwright && playwright install chromium"
        ) from error

    screenshot_dir = tmp(username, "landing")
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshots = []
    previous_hash = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 AppleWebKit/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        for index in range(MAX_SCREENSHOTS):
            image_bytes = page.screenshot(full_page=False)
            image_hash = hashlib.md5(image_bytes).hexdigest()
            if image_hash == previous_hash:
                break
            screenshot_path = screenshot_dir / f"screen_{index + 1}.png"
            screenshot_path.write_bytes(image_bytes)
            screenshots.append(screenshot_path)
            previous_hash = image_hash

            scroll_before = page.evaluate("window.scrollY")
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(700)
            if page.evaluate("window.scrollY") == scroll_before:
                break

        full_text = page.inner_text("body")[:MAX_TEXT_CHARS]
        browser.close()

    return {
        "fetch_success": True,
        "screenshots": screenshots,
        "screenshot_dir": screenshot_dir,
        "full_text": full_text,
        "text_length": len(full_text),
        "is_spa": len(full_text.strip()) < 200,
    }


def _parse_json(response: str) -> dict:
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = "\n".join(
            line for line in stripped.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Ответ модели должен быть JSON-объектом")
    return parsed


def _field_schema(fields: tuple[str, ...]) -> str:
    return json.dumps(
        {
            name: {
                "value": "наблюдение или пустая строка",
                "data_status": "ok|not_found|inferred",
                "confidence": "high|medium|low",
            }
            for name in fields
        },
        ensure_ascii=False,
        indent=2,
    )


def _normalize_fields(raw: dict, expected: tuple[str, ...]) -> dict:
    result = {}
    for name in expected:
        entry = raw.get(name) if isinstance(raw.get(name), dict) else {}
        result[name] = _field(
            entry.get("value", ""),
            entry.get("data_status", "not_found"),
            entry.get("confidence", "low"),
        )
    return result


def _run_vision_pass(url: str, destination_type: str, screenshot_path) -> dict:
    image_b64 = base64.b64encode(screenshot_path.read_bytes()).decode("ascii")
    prompt = f"""Проанализируй только первый экран лендинга.
URL: {url}
Тип назначения: {destination_type}
Не додумывай элементы ниже первого экрана. Верни только JSON по схеме:
{_field_schema(VISION_FIELDS)}"""
    parsed = _parse_json(
        vision([{"b64": image_b64, "detail": "low"}], prompt, model=MODEL, max_tokens=900)
    )
    return _normalize_fields(parsed, VISION_FIELDS)


def _run_text_pass(
    pass_name: str,
    expected: tuple[str, ...],
    url: str,
    destination_type: str,
    full_text: str,
) -> dict:
    system_prompt = f"""Ты анализируешь текст лендинга. Проход: {pass_name}.
Извлекай только факты, поддержанные текстом. Пустое поле отмечай not_found.
Верни только JSON по схеме:
{_field_schema(expected)}"""
    user_prompt = (
        f"URL: {url}\nТип: {destination_type}\n\n"
        f"=== ТЕКСТ СТРАНИЦЫ ===\n{full_text}\n=== КОНЕЦ ==="
    )
    parsed = _parse_json(
        chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL,
            max_tokens=1600,
        )
    )
    return _normalize_fields(parsed, expected)


def _legacy_fields(fields_new: dict) -> dict:
    def value(name: str) -> str:
        return fields_new.get(name, {}).get("value", "")

    def status(name: str) -> str:
        return fields_new.get(name, {}).get("data_status", "not_found")

    def combined(names: tuple[str, ...]) -> dict:
        text = "; ".join(filter(None, (value(name) for name in names)))
        return {"value": text, "data_status": "ok" if text else "not_found"}

    jobs = []
    if value("core_job"):
        jobs.append(f"Core Job: {value('core_job')}")
    if value("big_job"):
        jobs.append(f"Big Job: {value('big_job')}")

    return {
        "chto_prodayut": {"value": value("nazvanie_produkta"), "data_status": status("nazvanie_produkta")},
        "pervye_3_ekrana": {"value": value("vizualnyy_obraz"), "data_status": status("vizualnyy_obraz")},
        "glavnyy_zagolovok": {"value": value("glavnyy_zagolovok"), "data_status": status("glavnyy_zagolovok")},
        "podzagolovok": {"value": value("podzagolovok"), "data_status": status("podzagolovok")},
        "dlya_kogo": {"value": value("dlya_kogo"), "data_status": status("dlya_kogo")},
        "obeshchanie_rezultata": {
            "value": "; ".join(jobs),
            "data_status": "ok" if jobs else "not_found",
        },
        "glavnyy_cta": {"value": value("glavnyy_cta"), "data_status": status("glavnyy_cta")},
        "sots_dokazatelstva": combined(("cifry", "otzyvy_format", "keysy", "media", "sertifikaty")),
        "boli": {"value": value("boli"), "data_status": status("boli")},
        "argumenty": combined(("unikalnost", "kak_sebya_nazyvayut")),
        "bloki_dalshe": {"value": value("vizualnyy_obraz"), "data_status": status("vizualnyy_obraz")},
    }


def _bot_output(username: str, url: str) -> dict:
    fields_new = {
        name: _field("", "not_applicable", "low") for name in ALL_NEW_FIELDS
    }
    return {
        "account": username,
        "stage": "stage5a2g",
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "destination_type": "бот",
        "fetch_success": True,
        "text_length": 0,
        "is_spa": False,
        "screenshots_taken": 0,
        "screenshots_dir": "",
        "pass_statuses": {"g1_vision": "skipped_bot", **{
            name: "skipped_bot" for name, _ in PASS_SPECS
        }},
        "tokens_used": None,
        "fields_new": fields_new,
        "fields": _legacy_fields(fields_new),
    }


def analyze(username: str, dry_run: bool = False) -> dict:
    """Собирает страницу и выполняет многошаговый анализ лендинга."""
    get_account(username)
    url, destination_type = _load_input(username)
    logger.info(
        "[5A-2G] analyze_landing | @%s | type=%s | dry_run=%s",
        username,
        destination_type,
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] Playwright и OpenAI не запускаются")
        return {
            "dry_run": True,
            "account": username,
            "url": url,
            "destination_type": destination_type,
            "max_screenshots": MAX_SCREENSHOTS,
            "text_limit": MAX_TEXT_CHARS,
            "planned_passes": ["g1_vision", *[name for name, _ in PASS_SPECS]],
            "actual_openai_calls": 0,
        }

    if destination_type == "бот":
        output = _bot_output(username, url)
    else:
        try:
            content = _fetch_page(username, url)
        except Exception as error:
            content = {
                "fetch_success": False,
                "fetch_error": str(error),
                "screenshots": [],
                "screenshot_dir": tmp(username, "landing"),
                "full_text": "",
                "text_length": 0,
                "is_spa": False,
            }

        fields_new = {name: _field() for name in ALL_NEW_FIELDS}
        pass_statuses = {}
        screenshots = content.get("screenshots", [])
        if screenshots:
            try:
                fields_new.update(_run_vision_pass(url, destination_type, screenshots[0]))
                pass_statuses["g1_vision"] = "ok"
            except Exception as error:
                logger.error("G1 Vision failed: %s", error)
                pass_statuses["g1_vision"] = "error"
        else:
            pass_statuses["g1_vision"] = "skipped"

        full_text = content.get("full_text", "")
        text_available = bool(full_text.strip()) and not content.get("is_spa")
        for pass_name, expected in PASS_SPECS:
            if text_available:
                try:
                    fields_new.update(
                        _run_text_pass(pass_name, expected, url, destination_type, full_text)
                    )
                    pass_statuses[pass_name] = "ok"
                except Exception as error:
                    logger.error("%s failed: %s", pass_name, error)
                    pass_statuses[pass_name] = "error"
            else:
                pass_statuses[pass_name] = "skipped"

        screenshot_dir = content.get("screenshot_dir") or tmp(username, "landing")
        output = {
            "account": username,
            "stage": "stage5a2g",
            "prompt_version": PROMPT_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "destination_type": destination_type,
            "fetch_success": content.get("fetch_success", False),
            "text_length": content.get("text_length", len(full_text)),
            "is_spa": content.get("is_spa", False),
            "screenshots_taken": len(screenshots),
            "screenshots_dir": str(screenshot_dir.relative_to(screenshot_dir.parents[3])),
            "pass_statuses": pass_statuses,
            "tokens_used": None,
            "fields_new": fields_new,
            "fields": _legacy_fields(fields_new),
        }
        if content.get("fetch_error"):
            output["fetch_error"] = content["fetch_error"]

    output_path = normalized(username, "stage5a2g_landing_analysis.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n=== Stage 5A-2G: Landing Analysis | @{username} ===")
    print(f"Тип: {destination_type} | fetch: {output['fetch_success']}")
    print(f"Проходы: {output['pass_statuses']}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2G: analyze landing")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не запускать Playwright")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
