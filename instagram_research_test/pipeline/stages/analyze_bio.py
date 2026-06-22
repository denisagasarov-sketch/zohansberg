"""Stage 5A-2E: семантический анализ Instagram bio.

Стейдж читает profile_summary.json, извлекает восемь маркетинговых полей
через текстовый OpenAI-запрос и сохраняет stage5a2e_bio_semantic.json.

Использование:
  python3 -m pipeline.stages.analyze_bio --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_bio --account vlada_kliuiko
"""

import argparse
import json
import logging
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STAGE = "stage5a2e"
PROMPT_VERSION = "v6"
MODEL = "gpt-4o"

FIELD_NAMES = (
    "niche",
    "target_audience",
    "result_promise",
    "positioning",
    "trust_arguments",
    "social_proof",
    "cta_text",
    "cta_destination",
)

SYSTEM_PROMPT = """Ты — аналитик маркетинговых текстов. Извлеки ровно восемь
полей из bio Instagram-аккаунта и верни только валидный JSON без markdown.

Общие правила:
- не додумывай факты, которых нет во входных данных;
- явный факт: data_status="ok";
- обоснованный, но неявный вывод: data_status="inferred", confidence="low";
- отсутствующий признак: data_status="not_found", value="" или "не найдено";
- notes содержит одно короткое объяснение.

Поля:
- niche: обобщённая тема деятельности в 2–4 словах, не копия bio;
- target_audience: для кого работает автор; неясный вывод начинай с "вероятно:";
- result_promise: какой результат получает клиент, включая обещание из названия продукта;
- positioning: кто автор и чем отличается;
- trust_arguments: должности, регалии, опыт и места работы без цифр результатов;
- social_proof: цифры результатов, СМИ, известные клиенты, награды и верификации;
- cta_text: только явный призыв к действию; стрелка без глагола не является CTA;
- cta_destination: внешняя ссылка из входных данных, если она есть.

Не смешивай trust_arguments и social_proof. Одна фраза может одновременно
содержать result_promise и CTA. Если данных нет, не компенсируй это догадками.

Формат ответа:
{
  "niche": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "target_audience": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "result_promise": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "positioning": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "trust_arguments": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "social_proof": {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "cta_text": {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "cta_destination": {"value": "...", "data_status": "ok|not_found", "notes": "..."}
}
Для inferred добавляй "confidence": "low"."""


def _unwrap(field):
    if isinstance(field, dict):
        return field.get("value")
    return field


def _load_profile(username: str) -> tuple[str, str]:
    profile_path = normalized(username, "profile_summary.json")
    if not profile_path.exists():
        raise FileNotFoundError(
            f"Не найден {profile_path}. Сначала запустите collect_profile."
        )

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    bio_text = str(_unwrap(profile.get("bio_text")) or "").strip()
    external_url = str(_unwrap(profile.get("external_url")) or "").strip()
    if not bio_text:
        raise ValueError("bio_text отсутствует в profile_summary.json")
    return bio_text, external_url


def _build_user_prompt(bio_text: str, external_url: str) -> str:
    link = external_url or "не указана"
    return (
        "Bio текст Instagram-аккаунта:\n\n"
        f"{bio_text}\n\n"
        f"Внешняя ссылка профиля: {link}\n\n"
        "Извлеки восемь полей строго по инструкции."
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
    return parsed


def _enrich_field(raw_field) -> dict:
    raw_field = raw_field if isinstance(raw_field, dict) else {}
    status = raw_field.get("data_status", "not_found")
    if status not in {"ok", "not_found", "inferred"}:
        status = "not_found"
    result = {
        "value": raw_field.get("value", ""),
        "data_status": status,
        "source": "bio_text",
        "notes": raw_field.get("notes", ""),
    }
    if status == "inferred":
        result["confidence"] = "low"
    return result


def analyze(username: str, dry_run: bool = False) -> dict:
    """Анализирует bio и возвращает совместимый stage5a2e JSON."""
    get_account(username)
    bio_text, external_url = _load_profile(username)
    user_prompt = _build_user_prompt(bio_text, external_url)

    logger.info("[5A-2E] analyze_bio | @%s | dry_run=%s", username, dry_run)
    if dry_run:
        logger.info("[DRY RUN] OpenAI не вызывается, файлы не записываются")
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "bio_text": bio_text,
            "external_url": external_url,
            "user_prompt": user_prompt,
        }

    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=MODEL,
        max_tokens=1800,
    )
    parsed = _parse_response(response)
    fields = {name: _enrich_field(parsed.get(name)) for name in FIELD_NAMES}

    output = {
        "account": username,
        "stage": STAGE,
        "prompt_version": PROMPT_VERSION,
        "model": MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bio_text": bio_text,
        "openai_status": "ok",
        "tokens_used": None,
        "fields": fields,
    }
    output_path = normalized(username, "stage5a2e_bio_semantic.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("Bio semantic analysis: %s", output_path)
    print(f"\n=== Stage 5A-2E: Bio Semantic | @{username} ===")
    for name in FIELD_NAMES:
        field = fields[name]
        print(f"{name}: [{field['data_status']}] {str(field['value'])[:80]}")
    print(f"Сохранено: {output_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2E: analyze bio")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать OpenAI")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
