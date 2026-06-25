"""
Stage 12.5: РАЗВЕДКА постов (scout).

Лёгкий проход ПЕРЕД сбором и анализом: один батч Apify (resultsType=posts),
без GPT, без скачивания медиа. Нужен, чтобы показать пользователю в Telegram
сводку и дать осознанно выбрать объём/период прогона.

Возвращает dict со всем, что нужно для экрана выбора:
  - total / by_type            — сколько постов и разбивка по типам
  - date_min / date_max        — период (самая старая/новая дата в батче)
  - hidden_likes               — у скольких постов лайки скрыты (likesCount == -1)
  - est_personal               — грубая оценка доли personal/мусора (по эвристике caption)
  - est_cost_usd / est_minutes — прикидка стоимости и времени анализа

Эвристика est_personal НЕ вызывает GPT (это разведка). Точный отсев делает
triage() (см. ниже) — каскад от дешёвого к дорогому.

triage(items) — каскадный отсев ПЕРЕД дорогим Vision-анализом:
  - Уровень 0 (правила, без GPT): drop старых постов и нерелевантных типов.
  - Уровень 1 (ОДИН gpt-4o-mini батч на все caption): professional→keep,
    personal→drop, mixed→review. Сбой батча → review (не режем вслепую).
Смысл: не платить $0.03/пост за Vision и не качать медиа по мусору.

Использование:
  python -m pipeline.stages.scout_posts --account kate.jet
"""

import argparse
import json
import logging
from datetime import datetime, timedelta, timezone

from pipeline.core.apify_client import run_actor
from pipeline.core.openai_client import chat
# Переиспользуем таксономию и модель фильтра из анализа (не дублируем текст промпта).
# analyze_posts не импортирует scout_posts → цикла нет.
from pipeline.stages.analyze_posts import FILTER_MODEL, FILTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Прикидка стоимости одного поста при анализе (gpt-4o Vision + скачивание медиа).
# Подберите под свой реальный биллинг; значения сознательно консервативные.
_COST_PER_POST_USD = 0.03
_SECONDS_PER_POST = 35  # из логов прогона: ~30-35 с/пост

# Грубые маркеры личного/мусорного контента для разведочной оценки.
_PERSONAL_HINTS = (
    "с новым годом", "с праздником", "поздравля", "др ", "день рожден",
    "отпуск", "путешеств", "италия", "море", "пляж", "люблю вас",
    "спасибо всем", "мой год", "итоги года", "семь",
)


def _post_type(raw_type: str) -> str:
    return {"Sidecar": "carousel", "Video": "video", "Image": "photo"}.get(raw_type, "photo")


def _looks_personal(caption: str) -> bool:
    c = (caption or "").lower()
    return any(h in c for h in _PERSONAL_HINTS)


# ─────────────────────────────────────────────────────────────────────────────
# triage — каскадный отсев постов ПЕРЕД дорогим анализом
# ─────────────────────────────────────────────────────────────────────────────
_FILTER_MAX_BATCH_TOKENS = 4000


def _short_code(item: dict) -> str:
    return item.get("shortCode") or item.get("id") or ""


def _parse_ts(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _verdict_from_content_type(ct: str) -> str:
    return {"professional": "keep", "personal": "drop", "mixed": "review"}.get(ct, "review")


def _parse_json_array(raw_text: str) -> list:
    """Парсит JSON-массив из ответа модели. Терпит ```-обёртку и {"...": [...]}."""
    raw_text = (raw_text or "").strip()
    if raw_text.startswith("```"):
        lines = raw_text.splitlines()
        raw_text = "\n".join(ln for ln in lines if not ln.startswith("```")).strip()
    data = json.loads(raw_text)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
        raise ValueError("в объекте нет массива")
    if not isinstance(data, list):
        raise ValueError("ответ не является массивом")
    return data


def _classify_batch(captions: list) -> list | None:
    """Уровень 1: ОДИН gpt-4o-mini вызов на ВСЕ caption сразу.

    Возвращает список объектов {content_type, reason} в порядке входа.
    None — если батч-вызов упал или вернул мусор (вызывающий уводит всех в review).
    """
    if not captions:
        return []

    numbered = "\n".join(
        f"[{i}] {((c or '').strip()[:300]) or '(нет caption)'}"
        for i, c in enumerate(captions)
    )
    user = (
        f"Классифицируй каждый из {len(captions)} постов по content_type "
        "(professional / personal / mixed) согласно правилам выше.\n"
        "Верни ТОЛЬКО валидный JSON-массив той же длины и в том же порядке, "
        "без текста до или после:\n"
        '[{"index": 0, "content_type": "professional|personal|mixed", "reason": "одно слово"}, ...]\n\n'
        f"Посты:\n{numbered}"
    )
    messages = [
        {"role": "system", "content": FILTER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    max_tokens = min(_FILTER_MAX_BATCH_TOKENS, 64 + 32 * len(captions))

    try:
        raw_text = chat(messages, model=FILTER_MODEL, max_tokens=max_tokens)
    except Exception as e:
        logger.warning("triage L1: батч-вызов упал (%s) → все выжившие в review", e)
        return None

    try:
        arr = _parse_json_array(raw_text)
    except Exception as e:
        logger.warning("triage L1: невалидный JSON (%s) → все выжившие в review", e)
        return None

    # Раскладываем по полю index (порядок в ответе может отличаться).
    out: list = [None] * len(captions)
    for obj in arr:
        if isinstance(obj, dict) and isinstance(obj.get("index"), int) and 0 <= obj["index"] < len(captions):
            out[obj["index"]] = obj
    # Фолбэк: модель не проставила index, но длина совпала — берём по порядку.
    if all(o is None for o in out) and len(arr) == len(captions):
        out = list(arr)
    return out


def triage(items, months_back: int | None = None, post_types: list | None = None, now=None) -> list:
    """Каскадный отсев постов ПЕРЕД дорогим Vision-анализом.

    items       — сырые посты от Apify (caption / type / timestamp / shortCode).
    months_back — если задан, посты старше периода уходят в drop на Уровне 0.
    post_types  — если задан, посты не из списка типов уходят в drop на Уровне 0.
    now         — точка отсчёта периода (для тестов); по умолчанию текущее UTC.

    Возвращает список вердиктов по входному порядку:
        {short_code, verdict: "keep"|"drop"|"review", content_type, reason}

    Маппинг content_type → verdict: professional→keep, personal→drop, mixed→review.
    """
    items = list(items or [])
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=months_back * 30) if months_back else None

    verdicts: list = [None] * len(items)
    pending: list = []  # (idx, short, caption) — выжившие после Уровня 0 → на Уровень 1

    # ── Уровень 0: бесплатные правила, без GPT ───────────────────────────────
    for idx, it in enumerate(items):
        short = _short_code(it)
        caption = it.get("caption") or ""
        pt = _post_type(it.get("type", "Image"))

        if post_types is not None and pt not in post_types:
            verdicts[idx] = {"short_code": short, "verdict": "drop",
                             "content_type": "irrelevant_type", "reason": f"тип не в выборке: {pt}"}
            continue

        if cutoff is not None:
            ts = _parse_ts(it.get("timestamp", ""))
            if ts is not None and ts < cutoff:
                verdicts[idx] = {"short_code": short, "verdict": "drop",
                                 "content_type": "out_of_period", "reason": "старше периода"}
                continue

        pending.append((idx, short, caption))

    # ── Уровень 1: один дешёвый батч на всех выживших ────────────────────────
    classified = _classify_batch([c for (_, _, c) in pending]) if pending else []

    for j, (idx, short, caption) in enumerate(pending):
        obj = classified[j] if (classified is not None and j < len(classified)) else None
        ct = obj.get("content_type") if isinstance(obj, dict) else None
        reason = (obj.get("reason") if isinstance(obj, dict) else "") or ""

        if ct in ("professional", "personal", "mixed"):
            verdict = _verdict_from_content_type(ct)
            # _looks_personal — ТОЛЬКО сигнал: сами пост не роняем (избегаем
            # ложных personal-срабатываний по ключевым словам), помечаем reason.
            if verdict != "drop" and _looks_personal(caption):
                reason = (f"{reason} · сигнал:личное").strip(" ·")
            verdicts[idx] = {"short_code": short, "verdict": verdict,
                             "content_type": ct, "reason": reason or ct}
        else:
            # Сбой/мусор по этому посту → review (не теряем данные, не режем вслепую).
            verdicts[idx] = {"short_code": short, "verdict": "review",
                             "content_type": "unknown", "reason": "классификатор не дал вердикт"}

    return verdicts


def triage_counts(verdicts) -> dict:
    """Сводка keep/review/drop по списку вердиктов triage()."""
    c = {"keep": 0, "review": 0, "drop": 0}
    for v in verdicts or []:
        vd = v.get("verdict")
        if vd in c:
            c[vd] += 1
    return c


def drop_codes(verdicts) -> list:
    """Список shortCode с verdict=drop — для exclude_codes в collect_posts.collect()."""
    return [v["short_code"] for v in (verdicts or [])
            if v.get("verdict") == "drop" and v.get("short_code")]


def scout(username: str, sample_limit: int = 48) -> dict:
    """Лёгкая разведка аккаунта. Один батч Apify, без GPT и без медиа."""
    url = f"https://www.instagram.com/{username}/"
    logger.info("[12.5] scout | @%s | sample_limit=%s", username, sample_limit)

    items = run_actor(
        actor_id="apify/instagram-scraper",
        input_data={
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": sample_limit,
            "proxy": {"useApifyProxy": True},
        },
    ) or []

    by_type = {"photo": 0, "carousel": 0, "video": 0}
    dates: list[datetime] = []
    hidden_likes = 0
    est_personal = 0

    for it in items:
        pt = _post_type(it.get("type", "Image"))
        by_type[pt] = by_type.get(pt, 0) + 1

        ts = it.get("timestamp", "")
        if ts:
            try:
                dates.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
            except Exception:
                pass

        if int(it.get("likesCount") or 0) < 0:
            hidden_likes += 1
        if _looks_personal(it.get("caption", "")):
            est_personal += 1

    total = len(items)
    date_min = min(dates).date().isoformat() if dates else None
    date_max = max(dates).date().isoformat() if dates else None

    return {
        "account": username,
        "total": total,
        "by_type": by_type,
        "date_min": date_min,
        "date_max": date_max,
        "hidden_likes": hidden_likes,
        "est_personal": est_personal,
        "est_cost_usd": round(total * _COST_PER_POST_USD, 2),
        "est_minutes": round(total * _SECONDS_PER_POST / 60, 1),
        "sample_truncated": total >= sample_limit,  # возможно, постов больше
        "items": items,  # сырые посты для triage() — один Apify-вызов на разведку
    }


def format_scout_message(s: dict, tri_counts: dict | None = None) -> str:
    """Готовый текст для Telegram (Markdown). Моноширинный блок со сводкой.

    tri_counts — опциональная сводка triage() {keep, review, drop}; если передана,
    в блок добавляется строка релевантности.
    """
    bt = s["by_type"]
    period = (
        f"{s['date_min']} … {s['date_max']}"
        if s["date_min"] else "период не определён"
    )
    more = " (и, возможно, больше)" if s.get("sample_truncated") else ""
    triage_seg = ""
    if tri_counts:
        triage_seg = (
            f"Релевантность  : {tri_counts.get('keep', 0)} keep · "
            f"{tri_counts.get('review', 0)} review · {tri_counts.get('drop', 0)} drop\n"
        )
    body = (
        f"@{s['account']} — разведка\n"
        f"{'─' * 32}\n"
        f"Найдено постов : {s['total']}{more}\n"
        f"  фото         : {bt.get('photo', 0)}\n"
        f"  карусели     : {bt.get('carousel', 0)}\n"
        f"  видео        : {bt.get('video', 0)}\n"
        f"Период         : {period}\n"
        f"Скрытые лайки  : {s['hidden_likes']} из {s['total']}  "
        f"(ERR по ним = н/д)\n"
        f"Личное/мусор   : ~{s['est_personal']} (грубая оценка)\n"
        f"{triage_seg}"
        f"{'─' * 32}\n"
        f"drop отсеивается автоматически, review идёт в анализ с пометкой.\n"
        f"Анализ (keep+review):\n"
        f"  ≈ ${s['est_cost_usd']} · ≈ {s['est_minutes']} мин"
    )
    return "```\n" + body + "\n```"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Stage 12.5: scout posts")
    parser.add_argument("--account", required=True)
    parser.add_argument("--sample-limit", type=int, default=48)
    args = parser.parse_args()
    result = scout(args.account, sample_limit=args.sample_limit)
    items = result.pop("items", [])  # не печатаем сырые посты в сводке
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    verdicts = triage(items, post_types=["photo", "carousel"])
    print(format_scout_message(result, tri_counts=triage_counts(verdicts)))
