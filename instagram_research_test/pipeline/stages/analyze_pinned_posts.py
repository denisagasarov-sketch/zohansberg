"""Stage 5A-2C: семантический анализ подписей закреплённых постов.

Стейдж читает stage5a2b_pinned_posts_details.json, анализирует каждый caption
через OpenAI и готовит совместимые строки листа «Закрепленные посты».

Использование:
  python3 -m pipeline.stages.analyze_pinned_posts --account vlada_kliuiko --dry-run
  python3 -m pipeline.stages.analyze_pinned_posts --account vlada_kliuiko
"""

import argparse
import json
import logging
import re
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
PROMPT_VERSION = "v4"

SEMANTIC_FIELDS = (
    "Тема поста",
    "Почему закреплен",
    "Хук / первый экран",
    "Что в тексте поста",
    "Ключевые смыслы",
    "Какой CTA",
    "Куда ведет CTA",
    "Роль в воронке",
)
HEADERS = (
    "Конкурент",
    "Ссылка на пост",
    "Позиция закрепа",
    *SEMANTIC_FIELDS,
)
FUNNEL_ROLES = {"знакомство", "доверие", "прогрев", "продажа", "лидогенерация"}
CTA_DESTINATIONS = {
    "директ", "комментарии", "био-ссылка", "анкета", "анкета предзаписи",
    "закрытый канал", "консультация", "курс", "сайт", "бот", "unknown",
}
CTA_ACTION_RE = re.compile(
    r"\b(?:пиши(?:те)?|напиши(?:те)?|оставь(?:те)?|перейди(?:те)?|переходи(?:те)?|"
    r"заполни(?:те)?|запишись|запишитесь|подпишись|подпишитесь|скачай(?:те)?|"
    r"узнай(?:те)?|нажми(?:те)?|получи(?:те)?)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """Ты анализируешь только текст подписи закреплённого Instagram-поста.
Не используй визуальные догадки. Верни только валидный JSON без markdown.

Правила:
- «Почему закреплен» — конкретный стратегический инференс, начинающийся с «Вероятно»;
- «Хук / первый экран» — дословная первая строка/абзац caption, максимум 250 символов;
- «Ключевые смыслы» — краткая цепочка боль → причина → оффер → соцдоки → CTA,
  отсутствующие элементы пропускай;
- CTA существует только при явном глаголе действия; иначе CTA и destination пустые;
- destination использует только: директ, комментарии, био-ссылка, анкета,
  анкета предзаписи, закрытый канал, консультация, курс, сайт, бот, unknown;
- роль в воронке использует только: знакомство, доверие, прогрев, продажа,
  лидогенерация; составные роли разделяй через « / »;
- ничего не выдумывай сверх caption.

Формат:
{
  "Тема поста": "...",
  "Почему закреплен": "Вероятно, ...",
  "Хук / первый экран": "...",
  "Что в тексте поста": "...",
  "Ключевые смыслы": "...",
  "Какой CTA": "... или пустая строка",
  "Куда ведет CTA": "... или пустая строка",
  "Роль в воронке": "...",
  "confidence": {"название поля": "high|medium|low"},
  "evidence": {"caption_quotes": [], "cta_quotes": [], "source_notes": []},
  "limitations": []
}"""


def _load_posts(username: str) -> list[dict]:
    input_path = normalized(username, "stage5a2b_pinned_posts_details.json")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Не найден {input_path}. Сначала запустите collect_pinned_details."
        )
    data = json.loads(input_path.read_text(encoding="utf-8"))
    posts = data.get("posts") or []
    if not posts:
        raise ValueError("В stage5a2b_pinned_posts_details.json нет постов")
    for post in posts:
        if not (post.get("full_caption") or post.get("caption_for_analysis")):
            raise ValueError(f"У закрепа {post.get('position')} отсутствует caption")
    return posts


def _build_prompt(post: dict) -> str:
    caption = post.get("full_caption") or post.get("caption_for_analysis") or ""
    return f"""Закреплённый пост #{post.get('position')}.
Тип: {post.get('media_type') or 'неизвестно'}.
Ссылка: {post.get('permalink') or ''}.

=== CAPTION ===
{caption}
=== END CAPTION ===

Заполни JSON строго по инструкции."""


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


def _normalize_role(value: str) -> str:
    roles = [part.strip().lower() for part in re.split(r"[/,]", value or "")]
    return " / ".join(role for role in roles if role in FUNNEL_ROLES)


def _normalize_destination(value: str) -> str:
    chunks = re.split(r"\s*(?:→|->|=>)\s*", value or "")
    normalized_chunks = []
    for chunk in chunks:
        parts = [part.strip().lower() for part in re.split(r"[/|]", chunk)]
        valid = [part for part in parts if part in CTA_DESTINATIONS]
        if valid:
            normalized_chunks.append(" / ".join(valid))
    return " → ".join(normalized_chunks)


def _normalize_fields(raw: dict, caption: str) -> tuple[dict, list[str]]:
    fields = {name: str(raw.get(name) or "").strip() for name in SEMANTIC_FIELDS}
    notes = []

    if not fields["Почему закреплен"].lower().startswith("вероятно"):
        fields["Почему закреплен"] = (
            f"Вероятно, {fields['Почему закреплен'].lstrip('., ')}"
            if fields["Почему закреплен"] else "Вероятно, закреп отражает ключевую роль поста."
        )
        notes.append("Добавлен маркер инференса в поле «Почему закреплен»")

    first_paragraph = next(
        (part.strip() for part in re.split(r"\n\s*\n|\n", caption) if part.strip()),
        "",
    )[:250]
    hook = fields["Хук / первый экран"]
    if not hook or hook not in caption:
        fields["Хук / первый экран"] = first_paragraph
        notes.append("Хук восстановлен дословно из начала caption")

    cta = fields["Какой CTA"]
    if cta and not CTA_ACTION_RE.search(cta):
        fields["Какой CTA"] = ""
        fields["Куда ведет CTA"] = ""
        notes.append("Удалён CTA без явного глагола действия")
    elif not cta:
        fields["Куда ведет CTA"] = ""
    else:
        fields["Куда ведет CTA"] = _normalize_destination(fields["Куда ведет CTA"])

    fields["Роль в воронке"] = _normalize_role(fields["Роль в воронке"])
    limits = {
        "Тема поста": 160,
        "Почему закреплен": 250,
        "Хук / первый экран": 250,
        "Что в тексте поста": 350,
        "Ключевые смыслы": 500,
        "Какой CTA": 180,
    }
    for field, limit in limits.items():
        fields[field] = fields[field][:limit]
    return fields, notes


def _semantic_post(post: dict, parsed: dict) -> dict:
    caption = post.get("full_caption") or post.get("caption_for_analysis") or ""
    fields, postprocessing_notes = _normalize_fields(parsed, caption)
    confidence_raw = parsed.get("confidence") if isinstance(parsed.get("confidence"), dict) else {}
    confidence = {
        field: confidence_raw.get(field, "low")
        if confidence_raw.get(field) in {"high", "medium", "low"} else "low"
        for field in SEMANTIC_FIELDS
    }
    evidence = parsed.get("evidence") if isinstance(parsed.get("evidence"), dict) else {}
    return {
        "position": post.get("position"),
        "permalink": post.get("permalink"),
        "shortcode": post.get("shortcode"),
        "post_id": post.get("post_id"),
        "caption_length": len(caption),
        "media_type": post.get("media_type"),
        "source": "caption_only",
        "visual_analyzed": False,
        "ocr_analyzed": False,
        "cache_status": "disabled",
        "tokens_used": None,
        "openai_status": "analyzed",
        "google_sheet_fields": fields,
        "confidence": confidence,
        "evidence": {
            "caption_quotes": evidence.get("caption_quotes", []),
            "cta_quotes": evidence.get("cta_quotes", []),
            "source_notes": evidence.get("source_notes", []),
        },
        "limitations": parsed.get("limitations", []),
        "validation_warnings": [],
        "postprocessing_notes": postprocessing_notes,
    }


def _sheet_output(username: str, semantic_posts: list[dict]) -> dict:
    rows_as_dicts = []
    for post in semantic_posts:
        row = {
            "Конкурент": username,
            "Ссылка на пост": post.get("permalink") or "",
            "Позиция закрепа": str(post.get("position") or ""),
            **post["google_sheet_fields"],
        }
        rows_as_dicts.append(row)
    return {
        "sheet": "Закрепленные посты",
        "stage": "stage5a2c",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headers": list(HEADERS),
        "rows": [[str(row.get(header, "") or "") for header in HEADERS] for row in rows_as_dicts],
        "rows_as_dicts": rows_as_dicts,
        "integration_note": "Stage 5D should prefer this file for pinned post semantics.",
    }


def analyze(username: str, dry_run: bool = False) -> dict:
    """Анализирует captions закрепов и сохраняет semantic + sheet rows."""
    get_account(username)
    posts = _load_posts(username)
    logger.info(
        "[5A-2C] analyze_pinned_posts | @%s | posts=%d | dry_run=%s",
        username,
        len(posts),
        dry_run,
    )

    if dry_run:
        logger.info("[DRY RUN] OpenAI не вызывается, файлы не записываются")
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "posts_total": len(posts),
            "planned_openai_calls": len(posts),
            "actual_openai_calls": 0,
            "prompt_previews": [_build_prompt(post)[:500] for post in posts],
        }

    semantic_posts = []
    for post in posts:
        response = chat(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(post)},
            ],
            model=MODEL,
            max_tokens=1800,
        )
        semantic_posts.append(_semantic_post(post, _parse_response(response)))

    output = {
        "account": username,
        "stage": "stage5a2c",
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "total_posts": len(semantic_posts),
        "source": "caption_only",
        "visual_analyzed": False,
        "ocr_analyzed": False,
        "cache_summary": {"hits": 0, "new": len(semantic_posts), "failed": 0},
        "total_tokens_used": None,
        "estimated_cost_usd": None,
        "posts": semantic_posts,
    }
    sheet_output = _sheet_output(username, semantic_posts)

    semantic_path = normalized(username, "stage5a2c_pinned_posts_semantic.json")
    rows_path = normalized(username, "stage5a2c_pinned_posts_google_sheet_rows.json")
    fixed_path = normalized(username, "stage5a2c_pinned_posts_google_sheet_rows_fixed.json")
    semantic_path.parent.mkdir(parents=True, exist_ok=True)
    semantic_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    rows_json = json.dumps(sheet_output, ensure_ascii=False, indent=2)
    rows_path.write_text(rows_json, encoding="utf-8")
    fixed_path.write_text(rows_json, encoding="utf-8")

    print(f"\n=== Stage 5A-2C: Pinned Semantics | @{username} ===")
    print(f"Проанализировано: {len(semantic_posts)}")
    print(f"Semantic: {semantic_path}")
    print(f"Sheet rows: {rows_path}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5A-2C: analyze pinned captions")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать OpenAI")
    args = parser.parse_args()
    analyze(args.account, args.dry_run)
