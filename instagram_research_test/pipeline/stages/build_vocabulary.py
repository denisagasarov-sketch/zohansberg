"""Stage 5 (vocabulary): индуктивная сборка словаря механик подачи и хуков.

Стейдж НЕ присваивает посту готовый ярлык. Он читает реальные тексты постов
(полный текст из raw + заголовок с обложки из stage5e1) и ИНДУКТИВНО, снизу
вверх, строит словарь приёмов прямо из этих текстов.

Три прохода GPT-4o (pipeline.core.openai_client):
  1. индукция (пер-пост)   — для КАЖДОГО поста назвать его механику и хук так,
     как реально устроен именно этот пост (привязка к post_id);
  2. стабилизация (кластеры) — сгруппировать синонимичные приёмы в категории,
     members = список постов-носителей категории;
  3. верификация            — придирчиво перепроверить каждого члена категории по
     тексту поста и убрать ошибочно приписанные.

Готовые ярлыки из stage5e1 («Механика подачи», «Тип хука») модели НЕ
показываются — иначе индукция выродится в копирование захардкоженного списка.

frequency считается ДЕТЕРМИНИРОВАННО в Python = число подтверждённых
постов-носителей, а не на глаз. Это исключает галлюцинации и расхождение
«частота против примеров». Деление:
  core       — приём встретился в >=2 постах (устойчивое ядро, рабочий
               справочник для analyze_posts);
  candidates — приём из 1 поста (единичные/новые приёмы на ревью Кейт).
При прогонах по новым конкурентам свежие механики копятся в candidates, а не
теряются.

Использование:
  python3 -m pipeline.stages.build_vocabulary --account kate.jet --dry-run
  python3 -m pipeline.stages.build_vocabulary --account kate.jet
"""

import argparse
import json
import logging
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.openai_client import chat
from pipeline.core.paths import normalized, raw
from pipeline.core import sheets_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STAGE = "stage5_vocabulary"
VOCAB_VERSION = "v1"
PROMPT_VERSION = "v4"
MODEL = "gpt-4o"
SHEET_NAME = "Словарь"

# Минимум постов, при котором приём попадает в устойчивое ядро.
CORE_MIN_FREQUENCY = 2
# Сколько постов-носителей показывать как иллюстративные примеры.
MAX_EXAMPLES = 3

POSTS_ANALYSIS_FILE = "stage5e1_posts_analysis.json"
POSTS_RAW_FILE = "stage5e0_posts_raw.json"
OUTPUT_FILE = "stage5_vocabulary.json"


# --------------------------------------------------------------------------- #
# Промпты трёх проходов
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT_TAG = """Ты — аналитик контента Instagram. Тебе дают тексты постов
одного автора, у каждого свой post_id.

Для КАЖДОГО поста определи два приёма, опираясь ТОЛЬКО на его текст:

- mechanic — драматургия ВСЕГО поста: как читателя ведут от входа к целевому
  действию (последовательность ходов: вход → развитие → доказательство →
  переход к продукту/CTA). Имя должно описывать ПРИЁМ (КАК сделан пост), а не
  ТЕМУ (О ЧЁМ он).
  Хорошие имена (приём): «от боли к решению по шагам», «миф → опровержение →
  доказательство», «личная история → урок → оффер», «разбор ошибки на кейсе».
  Плохие имена (это темы, так НЕЛЬЗЯ): «аналитика и метрики», «обучение и
  курсы», «стратегия», «про KPI».
  Дай имя и пояснение в одну фразу.

- hook — приём первых 1–2 секунд: заголовок с обложки или первая фраза, то, что
  останавливает скролл. Имя описывает ТИП ВХОДА, а не тему.
  Хорошие имена (приём): «цепляющий вопрос», «провокационное заявление»,
  «обещание конкретного результата», «шокирующая цифра», «узнаваемая боль».
  Плохие имена (это темы, так НЕЛЬЗЯ): «привлечение через метрики», «про курсы».
  Дай имя и пояснение в одну фразу.

Называй так, как реально устроен ИМЕННО ЭТОТ пост, не подгоняй под общий список.
Не путай типы: механика — про весь пост, хук — только вход; CTA в конце поста —
часть механики, а НЕ хук. Если пост — служебный анонс «не для широкой
аудитории», всё равно назови его драматургию, НЕ делай приёмом сам факт
ограничения доступа.

Верни только валидный JSON без markdown, по одному элементу на каждый пост:
{
  "posts": [
    {"post_id": "...",
     "mechanic": {"name": "...", "note": "..."},
     "hook": {"name": "...", "note": "..."}}
  ]
}
post_id бери дословно из входных данных."""


SYSTEM_PROMPT_CLUSTER = """Ты — редактор словаря приёмов контента. Тебе дают
по-постовые приёмы: для каждого post_id названы его механика и хук.

Сгруппируй СИНОНИМИЧНЫЕ приёмы в категории — отдельно механики, отдельно хуки.

ГЛАВНОЕ: группируй по ПРИЁМУ (КАК сделан пост), а НЕ по ТЕМЕ (О ЧЁМ он). Два
поста про разные темы (например, про аналитику и про тексты), но с одной
драматургией (боль → разбор → оффер) — это ОДНА категория. Имя категории
описывает приём; в нём НЕ должно быть темы (аналитика, KPI, курсы, метрики,
тексты, стратегия). «Фильтрованный контент» / «не для паблика» — это не приём,
не делай из этого категорию.

Правила слияния:
- объединяй ТОЛЬКО приёмы с одной сутью (разные слова — один приём). Разные по
  сути приёмы НЕ сливай, даже если они тематически близки;
- приём, встретившийся лишь в одном посте, ОБЯЗАТЕЛЬНО оставь отдельной
  категорией — его нельзя терять (он станет кандидатом);
- каждый post_id-механика попадает ровно в одну категорию механик; каждый
  post_id-хук — ровно в одну категорию хуков;
- members бери ТОЛЬКО из входных post_id, дословно, ничего не выдумывай.

Для каждой категории верни: name (имя категории), definition (1–2 фразы),
why_it_works (почему цепляет), members (список ВСЕХ её post_id).

Верни только валидный JSON без markdown:
{
  "mechanics": [
    {"name": "...", "definition": "...", "why_it_works": "...",
     "members": ["post_id", "post_id"]}
  ],
  "hooks": [
    {"name": "...", "definition": "...", "why_it_works": "...",
     "members": ["post_id"]}
  ]
}"""


SYSTEM_PROMPT_VERIFY = """Ты — придирчивый проверяющий словаря приёмов. Тебе дают
категории приёмов (имя + определение) с приписанными постами (members) и тексты
этих постов по post_id.

Для КАЖДОЙ категории перепроверь КАЖДЫЙ member по тексту поста: действительно ли
этот пост использует именно этот приём так, как он определён? Убери посты, которые
приписаны ошибочно. Будь строгим: при сомнении — убирай.

Не добавляй новых постов и новых категорий, не переименовывай категории и не меняй
их определения. Только уточняй состав members.

Верни только валидный JSON без markdown в той же структуре:
{
  "mechanics": [
    {"name": "...", "definition": "...", "why_it_works": "...",
     "members": ["post_id"]}
  ],
  "hooks": [
    {"name": "...", "definition": "...", "why_it_works": "...",
     "members": ["post_id"]}
  ]
}"""


# --------------------------------------------------------------------------- #
# Загрузка постов
# --------------------------------------------------------------------------- #

def _load_posts(username: str) -> list[dict]:
    """Джойнит заголовки с обложки (stage5e1) и полные тексты (raw) по url.

    Возвращает список постов вида:
      {"post_id": shortCode, "url": ..., "cover_title": ..., "caption": ...}
    Готовые ярлыки stage5e1 (Механика подачи / Тип хука) НЕ переносятся.
    """
    analysis_path = normalized(username, POSTS_ANALYSIS_FILE)
    raw_path = raw(username, POSTS_RAW_FILE)
    if not analysis_path.exists():
        raise FileNotFoundError(
            f"Не найден {analysis_path}. Сначала запустите analyze_posts."
        )
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Не найден {raw_path}. Сначала запустите collect_posts."
        )

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    raw_items = json.loads(raw_path.read_text(encoding="utf-8"))

    by_url = {}
    for item in raw_items:
        url = str(item.get("url", "")).rstrip("/")
        if url:
            by_url[url] = item

    posts: list[dict] = []
    for row in analysis.get("rows", []):
        url = str(row.get("Ссылка на пост", "")).rstrip("/")
        raw_item = by_url.get(url, {})
        caption = str(raw_item.get("caption", "")).strip()
        cover_title = str(row.get("Заголовок поста", "")).strip()
        post_id = str(raw_item.get("shortCode", "")).strip() or (
            url.rsplit("/", 1)[-1] if url else ""
        )
        if not post_id or (not caption and not cover_title):
            continue
        posts.append({
            "post_id": post_id,
            "url": url,
            "cover_title": cover_title,
            "caption": caption,
        })
    if not posts:
        raise ValueError("Не удалось собрать ни одного поста с текстом для словаря.")
    return posts


def _post_text(post: dict) -> str:
    cover = post["cover_title"] or "(нет заголовка с обложки)"
    caption = post["caption"] or "(нет текста)"
    return (
        f"Заголовок с обложки: {cover}\n"
        f"Полный текст поста:\n{caption}"
    )


def _build_corpus_prompt(posts: list[dict]) -> str:
    """Корпус текстов постов для прохода 1 (индукция)."""
    blocks = [f"post_id: {p['post_id']}\n{_post_text(p)}" for p in posts]
    return (
        f"Корпус из {len(posts)} постов одного автора. "
        "Для каждого поста назови механику и хук строго по инструкции.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def _corpus_for_verify(posts: list[dict]) -> str:
    """Тексты постов по post_id для прохода 3 (верификация)."""
    blocks = [f"post_id: {p['post_id']}\n{_post_text(p)}" for p in posts]
    return "\n\n---\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Разбор ответов модели
# --------------------------------------------------------------------------- #

def _parse_response(response: str) -> dict:
    """Парсит JSON-ответ модели, снимая возможную markdown-обёртку."""
    stripped = (response or "").strip()
    if stripped.startswith("```"):
        stripped = "\n".join(
            line for line in stripped.splitlines()
            if not line.strip().startswith("```")
        ).strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Ответ OpenAI должен быть JSON-объектом")
    return parsed


def _clean_members(members, valid_ids: set[str]) -> list[str]:
    """Оставляет только реальные post_id корпуса, без повторов и порядок сохраняя."""
    if not isinstance(members, list):
        members = [members]
    out, seen, dropped = [], set(), []
    for m in members:
        mid = str(m).strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        if mid in valid_ids:
            out.append(mid)
        else:
            dropped.append(mid)
    if dropped:
        logger.warning("Отброшены выдуманные/неизвестные post_id: %s", dropped)
    return out


def _clean_clusters(parsed: dict, valid_ids: set[str]) -> dict:
    """Приводит ответ кластеризации/верификации к каноничной форме."""
    result = {"mechanics": [], "hooks": []}
    for block in ("mechanics", "hooks"):
        for cat in parsed.get(block, []) or []:
            if not isinstance(cat, dict):
                continue
            name = str(cat.get("name", "")).strip()
            if not name:
                continue
            result[block].append({
                "name": name,
                "definition": str(cat.get("definition", "")).strip(),
                "why_it_works": str(cat.get("why_it_works", "")).strip(),
                "members": _clean_members(cat.get("members"), valid_ids),
            })
    return result


# --------------------------------------------------------------------------- #
# Три прохода
# --------------------------------------------------------------------------- #

def _tag_posts(posts: list[dict]) -> dict:
    """Проход 1: пер-пост индукция механики и хука каждого поста."""
    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_TAG},
            {"role": "user", "content": _build_corpus_prompt(posts)},
        ],
        model=MODEL,
        max_tokens=4000,
    )
    parsed = _parse_response(response)
    return {"posts": parsed.get("posts", []) if isinstance(parsed, dict) else []}


def _cluster(tags: dict, valid_ids: set[str]) -> dict:
    """Проход 2: группировка синонимичных приёмов в категории."""
    user_prompt = (
        "По-постовые приёмы в JSON (для каждого post_id — механика и хук). "
        "Сгруппируй синонимы в категории по инструкции.\n\n"
        + json.dumps(tags, ensure_ascii=False, indent=2)
    )
    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_CLUSTER},
            {"role": "user", "content": user_prompt},
        ],
        model=MODEL,
        max_tokens=4000,
    )
    return _clean_clusters(_parse_response(response), valid_ids)


def _verify(clusters: dict, posts: list[dict], valid_ids: set[str]) -> dict:
    """Проход 3: придирчивая проверка состава members по текстам постов."""
    user_prompt = (
        "Категории приёмов (JSON):\n"
        + json.dumps(clusters, ensure_ascii=False, indent=2)
        + "\n\nТексты постов по post_id:\n\n"
        + _corpus_for_verify(posts)
        + "\n\nПерепроверь members каждой категории по тексту и верни уточнённый JSON."
    )
    response = chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_VERIFY},
            {"role": "user", "content": user_prompt},
        ],
        model=MODEL,
        max_tokens=4000,
    )
    return _clean_clusters(_parse_response(response), valid_ids)


# --------------------------------------------------------------------------- #
# Сборка словаря
# --------------------------------------------------------------------------- #

def _category_to_item(category: dict) -> dict | None:
    """Превращает категорию (с members) в элемент словаря.

    frequency считается детерминированно = число подтверждённых постов-носителей.
    Категории без носителей (все члены отсеяны верификацией) выбрасываются.
    """
    members = category["members"]
    if not members:
        return None
    return {
        "name": category["name"],
        "definition": category["definition"],
        "why_it_works": category["why_it_works"],
        "frequency": len(members),
        "examples": members[:MAX_EXAMPLES],
    }


def _split_core_candidates(categories: list[dict]) -> dict:
    """Делит категории на ядро (>=CORE_MIN_FREQUENCY постов) и кандидатов.

    Деление детерминированное (на стороне Python), чтобы правило «>=2 постов»
    не зависело от модели. Оба списка сортируются по убыванию частоты.
    """
    core, candidates = [], []
    for category in categories:
        item = _category_to_item(category)
        if item is None:
            continue
        status = "core" if item["frequency"] >= CORE_MIN_FREQUENCY else "candidate"
        item = {**item, "status": status}
        (core if status == "core" else candidates).append(item)
    core.sort(key=lambda x: x["frequency"], reverse=True)
    candidates.sort(key=lambda x: x["frequency"], reverse=True)
    return {"core": core, "candidates": candidates}


def _build_vocabulary(verified: dict, username: str, built_at: str) -> dict:
    """Собирает итоговую структуру словаря с заделом под рост."""
    return {
        "version": VOCAB_VERSION,
        "built_at": built_at,
        "account": username,
        "stage": STAGE,
        "model": MODEL,
        "prompt_version": PROMPT_VERSION,
        "mechanics": _split_core_candidates(verified.get("mechanics", [])),
        "hooks": _split_core_candidates(verified.get("hooks", [])),
    }


# --------------------------------------------------------------------------- #
# Лист «Словарь»
# --------------------------------------------------------------------------- #

SHEET_HEADERS = (
    "Категория", "Имя", "Определение", "Почему цепляет", "Частота",
    "Статус", "Примеры", "Дата записи",
)
_STATUS_RU = {"core": "ядро", "candidate": "кандидат"}


def _sheet_rows(vocabulary: dict) -> dict:
    """Готовит payload листа «Словарь»: два блока — Механики и Хуки."""
    date_str = vocabulary["built_at"][:10]
    rows: list[list[str]] = []

    def _emit(category: str, bucket: dict) -> None:
        # ядро сверху, затем кандидаты — оба уже отсортированы по частоте
        for item in bucket.get("core", []) + bucket.get("candidates", []):
            rows.append([
                category,
                item["name"],
                item["definition"],
                item["why_it_works"],
                str(item["frequency"]),
                _STATUS_RU.get(item["status"], item["status"]),
                ", ".join(item["examples"]),
                date_str,
            ])

    _emit("Механика", vocabulary["mechanics"])
    _emit("Хук", vocabulary["hooks"])
    return {"headers": list(SHEET_HEADERS), "rows": rows}


def _write_sheet(username: str, vocabulary: dict, dry_run: bool) -> dict:
    """Пишет лист «Словарь» через sheets_client (replace-семантика).

    Лист общий (не per-competitor), поэтому replace перезаписывает его целиком.
    Ошибку записи (например, вкладки «Словарь» ещё нет в таблице) не роняем —
    JSON-словарь уже сохранён, а статус записи возвращаем наверх.
    """
    payload = {
        "account": username,
        "sheets": {SHEET_NAME: _sheet_rows(vocabulary)},
    }
    try:
        return sheets_client.write_payload(payload, dry_run=dry_run, write_mode="replace")
    except Exception as error:  # noqa: BLE001 — лист не должен ронять стейдж
        logger.warning("Запись листа «%s» не удалась: %s", SHEET_NAME, error)
        return {"ok": False, "error": str(error).splitlines()[0]}


def _print_summary(vocabulary: dict) -> None:
    print(f"\n=== Stage 5 Vocabulary | @{vocabulary['account']} ===")
    for block, title in (("mechanics", "МЕХАНИКИ"), ("hooks", "ХУКИ")):
        bucket = vocabulary[block]
        print(f"\n{title}: ядро={len(bucket['core'])}, кандидаты={len(bucket['candidates'])}")
        for item in bucket["core"]:
            print(f"  [ядро ×{item['frequency']}] {item['name']} — {item['definition'][:70]}")
        for item in bucket["candidates"]:
            print(f"  [канд ×{item['frequency']}] {item['name']} — {item['definition'][:70]}")


# --------------------------------------------------------------------------- #
# Оркестрация
# --------------------------------------------------------------------------- #

def build(username: str, dry_run: bool = False) -> dict:
    """Строит словарь механик/хуков индуктивно и пишет JSON + лист «Словарь»."""
    get_account(username)
    posts = _load_posts(username)
    valid_ids = {p["post_id"] for p in posts}

    logger.info("[5-VOCAB] build_vocabulary | @%s | постов=%d | dry_run=%s",
                username, len(posts), dry_run)
    if dry_run:
        logger.info("[DRY RUN] OpenAI и Google Sheets не вызываются, файлы не пишутся")
        return {
            "dry_run": True,
            "account": username,
            "model": MODEL,
            "posts_count": len(posts),
            "post_ids": sorted(valid_ids),
            "user_prompt_preview": _build_corpus_prompt(posts)[:1200],
        }

    built_at = datetime.now(timezone.utc).isoformat()
    tags = _tag_posts(posts)                       # проход 1: пер-пост индукция
    clusters = _cluster(tags, valid_ids)           # проход 2: кластеризация
    verified = _verify(clusters, posts, valid_ids) # проход 3: верификация
    vocabulary = _build_vocabulary(verified, username, built_at)

    output_path = normalized(username, OUTPUT_FILE)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(vocabulary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sheet_result = _write_sheet(username, vocabulary, dry_run=False)

    _print_summary(vocabulary)
    print(f"\nСохранено: {output_path}")
    print(f"Лист «{SHEET_NAME}»: {sheet_result}")
    return {**vocabulary, "sheet_result": sheet_result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5: build vocabulary")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать внешние API")
    args = parser.parse_args()
    build(args.account, args.dry_run)
