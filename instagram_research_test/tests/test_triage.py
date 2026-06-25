"""Юнит-тесты triage() из scout_posts на моках (без сети, без pytest).

Покрывает: professional→keep, personal→drop, mixed→review, старый пост→drop (L0),
видео (не тот тип)→drop (L0), сбой gpt-mini→review (fallback), мусорный JSON→review,
а также что L1 НЕ вызывается, если L0 отсеял всё.

Запуск из корня проекта:
    python tests/test_triage.py
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.stages.scout_posts as sp  # noqa: E402

NOW = datetime(2026, 6, 25, tzinfo=timezone.utc)


def _item(short, caption="", typ="Sidecar", ts="2026-06-01T00:00:00.000Z"):
    return {"shortCode": short, "caption": caption, "type": typ, "timestamp": ts}


def _fake_chat(mapping):
    """chat-заглушка: отдаёт JSON-массив content_type по порядку входа."""
    def fake(messages, model=None, max_tokens=None, **kw):
        arr = [{"index": i, "content_type": ct, "reason": "mock"} for i, ct in enumerate(mapping)]
        return json.dumps(arr, ensure_ascii=False)
    return fake


def test_professional_personal_mixed():
    items = [_item("AAA", "кейс клиента +300к"),
             _item("BBB", "с новым годом друзья"),
             _item("CCC", "разбор с личной историей")]
    sp.chat = _fake_chat(["professional", "personal", "mixed"])
    res = sp.triage(items, months_back=None, post_types=["photo", "carousel"], now=NOW)
    by = {r["short_code"]: r["verdict"] for r in res}
    assert by == {"AAA": "keep", "BBB": "drop", "CCC": "review"}, by
    print("OK  professional→keep · personal→drop · mixed→review")


def test_old_post_dropped_at_level0():
    items = [_item("OLD", "кейс", ts="2024-01-01T00:00:00.000Z"),
             _item("NEW", "кейс", ts="2026-06-01T00:00:00.000Z")]
    sp.chat = _fake_chat(["professional"])  # на L1 доходит только NEW
    res = sp.triage(items, months_back=6, post_types=["photo", "carousel"], now=NOW)
    by = {r["short_code"]: (r["verdict"], r["content_type"]) for r in res}
    assert by["OLD"] == ("drop", "out_of_period"), by
    assert by["NEW"][0] == "keep", by
    print("OK  старый пост → drop на L0 (без GPT)")


def test_irrelevant_type_dropped_at_level0():
    items = [_item("VID", "обзор", typ="Video"),
             _item("CAR", "кейс", typ="Sidecar")]
    sp.chat = _fake_chat(["professional"])  # на L1 доходит только CAR
    res = sp.triage(items, post_types=["photo", "carousel"], now=NOW)
    by = {r["short_code"]: (r["verdict"], r["content_type"]) for r in res}
    assert by["VID"] == ("drop", "irrelevant_type"), by
    assert by["CAR"][0] == "keep", by
    print("OK  видео (не тот тип) → drop на L0 (без GPT)")


def test_gpt_failure_fallback_review():
    items = [_item("X1", "кейс"), _item("X2", "ещё кейс")]

    def boom(*a, **k):
        raise RuntimeError("gpt-mini недоступен")

    sp.chat = boom
    res = sp.triage(items, post_types=["photo", "carousel"], now=NOW)
    assert all(r["verdict"] == "review" for r in res), res
    print("OK  сбой gpt-mini → review (fallback, данные не теряем)")


def test_garbage_json_fallback_review():
    items = [_item("Y1", "кейс")]
    sp.chat = lambda *a, **k: "извините, вот ответ: не-json"
    res = sp.triage(items, post_types=["photo", "carousel"], now=NOW)
    assert res[0]["verdict"] == "review", res
    print("OK  мусорный JSON → review (fallback)")


def test_no_gpt_call_when_level0_drops_all():
    items = [_item("VID", "x", typ="Video")]
    calls = {"n": 0}

    def counting(*a, **k):
        calls["n"] += 1
        return "[]"

    sp.chat = counting
    res = sp.triage(items, post_types=["photo", "carousel"], now=NOW)
    assert calls["n"] == 0, "L1 не должен вызываться, если L0 всё отсеял"
    assert res[0]["verdict"] == "drop", res
    print("OK  нет GPT-вызова, когда L0 отсеял всё (экономия денег)")


def test_personal_hint_does_not_override_keep():
    # caption с личным маркером ('путешеств'), но L1 говорит professional →
    # _looks_personal лишь помечает reason, вердикт остаётся keep (нет ложного drop).
    items = [_item("Z1", "как мы выросли за путешествие по рынку SMM")]
    sp.chat = _fake_chat(["professional"])
    res = sp.triage(items, post_types=["photo", "carousel"], now=NOW)
    assert res[0]["verdict"] == "keep", res
    assert "сигнал:личное" in res[0]["reason"], res
    print("OK  _looks_personal — только сигнал, ложного drop нет")


if __name__ == "__main__":
    test_professional_personal_mixed()
    test_old_post_dropped_at_level0()
    test_irrelevant_type_dropped_at_level0()
    test_gpt_failure_fallback_review()
    test_garbage_json_fallback_review()
    test_no_gpt_call_when_level0_drops_all()
    test_personal_hint_does_not_override_keep()
    print("\n✅ все тесты triage пройдены")
