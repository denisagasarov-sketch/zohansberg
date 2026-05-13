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
PROMPT_VERSION = "v1"
DEFAULT_MODEL  = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Bio extraction
# ---------------------------------------------------------------------------

def load_bio_text() -> tuple[str, str | None]:
    """Return (bio_text, error_or_None)."""
    if not PROFILE_SUMMARY_PATH.exists():
        return "", f"{PROFILE_SUMMARY_PATH.relative_to(BASE)} not found"
    try:
        data = json.loads(PROFILE_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return "", f"Failed to parse profile_summary.json: {e}"

    raw = data.get("bio_text", {})
    if isinstance(raw, dict):
        bio = raw.get("value") or ""
    else:
        bio = str(raw) if raw else ""

    if not bio:
        return "", "bio_text.value is empty in profile_summary.json"
    return bio, None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Ты — аналитик маркетинговых текстов. Тебе передают текст bio Instagram-аккаунта.
Твоя задача — извлечь ровно 4 поля из bio. Отвечай строго в JSON, без пояснений вне JSON.

ПРАВИЛА:
1. Не додумывай и не выводи информацию косвенно.
2. Если явного признака нет — data_status: "not_found", value: "".
3. Если признак есть, но неоднозначен — data_status: "inferred", value: "...", confidence: "low".
4. Если признак чёткий и явный — data_status: "ok", value: "...".
5. Добавляй поле notes с кратким объяснением решения (1 предложение).

ПОЛЯ:

target_audience (Для кого):
  Считается: явные маркеры — "для", "если ты", слова типа "маркетологам", "экспертам", "предпринимателям".
  НЕ считается: тема или продукт ("курс по маркетингу") без явного указания аудитории.
  Пример OK:    "для маркетологов и владельцев бизнеса"
  Пример НЕЛЬЗЯ: выводить "маркетологи" из "курс по маркетинговым стратегиям"

result_promise (Обещание результата):
  Считается: явное обещание клиенту — "получишь", "твой результат", "за X недель/уроков".
  НЕ считается: позиционирование автора ("аналитически точные стратегии") — это про автора, не про результат клиента.
  Пример OK:    "за 4 недели выстроишь стратегию"
  Пример НЕЛЬЗЯ: "аналитически точные стратегии" → это не обещание клиенту

trust_arguments (Аргументы доверия):
  Считается: должность, роль, упоминание компании/агентства, опыт, основатель.
  НЕ считается: цифры продаж, отзывы клиентов (это social_proof).
  Пример OK:    "основатель @elpodium_agency"
  Пример OK:    "8 лет в маркетинге"

social_proof (Социальные доказательства):
  Считается: цифры (N клиентов, N кейсов, N% рост), явные результаты клиентов, отзывы.
  НЕ считается: должность или роль автора (это trust_arguments).
  Пример OK:    "помогла 200+ клиентам"
  Пример НЕЛЬЗЯ: "основатель агентства" → это не социальное доказательство

ФОРМАТ ОТВЕТА (строго JSON, никакого текста вне JSON):
{
  "target_audience":  {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "result_promise":   {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "trust_arguments":  {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."},
  "social_proof":     {"value": "...", "data_status": "ok|not_found|inferred", "notes": "..."}
}
Если data_status = "inferred" — добавь поле "confidence": "low" в тот же объект.
"""


def build_user_prompt(bio_text: str) -> str:
    return f"Bio текст Instagram-аккаунта:\n\n{bio_text}\n\nИзвлеки 4 поля строго по инструкции. Отвечай только JSON."


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
    "target_audience": {"source": "bio_text"},
    "result_promise":  {"source": "bio_text"},
    "trust_arguments": {"source": "bio_text"},
    "social_proof":    {"source": "bio_text"},
}


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
    for key in ("target_audience", "result_promise", "trust_arguments", "social_proof"):
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
        "target_audience": "Для кого",
        "result_promise":  "Обещание результата",
        "trust_arguments": "Аргументы доверия",
        "social_proof":    "Социальные доказательства",
    }
    for key, label in labels.items():
        f = output["fields"][key]
        status = f["data_status"]
        val    = f["value"] or "(empty)"
        print(f"  {label:<30}: [{status}] {val[:80]}")


if __name__ == "__main__":
    main()
