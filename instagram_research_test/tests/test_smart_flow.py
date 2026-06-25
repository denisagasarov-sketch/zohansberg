"""Смоук умного флоу без реального Apify: scout и get_account_rows замоканы.
Доводим до экрана состояния и навигации по действиям (без запуска пайплайна).

Запуск из корня: python tests/test_smart_flow.py
"""
import asyncio
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)                       # пакет pipeline.*
sys.path.insert(0, os.path.join(_REPO, "scripts"))  # модуль analyze_flow рядом с ботом

import analyze_flow as af  # noqa: E402

# ── моки сети ────────────────────────────────────────────────────────────────
FAKE_SCOUT = {
    "account": "kate.jet", "total": 200, "by_type": {"photo": 5, "carousel": 40, "video": 155},
    "date_min": "2025-08-01", "date_max": "2026-06-20", "hidden_likes": 120, "est_personal": 18,
    "post_types": ["photo", "carousel"], "truncated": True,
    "period_breakdown": [
        {"months": 3,  "count": 3,  "lower_bound": False, "est_cost_usd": 0.09, "est_minutes": 1.8},
        {"months": 6,  "count": 7,  "lower_bound": False, "est_cost_usd": 0.21, "est_minutes": 4.1},
        {"months": 12, "count": 18, "lower_bound": True,  "est_cost_usd": 0.54, "est_minutes": 10.5},
        {"months": 24, "count": 18, "lower_bound": True,  "est_cost_usd": 0.54, "est_minutes": 10.5},
    ],
    "items": [{"shortCode": "X", "type": "Sidecar", "timestamp": "2026-06-01T00:00:00Z", "caption": "кейс"}],
}
FAKE_ROWS = {
    "headers": ["Дата записи", "Конкурент", "Ссылка на пост", "Заголовок поста"],
    "rows": [
        ["24.06.2026", "kate.jet", "https://www.instagram.com/p/A/", "T1"],
        ["20.05.2026", "kate.jet", "https://www.instagram.com/p/B/", "T2"],
    ],
}
af.scout = lambda u: dict(FAKE_SCOUT)
af.sheets_client.get_account_rows = lambda sheet, u: dict(FAKE_ROWS)

# ── лёгкие фейки Telegram-объектов ───────────────────────────────────────────
captured = {}


class _Msg:
    async def edit_text(self, text, **kw):
        captured["text"] = text; captured["markup"] = kw.get("reply_markup"); return self


class _Message:
    def __init__(self, text): self.text = text
    async def reply_text(self, text, **kw):
        captured["text"] = text; captured["markup"] = kw.get("reply_markup"); return _Msg()


class _Update:
    def __init__(self, text): self.message = _Message(text); self.callback_query = None


class _CQ:
    def __init__(self, data): self.data = data
    async def answer(self, *a, **k): pass
    async def edit_message_text(self, text, **kw):
        captured["text"] = text; captured["markup"] = kw.get("reply_markup"); return None


class _CQUpdate:
    def __init__(self, data): self.callback_query = _CQ(data); self.message = None


class _Ctx:
    def __init__(self): self.user_data = {}; self.args = []


def _callbacks(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row]


def test_table_state():
    st = af._table_state("kate.jet")
    assert st["ok"] and st["count"] == 2, st
    assert st["last_date"] == "24.06.2026", st  # максимум по «Дата записи»
    print("OK  _table_state: 2 строки, посл. анализ 24.06.2026")


def test_full_navigation():
    async def run():
        ctx = _Ctx()

        # entry-кнопка → просит username
        assert await af.smart_entry(_CQUpdate("smart:start"), ctx) == af.SMART_USERNAME

        # username → экран состояния
        st = await af.smart_username(_Update("@kate.jet"), ctx)
        assert st == af.SMART_ACTION, st
        txt = captured["text"]
        assert "@kate.jet" in txt and "В таблице" in txt, txt
        assert "В Instagram" in txt and "12 мес → 18+" in txt, txt
        assert ctx.user_data["smart_username"] == "kate.jet"
        assert ctx.user_data.get("smart_items") and ctx.user_data.get("smart_tbl")
        cbs = _callbacks(captured["markup"])
        assert "smartrun:replace:12" in cbs and "smartrun:upsert:12" in cbs, cbs
        assert "smartperiod:menu" in cbs

        # «Выбрать период…» → меню периодов
        assert await af.smart_action(_CQUpdate("smartperiod:menu"), ctx) == af.SMART_PERIOD
        assert "smartp:6" in _callbacks(captured["markup"])

        # 6 мес → экран режима
        assert await af.smart_period(_CQUpdate("smartp:6"), ctx) == af.SMART_PERIOD_MODE
        assert ctx.user_data["smart_months"] == 6
        assert "smartm:replace" in _callbacks(captured["markup"])

        # назад из режима → период → назад → действия (экран состояния снова)
        assert await af.smart_period_mode(_CQUpdate("smartm:back"), ctx) == af.SMART_PERIOD
        assert await af.smart_period(_CQUpdate("smartp:back"), ctx) == af.SMART_ACTION
        assert "В таблице" in captured["text"]

        # отмена
        assert await af.smart_action(_CQUpdate("smartcancel:x"), ctx) == af.ConversationHandler.END
        print("OK  entry → состояние → действие/период/режим/назад/отмена")
    asyncio.run(run())


def test_table_read_failure_graceful():
    af.sheets_client.get_account_rows = lambda sheet, u: (_ for _ in ()).throw(RuntimeError("boom"))
    st = af._table_state("kate.jet")
    assert st["ok"] is False and st["error"] == "RuntimeError", st
    af.sheets_client.get_account_rows = lambda sheet, u: dict(FAKE_ROWS)  # вернуть мок
    print("OK  сбой чтения таблицы → ok=False, не падает")


def test_conversation_builds():
    assert af.build_smart_conversation() is not None
    print("OK  build_smart_conversation собран")


if __name__ == "__main__":
    test_table_state()
    test_full_navigation()
    test_table_read_failure_graceful()
    test_conversation_builds()
    print("\n✅ смоук умного флоу пройден")
