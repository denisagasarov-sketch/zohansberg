"""Тесты правки пути записи (без сети, без pytest):
  1. filtered_out НЕ попадает в лист «Посты» (prepare_sheets._build_posts).
  2. Средний ERR считается только по релевантным (не filtered_out) с известным ERR;
     при отсутствии таких avg_err=None → «н/д», «ERR выше среднего?»=«н/д» у всех,
     код НЕ падает.
  3. Прямой запуск analyze() без триажа (triage=None) не сломан (triage_source=per_post).

Реальный кейс: 6 постов со скрытыми лайками (релевантные) + 1 filtered_out
с видимыми лайками (праздник).

Запуск из корня:  python tests/test_write_path.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline.stages.analyze_posts as ap       # noqa: E402
import pipeline.stages.prepare_sheets as ps       # noqa: E402


def _fake_posts():
    posts = []
    for i in range(6):  # релевантные, лайки скрыты (-1)
        posts.append({
            "shortCode": f"H{i}", "id": f"H{i}", "type": "Sidecar",
            "caption": f"кейс клиента №{i} +300к", "likesCount": -1,
            "commentsCount": 5, "timestamp": "2026-06-01T00:00:00Z",
            "url": f"https://www.instagram.com/p/H{i}/",
        })
    posts.append({  # будет filtered_out, лайки видимые → известный ERR
        "shortCode": "PRZ", "id": "PRZ", "type": "Sidecar",
        "caption": "с праздником, друзья!", "likesCount": 132,
        "commentsCount": 13, "timestamp": "2026-06-02T00:00:00Z",
        "url": "https://www.instagram.com/p/PRZ/",
    })
    return posts


def _run_analyze():
    """Прогоняет analyze() на моках, возвращает output dict."""
    tmp = Path(tempfile.mkdtemp(prefix="wp_"))
    ap._load_posts_index = lambda u: (_fake_posts(), {})
    ap._load_followers = lambda u: 10000
    ap._download_media = lambda post, pt, td: ([], "")
    ap._analyze_with_gpt = lambda **kw: {
        "title": "T", "topic": "тема", "mechanic": "Кейс / история клиента",
        "summary": "s", "hook_type": "обещание пользы", "hook_text": "h",
        "structure": "проблема→CTA", "rubric": "Кейсы и результаты",
        "what_worked": "x", "what_to_test": "y",
    }
    ap.normalized = lambda u, name: tmp / u / name
    ap.get_account = lambda u: {"posts_sheet_types": ["photo", "carousel"]}

    def fake_isrel(caption):
        if "праздник" in caption:
            return (False, "personal", "праздник")
        return (True, "professional", "ok")
    ap._is_relevant = fake_isrel

    # triage=None → прямой путь (как при CLI-запуске)
    return ap.analyze("kate.jet", content_filter="professional", triage=None)


def test_avg_err_none_and_nd_everywhere():
    out = _run_analyze()
    assert out["triage_source"] == "per_post", out["triage_source"]   # прямой путь не сломан
    assert out["posts_ok"] == 6, out["posts_ok"]
    assert out["filtered_count"] == 1, out["filtered_count"]
    assert out["review_count"] == 0, out["review_count"]
    assert out["avg_err"] is None, f"avg_err должен быть None, а не {out['avg_err']!r}"

    rows = out["rows"]
    assert len(rows) == 7, len(rows)
    kept = [r for r in rows if r["Заголовок поста"] != "filtered_out"]
    filt = [r for r in rows if r["Заголовок поста"] == "filtered_out"]
    assert len(kept) == 6 and len(filt) == 1, (len(kept), len(filt))

    for r in kept:
        assert r["Лайки"] == "скрыто", r["Лайки"]
        assert r["ERR"] == "н/д", r["ERR"]
        assert r["Средний ERR"] == "н/д", f"Средний ERR='{r['Средний ERR']}' (ожидали «н/д»)"
        assert r["ERR выше среднего?"] == "н/д", r["ERR выше среднего?"]
    print("OK  avg_err=None → «н/д», ERR выше среднего=«н/д» у всех, код не падает")
    return out


def test_build_posts_excludes_filtered_out():
    out = _run_analyze()  # 7 строк: 6 kept + 1 filtered_out
    ps.get_account = lambda u: {"posts_sheet_types": ["photo", "carousel"]}
    sources = {"stage5e1_posts": {"rows": out["rows"]}}
    rows, warnings = ps._build_posts(sources, "kate.jet")
    assert len(rows) == 6, f"в листе должно остаться 6 строк (без filtered_out), а не {len(rows)}"
    flat = [str(c) for row in rows for c in row]
    assert "filtered_out" not in flat, "filtered_out не должен попадать в лист «Посты»"
    assert any("filtered_out" in str(w) for w in warnings), warnings
    print("OK  filtered_out исключён из листа «Посты» (6 строк, есть warning)")


def test_direct_cli_path_not_broken():
    # отдельная проверка: analyze() без триажа отрабатывает и пишет файл
    out = _run_analyze()
    assert out.get("stage") == "stage5e1" and out.get("model"), out
    print("OK  прямой запуск analyze() (triage=None) не сломан")


if __name__ == "__main__":
    test_avg_err_none_and_nd_everywhere()
    test_build_posts_excludes_filtered_out()
    test_direct_cli_path_not_broken()
    print("\n✅ все тесты пути записи пройдены")
