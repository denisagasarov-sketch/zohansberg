"""Stage 5A-2F: классификация внешней ссылки Instagram-профиля.

Стейдж загружает страницу, применяет доменные эвристики и при необходимости
классифицирует назначение через OpenAI.

Использование:
  python3 -m pipeline.stages.classify_profile_link --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.classify_profile_link --account vlada_kliuiko
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
PROMPT_VERSION = "v1"
UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"}
DESTINATION_TYPES = {
    "лендинг_курса", "лендинг_консультации", "лендинг_агентства",
    "лендинг_продукта", "taplink", "бот", "telegram_канал", "анкета",
    "мультиссылка", "сайт", "неизвестно",
}

SYSTEM_PROMPT = """Ты классифицируешь страницу по ссылке из Instagram bio.
Верни только JSON:
{
  "destination_type": "одна категория",
  "confidence": "high|medium|low",
  "reasoning": "одно предложение",
  "data_status": "ok|not_found"
}
Категории: лендинг_курса, лендинг_консультации, лендинг_агентства,
лендинг_продукта, taplink, бот, telegram_канал, анкета, мультиссылка, сайт,
неизвестно.
Курс/обучение/тренинг → лендинг_курса. Консультация/разбор/аудит →
лендинг_консультации. Услуги компании → лендинг_агентства. Если данных мало,
выбери «неизвестно». Не додумывай."""


class _MetaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.og_title = ""
        self.description = ""
        self.og_description = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attributes.get("name", "").lower()
            prop = attributes.get("property", "").lower()
            content = attributes.get("content", "")
            if name == "description":
                self.description = content
            elif prop == "og:title":
                self.og_title = content
            elif prop == "og:description":
                self.og_description = content

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def _unwrap(field):
    if isinstance(field, dict):
        return field.get("value")
    return field


def _load_url(username: str) -> str:
    profile_path = normalized(username, "profile_summary.json")
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Не найден {profile_path}. Сначала запустите collect_profile."
        )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    url = str(_unwrap(profile.get("external_url")) or "").strip()
    if not url:
        raise ValueError("external_url отсутствует в profile_summary.json")
    return url


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {key: value for key, value in query.items() if key.lower() not in UTM_PARAMS}
    return urlunparse(parsed._replace(query=urlencode(filtered, doseq=True)))


def _heuristic(url: str) -> str | None:
    parsed = urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")
    path = parsed.path.lower()
    if domain in {"taplink.ru", "tap.link"}:
        return "taplink"
    if domain in {"forms.gle", "typeform.com", "tally.so"}:
        return "анкета"
    if domain in {"mssg.me", "linktr.ee", "beacons.ai"}:
        return "мультиссылка"
    if domain == "t.me":
        return "бот" if "bot" in path else "telegram_канал"
    return None


def _fetch(url: str) -> dict:
    response = requests.get(
        url,
        timeout=20,
        allow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0 AppleWebKit/537.36"},
    )
    final_url = response.url
    redirected = final_url.rstrip("/") != url.rstrip("/")
    if response.status_code != 200:
        return {
            "status": "fetch_failed",
            "fetch_status": response.status_code,
            "final_url": final_url,
            "redirected": redirected,
        }

    parser = _MetaParser()
    parser.feed(response.text)
    server = response.headers.get("server", "")
    tilda = response.headers.get("x-tilda-server", "")
    server_hint = "tilda" if tilda or "tilda" in server.lower() else server.split("/")[0].lower()
    return {
        "status": "ok",
        "fetch_status": response.status_code,
        "final_url": final_url,
        "redirected": redirected,
        "title": parser.title.strip(),
        "og_title": parser.og_title.strip(),
        "description": (parser.description or parser.og_description).strip(),
        "server_hint": server_hint,
    }


def _build_prompt(fetch: dict) -> str:
    return (
        f"URL: {fetch.get('final_url', '')}\n"
        f"Title: {fetch.get('title', '')}\n"
        f"OG Title: {fetch.get('og_title', '')}\n"
        f"Description: {fetch.get('description', '')}\n"
        f"Server: {fetch.get('server_hint', '')}\n\n"
        "Определи тип страницы."
    )


def _parse_response(response: str) -> dict:
    stripped = response.strip()
    if stripped.startswith("```"):
        stripped = "\n".join(
            line for line in stripped.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Ответ OpenAI должен быть JSON-объектом")
    destination_type = parsed.get("destination_type")
    if destination_type not in DESTINATION_TYPES:
        destination_type = "неизвестно"
    confidence = parsed.get("confidence")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"
    return {
        "destination_type": destination_type,
        "confidence": confidence,
        "reasoning": str(parsed.get("reasoning") or "")[:300],
        "data_status": parsed.get("data_status")
        if parsed.get("data_status") in {"ok", "not_found"} else "not_found",
    }


def classify(username: str, dry_run: bool = False) -> dict:
    """Классифицирует назначение внешней ссылки профиля."""
    get_account(username)
    url_input = _load_url(username)
    url_clean = _clean_url(url_input)
    logger.info("[5A-2F] classify_profile_link | @%s | dry_run=%s", username, dry_run)

    if dry_run:
        logger.info("[DRY RUN] HTTP и OpenAI не вызываются, файлы не записываются")
        return {
            "dry_run": True,
            "account": username,
            "url_input": url_input,
            "url_clean": url_clean,
            "heuristic_preview": _heuristic(url_clean),
            "planned_http_calls": 1,
            "actual_http_calls": 0,
            "actual_openai_calls": 0,
        }

    try:
        fetch = _fetch(url_input)
    except Exception as error:
        fetch = {
            "status": "fetch_failed",
            "fetch_status": None,
            "final_url": url_input,
            "redirected": False,
            "error": str(error),
        }

    final_url = fetch.get("final_url", url_input)
    if fetch["status"] == "fetch_failed":
        method = None
        result = {
            "destination_type": "неизвестно",
            "confidence": "low",
            "reasoning": f"Страница недоступна: {fetch.get('fetch_status') or fetch.get('error')}",
            "data_status": "fetch_failed",
        }
    else:
        heuristic = _heuristic(final_url)
        if heuristic:
            method = "heuristic"
            result = {
                "destination_type": heuristic,
                "confidence": "high",
                "reasoning": f"Домен соответствует правилу {heuristic}",
                "data_status": "ok",
            }
        else:
            method = "openai"
            response = chat(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_prompt(fetch)},
                ],
                model=MODEL,
                max_tokens=400,
            )
            result = _parse_response(response)

    output = {
        "account": username,
        "stage": "stage5a2f",
        "prompt_version": PROMPT_VERSION,
        "url_input": url_input,
        "url_clean": url_clean,
        "url_final": final_url,
        "fetch_status": fetch.get("fetch_status"),
        "redirected": fetch.get("redirected", False),
        "title": fetch.get("title", ""),
        "og_title": fetch.get("og_title", ""),
        "description": fetch.get("description", ""),
        "server_hint": fetch.get("server_hint", ""),
        "classification_method": method,
        "tokens_used": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    output_path = normalized(username, "stage5a2f_link_destination.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n=== Stage 5A-2F: Link Destination | @{username} ===")
    print(f"Тип: {result['destination_type']} | метод: {method or 'fetch_failed'}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2F: classify profile link")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не делать HTTP-запрос")
    args = parser.parse_args()
    classify(args.account, args.dry_run)
