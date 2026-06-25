"""Тесты раскладки разведки по периодам (scout_posts._period_breakdown), без сети.

Запуск из корня:  python tests/test_scout_period.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.stages.scout_posts as sp  # noqa: E402

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)
PTS = {"photo", "carousel"}


def _item(date, typ="Sidecar"):
    return {"type": typ, "timestamp": f"{date}T00:00:00.000Z"}


def test_counts_per_bucket_and_type_filter():
    items = [
        _item("2026-06-01"),            # ~24 дн  → попадает в 3/6/12/24
        _item("2026-02-01", "Image"),   # ~5 мес  → в 6/12/24 (фото — тоже разрешён)
        _item("2025-09-01"),            # ~9.8 мес→ в 12/24
        _item("2024-12-01"),            # ~18 мес → в 24
        _item("2023-01-01"),            # >24 мес → ни в одну
        _item("2026-06-10", "Video"),   # видео   → исключается типом везде
    ]
    bd = sp._period_breakdown(items, PTS, NOW, truncated=False)
    counts = {b["months"]: b["count"] for b in bd}
    assert counts == {3: 1, 6: 2, 12: 3, 24: 4}, counts
    # счётчики монотонны (вложенные окна)
    seq = [counts[m] for m in (3, 6, 12, 24)]
    assert seq == sorted(seq), seq
    # не truncated → нижних оценок нет
    assert all(not b["lower_bound"] for b in bd)
    print("OK  count по корзинам корректен; видео исключено; монотонность")


def test_lower_bound_only_when_truncated():
    # все собранные посты свежие (oldest=2026-03-01) и батч упёрся в лимит
    items = [_item("2026-06-01"), _item("2026-04-15"), _item("2026-03-01")]
    bd = {b["months"]: b for b in sp._period_breakdown(items, PTS, NOW, truncated=True)}
    # 3 мес: cutoff 2026-03-27 новее самого старого (2026-03-01) → окно покрыто → НЕ нижняя оценка
    assert bd[3]["lower_bound"] is False, bd[3]
    # 6/12/24: окно уходит старше собранного → нижняя оценка «N+»
    assert bd[6]["lower_bound"] is True, bd[6]
    assert bd[12]["lower_bound"] is True and bd[24]["lower_bound"] is True
    # без truncated тех же данных — нижних оценок нет
    bd2 = sp._period_breakdown(items, PTS, NOW, truncated=False)
    assert all(b["lower_bound"] is False for b in bd2)
    print("OK  lower_bound только при truncated и окне старше собранного")


def test_cost_estimate_in_breakdown():
    bd = sp._period_breakdown([_item("2026-06-01")], PTS, NOW, truncated=False)
    b3 = next(b for b in bd if b["months"] == 3)
    assert b3["count"] == 1
    assert b3["est_cost_usd"] == round(1 * sp._COST_PER_POST_USD, 2), b3
    assert b3["est_minutes"] == round(1 * sp._SECONDS_PER_POST / 60, 1), b3
    print("OK  оценка $/мин присутствует в раскладке")


def test_buckets_present_and_shape():
    bd = sp._period_breakdown([], PTS, NOW, truncated=False)
    assert [b["months"] for b in bd] == [3, 6, 12, 24], bd
    assert all({"months", "count", "lower_bound"} <= set(b) for b in bd)
    assert all(b["count"] == 0 for b in bd)  # пустой вход → нули
    print("OK  всегда 3/6/12/24 корзины нужной формы; пустой вход → нули")


if __name__ == "__main__":
    test_counts_per_bucket_and_type_filter()
    test_lower_bound_only_when_truncated()
    test_cost_estimate_in_breakdown()
    test_buckets_present_and_shape()
    print("\n✅ все тесты раскладки по периодам пройдены")
