"""Stage 5A-2E: Bio Semantic Analyzer.

Reads bio_text from data/normalized/profile_summary.json.
Sends bio text to OpenAI and extracts 4 semantic fields:
  - target_audience    (Для кого)
  - result_promise     (Обещание результата)
  - trust_arguments    (Аргументы доверия)
  - social_proof       (Социальные доказательства)

Usage:
    python3 scripts/stage5a2e_bio_semantic_analyzer.py --dry-run
    python3 scripts/stage5a2e_bio_semantic_analyzer.py
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

PROFILE_SUMMARY_PATH = NORM_DIR / "profile_summary.json"
OUTPUT_PATH          = NORM_DIR / "stage5a2e_bio_semantic.json"
STAGE          = "stage5a2e"
PROMPT_VERSION = "v6"
DEFAULT_MODEL  = "gpt-4o-mini"

RAW_PROFILE_PATH = BASE / "data" / ACCOUNT / "raw" / "stage5a1_profile_details_raw.json"


# ---------------------------------------------------------------------------
# Bio extraction
# ---------------------------------------------------------------------------

def _fix_profile_summary_bio(bio: str):
    """Patch bio_text.value in profile_summary.json with bio from raw."""
    try:
        data = json.loads(PROFILE_SUMMARY_PATH.read_text(encoding="utf-8"))
        raw = data.get("bio_text")
        if isinstance(raw, dict):
            data["bio_text"]["value"] = bio
            data["bio_text"]["data_status"] = "ok"
        else:
            data["bio_text"] = {"value": bio, "data_status": "ok", "source_ref": "raw_stage5a1"}
        PROFILE_SUMMARY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [INFO] profile_summary.json bio_text updated from raw (перенормализован)")
    except Exception as e:
        print(f"  [WARN] Could not patch profile_summary.json: {e}")


def load_bio_text() -> tuple[str, str | None]:
    """Return (bio_text, error_or_None).
    If profile_summary bio_text is empty, falls back to biography in raw stage5a1 file.
    On fallback success, auto-patches profile_summary.json (перенормализация).
    If nothing found, returns 'bio не доступно'.
    """
    bio = ""
    if PROFILE_SUMMARY_PATH.exists():
        try:
            data = json.loads(PROFILE_SUMMARY_PATH.read_text(encoding="utf-8"))
            raw = data.get("bio_text", {})
            if isinstance(raw, dict):
                bio = (raw.get("value") or "").strip()
            else:
                bio = str(raw).strip() if raw else ""
        except Exception as e:
            return "", f"Failed to parse profile_summary.json: {e}"
    else:
        return "", f"{PROFILE_SUMMARY_PATH.relative_to(BASE)} not found"

    if not bio:
        # Fallback: read biography directly from raw stage5a1 profile file
        if RAW_PROFILE_PATH.exists():
            try:
                raw_data = json.loads(RAW_PROFILE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw_data, list):
                    raw_data = raw_data[0] if raw_data else {}
                bio = (raw_data.get("biography") or raw_data.get("bio") or "").strip()
                if bio:
                    print(f"  [INFO] bio_text пуст в profile_summary — взят из raw ({RAW_PROFILE_PATH.name})")
                    _fix_profile_summary_bio(bio)
            except Exception as e:
                print(f"  [WARN] Could not read raw profile: {e}")

    if not bio:
        bio = "bio не доступно"
        print(f"  [WARN] biography не найден нигде — продолжаем с '{bio}'")

    return bio, None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик маркетинговых текстов. Тебе передают текст bio Instagram-аккаунта.
Твоя задача — извлечь ровно 8 полей из bio. Отвечай строго в JSON, без пояснений вне JSON.

ПРАВИЛА:
1. Не додумывай и не выводи информацию косвенно.
2. Если явного признака нет — data_status: "not_found", value: "".
3. Если признак есть, но неоднозначен — data_status: "inferred", value: "...", confidence: "low".
4. Если признак чёткий и явный — data_status: "ok", value: "...".
5. Добавляй поле notes с кратким объяснением решения (1 предложение).

ПОЛЯ:

niche (Ниша):
  Тематика деятельности в 2-4 словах по всему тексту bio.
  Формат: одно-два существительных или словосочетание.
  Примеры: "маркетинг", "SMM и контент", "онлайн-коучинг", "нутрициология".
  НЕ копируй первую строку bio дословно. Давай обобщённую тему.

target_audience (Для кого):
  Целевая аудитория. Приоритет:
  (1) явно написано в bio — бери дословно, data_status: "ok".
  (2) выводится из продукта/темы — пиши значение с префиксом "вероятно: " перед текстом, data_status: "inferred", confidence: "low".
  (3) совсем не ясно — value: "не определено", data_status: "not_found".
  Примеры: "маркетологи и эксперты" | "вероятно: предприниматели малого бизнеса".

result_promise (Обещание результата):
  Что человек получит или чем станет. Ищи:
  — глаголы результата: "научишься", "станешь", "получишь"
  — упоминание курса/продукта: из его названия выведи чему научит ("курс по маркетинговым стратегиям с AI" → "научиться создавать маркетинговые стратегии с помощью AI"). Это РАЗРЕШЁННЫЙ инференс.
  — косвенные обещания: "стратегии которые работают"
  ВАЖНО: одна и та же фраза может быть одновременно cta_text и result_promise — это не противоречие. Если фраза содержит название курса/продукта — извлекай из неё result_promise независимо от того попала ли она в cta_text.
  Если ничего — value: "не найдено", data_status: "not_found".
  НЕ считается: описание автора ("аналитически точные стратегии") — это позиционирование, не обещание клиенту.
  Пример OK: "научиться создавать маркетинговые стратегии с помощью AI".

positioning (Позиционирование):
  Кто этот человек — первая строка bio если она описательная, иначе самый ёмкий тезис.
  Приоритет: первая строка → самое описательное предложение.
  Примеры: "основатель маркетингового агентства", "эксперт по системному SMM".

trust_arguments (Аргументы доверия):
  Личные регалии и опыт: должности, места работы, годы опыта.
  Примеры OK: "основатель @elpodium_agency", "Ex-Head of SMM Refocus", "7 лет в маркетинге".
  НЕ считается: цифры достижений — даже если рядом с должностью (это social_proof).
  Если фраза содержит и должность и цифру ("Ex-Head of SMM: сделала выручку $1 млн") —
    trust_arguments получает только должность: "Ex-Head of SMM Refocus",
    social_proof получает только цифру: "сделала выручку $1 млн".

social_proof (Социальные доказательства):
  Анализируй ТОЛЬКО текст bio — не додумывай из контекста.
  ВАЖНО: должности и места работы — это trust_arguments, НЕ social_proof.
  Примеры которые НЕ являются соцдоком: "основатель агентства", "Ex-Head of SMM", "директор".
  Соцдок — только внешнее подтверждение: цифры результатов клиентов, упоминания СМИ, известные клиенты, награды.
  Найди все упоминания по пяти типам, перечисляй через ";":
  1. Цифры результатов: "$1 млн выручки", "200+ клиентов", "1500 учеников"
  2. Упоминания в СМИ: "Forbes писали", "VC.ru", "Тинькофф журнал"
  3. Известные клиенты: "работала с Nike", "клиенты: Сбер"
  4. Награды: "топ-10 SMM специалистов", "победитель конкурса"
  5. Верификации: "сертифицированный партнёр Meta"
  Если один факт подходит под несколько типов — пиши один раз, наиболее точный тип.
  Если ничего нет — value: "не найдено", data_status: "not_found".

cta_text (Призыв к действию):
  CTA — призыв к конкретному действию с глаголом или устойчивой конструкцией действия.
  Ищи: глагол-императив ("записывайся", "переходи", "систематизируй"), конструкции "занять место", "успеть записаться", "получить доступ".
  ВАЖНО: стрелка ↓ (👇 ⬇ ↓) сама по себе НЕ является CTA — она указывает на ссылку ниже.
  Если написано только "↓ название продукта" без глагола — это НЕ CTA, value: "не найдено".
  Если написано "переходи ↓" или "записывайся ↓" — это CTA.
  Записывай текст CTA дословно из bio (без ссылки — ссылка идёт в cta_destination).
  Если CTA не найден — value: "не найдено", data_status: "not_found".
  Пример OK: "Систематизируй SMM с помощью курса | занять место"
  Пример НЕ CTA: "↓ курс по маркетинговым стратегиям с AI" (только стрелка + название, нет глагола)

cta_destination (Куда ведёт CTA):
  Если в bio есть внешняя ссылка (http/https или ссылка вида @handle/linktree/taplink) — записывай её сюда.
  Записывай ссылку дословно как она указана в bio.
  Если ссылки нет — value: "", data_status: "not_found".

ФОРМАТ ОТВЕТА (строго JSON, никакого текста вне JSON):
{
  "niche":            {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "target_audience":  {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "result_promise":   {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "positioning":      {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "trust_arguments":  {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "social_proof":     {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "cta_text":         {"value": "...", "data_status": "ok|not_found", "notes": "..."},
  "cta_destination":  {"value": "...", "data_status": "ok|not_found", "notes": "..."}
}
Если data_status = "inferred" — добавь поле "confidence": "low" в тот же объект.
"""


def build_user_prompt(bio_text: str) -> str:
    return f"Bio текст Instagram-аккаунта:\n\n{bio_text}\n\nИзвлеки 8 полей строго по инструкции. Отвечай только JSON."


# ---------------------------------------------------------------------------
# OpenAI call
# ---------------------------------------------------------------------------

def _call_openai(client, bio_text: str, model: str) -> dict:
    """Call OpenAI and return parsed JSON result or error dict."""
    user_prompt = build_user_prompt(bio_text)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or ""
        parsed = json.loads(raw)
        return {"status": "ok", "fields": parsed, "tokens_used": response.usage.total_tokens}
    except json.JSONDecodeError as e:
        return {"status": "json_error", "error": str(e), "raw": raw}
    except Exception as e:
        return {"status": "openai_error", "error": str(e)}


# ---------------------------------------------------------------------------
# Output builder
# ---------------------------------------------------------------------------

_FIELD_META = {
    "niche":           {"source": "bio_text"},
    "target_audience": {"source": "bio_text"},
    "result_promise":  {"source": "bio_text"},
    "positioning":     {"source": "bio_text"},
    "trust_arguments": {"source": "bio_text"},
    "social_proof":    {"source": "bio_text"},
    "cta_text":        {"source": "bio_text"},
    "cta_destination": {"source": "bio_text"},
}

_ALL_FIELDS = list(_FIELD_META.keys())


def _enrich_field(key: str, raw: dict) -> dict:
    """Merge source metadata into a field dict."""
    result = {
        "value":       raw.get("value", ""),
        "data_status": raw.get("data_status", "not_found"),
        "source":      _FIELD_META[key]["source"],
        "notes":       raw.get("notes", ""),
    }
    if raw.get("data_status") == "inferred":
        result["confidence"] = raw.get("confidence", "low")
    return result


def build_output(bio_text: str, openai_result: dict) -> dict:
    fields_raw = openai_result.get("fields") or {}
    fields = {}
    for key in _ALL_FIELDS:
        raw = fields_raw.get(key) or {}
        fields[key] = _enrich_field(key, raw)

    return {
        "account":        ACCOUNT,
        "stage":          STAGE,
        "prompt_version": PROMPT_VERSION,
        "model":          DEFAULT_MODEL,
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "bio_text":       bio_text,
        "openai_status":  openai_result.get("status"),
        "tokens_used":    openai_result.get("tokens_used"),
        "fields":         fields,
    }


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def run_dry_run(bio_text: str):
    print("[DRY-RUN] OpenAI not called. No files will be written.\n")
    print("=" * 60)
    print("BIO TEXT:")
    print("=" * 60)
    print(bio_text)
    print()
    print("=" * 60)
    print("SYSTEM PROMPT (будет отправлен в OpenAI):")
    print("=" * 60)
    print(SYSTEM_PROMPT)
    print()
    print("=" * 60)
    print("USER PROMPT (будет отправлен в OpenAI):")
    print("=" * 60)
    print(build_user_prompt(bio_text))
    print()
    print(f"Model:          {DEFAULT_MODEL}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"Output path:    {OUTPUT_PATH.relative_to(BASE)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Stage 5A-2E: Bio Semantic Analyzer"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show bio_text and prompt; do NOT call OpenAI and do NOT write output",
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

    # Load bio text
    bio_text, err = load_bio_text()
    if err:
        if args.dry_run:
            # Use documented example bio when source file absent in dry-run
            bio_text = (
                "аналитически точные стратегии с опорой на цифры\n"
                "основатель @elpodium_agency \n"
                "каждый четверг-рубрика разборов \n"
                "↓ курс по маркетинговым стратегиям с AI"
            )
            print(f"[DRY-RUN] {err}")
            print("[DRY-RUN] Using documented example bio for prompt preview.\n")
        else:
            if OUTPUT_PATH.exists():
                print(f"[INFO] {err} — reusing existing {OUTPUT_PATH.name}")
                sys.exit(0)
            print(f"[ERROR] {err}")
            sys.exit(1)

    if args.dry_run:
        run_dry_run(bio_text)
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

    print(f"Calling OpenAI ({args.model}) for bio semantic analysis...")
    result = _call_openai(client, bio_text, model=args.model)

    if result["status"] not in ("ok",):
        print(f"[ERROR] OpenAI call failed: {result.get('error')}")
        sys.exit(1)

    output = build_output(bio_text, result)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Written: {OUTPUT_PATH.relative_to(BASE)}")

    # Print summary
    print("\n=== Field Summary ===")
    labels = {
        "niche":           "Ниша",
        "target_audience": "Для кого",
        "result_promise":  "Обещание результата",
        "positioning":     "Позиционирование",
        "trust_arguments": "Аргументы доверия",
        "social_proof":    "Социальные доказательства",
        "cta_text":        "CTA",
        "cta_destination": "Куда ведёт CTA",
    }
    for key, label in labels.items():
        f = output["fields"][key]
        status = f["data_status"]
        val    = f["value"] or "(empty)"
        print(f"  {label:<30}: [{status}] {val[:80]}")


if __name__ == "__main__":
    main()
