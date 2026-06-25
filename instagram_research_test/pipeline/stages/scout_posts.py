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
фильтр на этапе анализа (_is_relevant). Здесь — только прикидка по ключевым словам.

Использование:
  python -m pipeline.stages.scout_posts --account kate.jet
"""

import argparse
import json
import logging
import re
from datetime import datetime

from pipeline.core.apify_client import run_actor

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
    }


def format_scout_message(s: dict) -> str:
    """Готовый текст для Telegram (Markdown). Моноширинный блок со сводкой."""
    bt = s["by_type"]
    period = (
        f"{s['date_min']} … {s['date_max']}"
        if s["date_min"] else "период не определён"
    )
    more = " (и, возможно, больше)" if s.get("sample_truncated") else ""
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
        f"Личное/мусор   : ~{s['est_personal']} (грубая оценка, отсеется фильтром)\n"
        f"{'─' * 32}\n"
        f"Полный анализ всех {s['total']}:\n"
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
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    print(format_scout_message(result))
