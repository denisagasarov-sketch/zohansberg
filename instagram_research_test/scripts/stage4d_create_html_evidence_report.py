#!/usr/bin/env python3
"""
Stage 4D: HTML Evidence Report Generator

Вход:
  data/normalized/stage4a_openai_plan.json
  data/normalized/stage4a_media_manifest.json
  analysis/stage4b/posts/*.json
  analysis/stage4b/highlight_batches/*.json
  analysis/stage4c/highlight_summary.json
  analysis/stage4c/account_summary.json

Выход:
  report/final_one_account_analysis_vlada_kliuiko.html

Не требует OpenAI, Apify, интернета, .env.
Запускать из корня проекта (instagram_research_test/):
  python scripts/stage4d_create_html_evidence_report.py
"""

import json
import sys
from html import escape
from pathlib import Path

BASE = Path(__file__).parent.parent  # instagram_research_test/
REPORT_DIR = BASE / "report"
OUT_PATH = REPORT_DIR / "final_one_account_analysis_vlada_kliuiko.html"

PLAN_PATH          = BASE / "data/normalized/stage4a_openai_plan.json"
MANIFEST_PATH      = BASE / "data/normalized/stage4a_media_manifest.json"
POSTS_DIR          = BASE / "analysis/stage4b/posts"
BATCHES_DIR        = BASE / "analysis/stage4b/highlight_batches"
HIGHLIGHT_SUMMARY  = BASE / "analysis/stage4c/highlight_summary.json"
ACCOUNT_SUMMARY    = BASE / "analysis/stage4c/account_summary.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path, default=None):
    """Load JSON; return default on any error."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  WARNING: не удалось загрузить {path}: {exc}", file=sys.stderr)
        return {} if default is None else default


def h(value):
    """HTML-escape any value."""
    return escape(str(value) if value is not None else "")


_EMPTY_VALS = {"not found", "not enough evidence", "n/a", "", "none", "—"}


def is_empty(value):
    return str(value or "").strip().lower() in _EMPTY_VALS


def badge(text, style="default"):
    colors = {
        "ok": "#27ae60", "partial": "#e67e22", "fail": "#c0392b",
        "high": "#27ae60", "medium": "#e67e22", "low": "#e74c3c",
        "role": "#2980b9", "trust": "#8e44ad", "warning": "#e67e22",
        "default": "#7f8c8d",
    }
    color = colors.get(str(style).lower(), colors["default"])
    return f'<span class="badge" style="background:{color}">{h(text)}</span>'


def img_thumb(src_path, alt_text=""):
    """
    Return clickable thumbnail HTML.
    src_path — путь относительно BASE (например output/openai_inputs/...).
    HTML-файл лежит в report/, поэтому используем ../src_path.
    """
    if not src_path:
        return ""
    href = "../" + str(src_path).replace("\\", "/")
    alt  = h(alt_text or Path(src_path).name)
    return (
        f'<a href="{h(href)}" target="_blank" class="thumb-link">'
        f'<img src="{h(href)}" alt="{alt}" class="thumb" '
        f'onerror="this.parentElement.style.opacity=\'0.3\'">'
        f'</a>'
    )


def render_evidence_list(evidence):
    if not evidence:
        return '<p class="dim">Evidence отсутствует в JSON</p>'
    items = "".join(f"<li>{h(e)}</li>" for e in evidence)
    return f'<ul class="evidence-list">{items}</ul>'


def render_source_refs(refs):
    if not refs:
        return ""
    spans = " ".join(f'<code class="ref">{h(r)}</code>' for r in refs)
    return f'<div class="source-refs">Источник: {spans}</div>'


def field_value_or_warning(label, value):
    if is_empty(value):
        return f'<span class="not-found">⚠ {h(label)}: не обнаружено</span>'
    return f'<span class="found-val">{h(value)}</span>'


# ---------------------------------------------------------------------------
# Index builders
# ---------------------------------------------------------------------------

def build_post_plan_index(plan):
    """request_id → plan entry dict"""
    return {req["request_id"]: req for req in plan.get("posts_plan", [])}


def build_hl_plan_index(plan):
    """request_id → batch plan entry dict"""
    return {req["request_id"]: req for req in plan.get("highlight_batches_plan", [])}


def build_story_index(manifest):
    """
    story_id (str) → {story_number, prepared_paths: []}
    из media manifest.
    """
    idx = {}
    for s in manifest.get("highlight", {}).get("stories", []):
        sid = str(s.get("story_id", ""))
        paths = [
            inp["prepared_path"]
            for inp in s.get("prepared_inputs", [])
            if inp.get("prepared_path") and inp.get("used_for_openai_plan")
        ]
        idx[sid] = {
            "story_number": s.get("story_number"),
            "prepared_paths": paths,
        }
    return idx


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f4f6f8;
    color: #2c3e50;
    font-size: 14px;
    line-height: 1.55;
}

/* ---- header / nav ---- */
.page-header {
    background: #1a252f;
    color: #ecf0f1;
    padding: 22px 32px;
    border-bottom: 3px solid #2980b9;
}
.page-header h1 { font-size: 20px; font-weight: 700; }
.page-header .meta { font-size: 12px; color: #95a5a6; margin-top: 6px; }
nav {
    background: #2c3e50;
    padding: 0 24px;
    display: flex;
    flex-wrap: wrap;
    gap: 0;
    border-bottom: 2px solid #1a252f;
    position: sticky;
    top: 0;
    z-index: 100;
}
nav a {
    color: #bdc3c7;
    text-decoration: none;
    padding: 9px 14px;
    font-size: 12px;
    border-bottom: 2px solid transparent;
    display: block;
    white-space: nowrap;
}
nav a:hover { color: #ecf0f1; border-bottom-color: #2980b9; }

/* ---- layout ---- */
.container { max-width: 1300px; margin: 0 auto; padding: 24px 28px; }
section { margin-bottom: 44px; }
section h2 {
    font-size: 17px;
    font-weight: 700;
    color: #1a252f;
    padding-bottom: 10px;
    border-bottom: 2px solid #2980b9;
    margin-bottom: 18px;
}
section h3 { font-size: 14px; font-weight: 600; color: #2c3e50; margin: 14px 0 6px; }
section h4 { font-size: 12px; font-weight: 700; text-transform: uppercase; color: #7f8c8d; margin: 10px 0 4px; }

/* ---- cards ---- */
.card {
    background: #fff;
    border-radius: 6px;
    border: 1px solid #dce3ea;
    margin-bottom: 18px;
    overflow: hidden;
}
.card-header {
    background: #eaf0f6;
    padding: 9px 14px;
    font-weight: 600;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    border-bottom: 1px solid #d5dde6;
}
.card-body { padding: 14px 16px; }

/* ---- post layout ---- */
.post-layout {
    display: grid;
    grid-template-columns: 200px 1fr;
    min-height: 140px;
}
.post-visuals {
    background: #1a252f;
    padding: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-content: flex-start;
    border-right: 1px solid #2c3e50;
}
.post-analysis { padding: 14px 16px; overflow: hidden; }

/* ---- thumbnails ---- */
.thumb-link { display: inline-block; vertical-align: top; }
.thumb {
    width: 84px;
    height: 84px;
    object-fit: cover;
    border-radius: 4px;
    border: 1px solid #333;
    display: block;
    background: #2c3e50;
}
.story-cell .thumb { width: 88px; height: 88px; }

/* ---- fields ---- */
.field-row {
    display: flex;
    gap: 8px;
    margin-bottom: 6px;
    flex-wrap: wrap;
    align-items: baseline;
}
.field-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    color: #95a5a6;
    min-width: 110px;
    flex-shrink: 0;
}
.field-value { font-size: 13px; flex: 1; }

/* ---- evidence block ---- */
.evidence-block {
    background: #f7f9fc;
    border-left: 3px solid #2980b9;
    padding: 8px 12px;
    margin-top: 12px;
    border-radius: 0 4px 4px 0;
}
.evidence-list { padding-left: 16px; }
.evidence-list li { margin-bottom: 4px; font-size: 12px; }

/* ---- badges & refs ---- */
.badge {
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    display: inline-block;
    line-height: 1.4;
}
.ref {
    background: #ecf0f1;
    color: #2c3e50;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    font-family: monospace;
}
.source-refs { font-size: 11px; color: #95a5a6; margin-top: 3px; margin-bottom: 6px; }
.not-found { color: #e67e22; font-size: 12px; }
.found-val { color: #2c3e50; font-size: 13px; }
.dim { color: #95a5a6; font-style: italic; font-size: 12px; }

/* ---- story grid ---- */
.story-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
}
.story-cell {
    background: #1a252f;
    border-radius: 4px;
    padding: 6px;
    text-align: center;
    width: 102px;
    flex-shrink: 0;
}
.story-num { font-size: 10px; color: #95a5a6; margin-top: 4px; }
.story-id-label { font-size: 9px; color: #636e72; word-break: break-all; }

/* ---- batch ---- */
.batch-header {
    background: #2c3e50;
    color: #ecf0f1;
    padding: 10px 16px;
}
.batch-header h3 { font-size: 14px; font-weight: 700; }
.batch-note {
    font-size: 11px;
    color: #f39c12;
    background: #1a252f;
    padding: 6px 16px;
    font-style: italic;
    border-bottom: 1px solid #2c3e50;
}

/* ---- quotes ---- */
.quote-item {
    background: #fff;
    border-left: 3px solid #8e44ad;
    padding: 10px 14px;
    margin-bottom: 8px;
    border-radius: 0 4px 4px 0;
    font-size: 13px;
    border: 1px solid #dce3ea;
    border-left-width: 3px;
}
.quote-meta { font-size: 11px; color: #95a5a6; margin-top: 5px; }

/* ---- trust / ideas / limitations ---- */
.item-block {
    background: #fff;
    border: 1px solid #dce3ea;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 10px;
}
.item-block .item-title { font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.limitation-box {
    background: #fef9e7;
    border: 1px solid #f5b942;
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
    color: #7d6608;
    font-size: 13px;
}

/* ---- two-col grid ---- */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 860px) {
    .two-col { grid-template-columns: 1fr; }
    .post-layout { grid-template-columns: 1fr; }
}
"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def section_summary(acc, hl):
    parts = []
    parts.append('<section id="summary">')
    parts.append('<h2>1. Короткое резюме</h2>')
    parts.append('<div class="two-col">')

    # --- левая колонка ---
    parts.append('<div>')

    # Что продает
    primary_offer = acc.get("primary_offer", {})
    parts.append('<div class="card">')
    parts.append('<div class="card-header">Что продает аккаунт</div>')
    parts.append('<div class="card-body">')
    pv = primary_offer.get("value", "не определено")
    parts.append(f'<p style="font-size:14px;margin-bottom:6px">{h(pv)}</p>')
    parts.append(render_source_refs(primary_offer.get("source_refs", [])))
    parts.append('</div></div>')

    # Роль постов (funnel)
    funnel_roles = acc.get("funnel_roles", {})
    parts.append('<div class="card">')
    parts.append('<div class="card-header">Роль постов (funnel)</div>')
    parts.append('<div class="card-body">')
    any_role = False
    for role, srcs in funnel_roles.items():
        if srcs:
            any_role = True
            refs_html = " ".join(f'<code class="ref">{h(s)}</code>' for s in srcs[:6])
            suffix = f' <span class="dim">…ещё {len(srcs)-6}</span>' if len(srcs) > 6 else ''
            parts.append(
                f'<div class="field-row">'
                f'<span class="field-label">{h(role)}</span>'
                f'<span class="field-value">{refs_html}{suffix}</span>'
                f'</div>'
            )
    if not any_role:
        parts.append('<p class="dim">Нет данных</p>')
    parts.append('</div></div>')

    # Роль хайлайта
    hl_dominant = hl.get("dominant_role", "—")
    hl_summary  = hl.get("summary", "")
    hl_stories  = hl.get("stories_total", "?")
    hl_batches  = hl.get("batches_analyzed", "?")
    parts.append('<div class="card">')
    parts.append('<div class="card-header">Роль хайлайта</div>')
    parts.append('<div class="card-body">')
    if hl_summary:
        parts.append(f'<p style="margin-bottom:8px">{h(hl_summary)}</p>')
    parts.append(
        f'<div class="field-row">'
        f'<span class="field-label">Доминирует</span>'
        f'<span class="field-value">{badge(hl_dominant, "role")}</span>'
        f'</div>'
    )
    hl_roles = hl.get("role_frequency", {})
    if hl_roles:
        roles_str = ", ".join(
            f"{r} ({c})" for r, c in sorted(hl_roles.items(), key=lambda x: -x[1])
        )
        parts.append(f'<div style="font-size:12px;color:#7f8c8d;margin-top:4px">{h(roles_str)}</div>')
    parts.append(
        f'<div class="field-row" style="margin-top:6px">'
        f'<span class="field-label">Объем</span>'
        f'<span class="field-value">{hl_stories} историй, {hl_batches} батчей</span>'
        f'</div>'
    )
    parts.append('</div></div>')
    parts.append('</div>')  # left col

    # --- правая колонка ---
    parts.append('<div>')

    # На чем строится доверие
    trust_mechanics = acc.get("trust_mechanics", [])
    parts.append('<div class="card">')
    parts.append('<div class="card-header">На чём строится доверие</div>')
    parts.append('<div class="card-body">')
    if trust_mechanics:
        for tm in trust_mechanics[:6]:
            parts.append(f'<div style="margin-bottom:6px">{h(tm.get("mechanic", ""))}</div>')
            parts.append(render_source_refs(tm.get("source_refs", [])))
    else:
        parts.append('<p class="dim">Нет данных</p>')
    parts.append('</div></div>')

    # Слабые места
    weak_spots = acc.get("weak_spots", [])
    parts.append('<div class="card">')
    parts.append('<div class="card-header">Слабые места / пробелы</div>')
    parts.append('<div class="card-body">')
    if weak_spots:
        for ws in weak_spots:
            parts.append(
                f'<div style="margin-bottom:8px">'
                f'<span style="color:#e67e22">⚠</span> {h(ws.get("spot", ""))}'
                f'</div>'
            )
            parts.append(render_source_refs(ws.get("source_refs", [])))
    else:
        parts.append('<p class="dim">Нет данных</p>')
    parts.append('</div></div>')

    # Уверенность
    conf_acc = acc.get("confidence", "?")
    conf_hl  = hl.get("confidence", "?")
    n_posts  = acc.get("analyzed_posts_count", "?")
    parts.append('<div class="card">')
    parts.append('<div class="card-header">Уверенность анализа</div>')
    parts.append('<div class="card-body">')
    parts.append(
        f'<div class="field-row">'
        f'<span class="field-label">Посты ({n_posts} шт.)</span>'
        f'<span class="field-value">{badge(conf_acc, conf_acc)}</span>'
        f'</div>'
    )
    parts.append(
        f'<div class="field-row">'
        f'<span class="field-label">Хайлайт</span>'
        f'<span class="field-value">{badge(conf_hl, conf_hl)}</span>'
        f'</div>'
    )
    parts.append('</div></div>')
    parts.append('</div>')  # right col

    parts.append('</div>')  # two-col
    parts.append('</section>')
    return "\n".join(parts)


def section_posts(posts_data, plan_index):
    parts = []
    parts.append('<section id="posts">')
    parts.append('<h2>2. Посты: визуальный разбор</h2>')

    if not posts_data:
        parts.append('<p class="dim">Файлы analysis/stage4b/posts/ не найдены.</p>')
        parts.append('</section>')
        return "\n".join(parts)

    for request_id, post in posts_data:
        plan_entry     = plan_index.get(request_id, {})
        prepared_paths = plan_entry.get("prepared_paths", [])

        im           = post.get("inferred_meanings", {})
        obs          = post.get("observed_facts", {})
        status       = post.get("status", "?")
        confidence   = post.get("confidence", "?")
        content_id   = post.get("content_id", request_id)
        url          = post.get("url", "")
        ptype        = post.get("type", "?")
        funnel_role  = im.get("funnel_role", "?")
        topic        = im.get("topic", "")
        fmt          = im.get("format", "")
        hook         = im.get("hook", "")
        cta          = im.get("cta", "")
        offer        = im.get("offer", "")
        sp           = im.get("social_proof", "")
        evidence     = post.get("evidence", [])
        limitations  = post.get("limitations", [])
        cap_facts    = obs.get("caption_facts", [])
        vis_facts    = obs.get("visual_facts", [])

        parts.append(f'<div class="card" id="post-{h(content_id)}">')

        # header
        url_link = (
            f'<a href="{h(url)}" target="_blank" '
            f'style="font-size:11px;color:#2980b9;margin-left:4px">{h(url[:70])}</a>'
            if url else ""
        )
        parts.append(
            f'<div class="card-header">'
            f'{badge(status, status.lower())} '
            f'<span>{h(content_id)}</span> '
            f'{badge(ptype, "default")} '
            f'{badge(funnel_role, "role")} '
            f'уверенность: {badge(confidence, confidence)}'
            f'{url_link}'
            f'</div>'
        )

        # two-panel: visuals | analysis
        parts.append('<div class="post-layout">')

        # visuals
        parts.append('<div class="post-visuals">')
        if prepared_paths:
            for pp in prepared_paths:
                parts.append(img_thumb(pp, Path(pp).name))
        else:
            parts.append('<p class="dim" style="color:#636e72;font-size:11px">Нет путей в плане</p>')
        parts.append('</div>')

        # analysis
        parts.append('<div class="post-analysis">')

        def fr(label, value):
            return (
            f'<div class="field-row">'
            f'<span class="field-label">{h(label)}</span>'
            f'<span class="field-value">{h(value) if value else "<span class=\'dim\'>—</span>"}</span>'
            f'</div>'
        )

        parts.append(fr("Тема", topic))
        parts.append(fr("Формат", fmt))
        parts.append(fr("Хук", hook))
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">CTA</span>'
            f'<span class="field-value">{field_value_or_warning("CTA", cta)}</span>'
            f'</div>'
        )
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">Оффер</span>'
            f'<span class="field-value">{field_value_or_warning("Оффер", offer)}</span>'
            f'</div>'
        )
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">Соц. докво</span>'
            f'<span class="field-value">{field_value_or_warning("Соц. докво", sp)}</span>'
            f'</div>'
        )

        if cap_facts:
            parts.append('<h4>Факты из caption</h4>')
            parts.append('<ul class="evidence-list">')
            for f_ in cap_facts:
                parts.append(f'<li>{h(f_)}</li>')
            parts.append('</ul>')

        if vis_facts:
            parts.append('<h4>Визуальные факты</h4>')
            parts.append('<ul class="evidence-list">')
            for f_ in vis_facts:
                parts.append(f'<li>{h(f_)}</li>')
            parts.append('</ul>')

        if limitations:
            lim_visible = [l for l in limitations if not str(l).startswith("missing")]
            if lim_visible:
                parts.append('<h4>Ограничения</h4>')
                parts.append('<ul class="evidence-list">')
                for lim in lim_visible:
                    parts.append(f'<li style="color:#e67e22">{h(lim)}</li>')
                parts.append('</ul>')

        parts.append('<div class="evidence-block">')
        parts.append('<h4>Evidence</h4>')
        parts.append(render_evidence_list(evidence))
        parts.append('</div>')

        parts.append('</div>')  # post-analysis
        parts.append('</div>')  # post-layout
        parts.append('</div>')  # card

    parts.append('</section>')
    return "\n".join(parts)


def section_highlights(batches_data, hl_plan_index, story_index):
    parts = []
    parts.append('<section id="highlights">')
    parts.append('<h2>3. Хайлайт: все stories и доказательства</h2>')
    parts.append(
        '<div class="batch-note">'
        '⚠ Цитаты ниже относятся к batch, а не гарантированно к конкретной story.'
        '</div>'
    )

    if not batches_data:
        parts.append('<p class="dim" style="margin-top:12px">Файлы analysis/stage4b/highlight_batches/ не найдены.</p>')
        parts.append('</section>')
        return "\n".join(parts)

    for batch_id, batch in batches_data:
        plan_entry     = hl_plan_index.get(batch_id, {})
        prepared_paths = plan_entry.get("prepared_paths", [])

        im           = batch.get("inferred_meanings", {})
        obs          = batch.get("observed_facts", {})
        status       = batch.get("status", "?")
        confidence   = batch.get("confidence", "?")
        batch_idx    = batch.get("batch_index", "?")
        story_numbers = batch.get("story_numbers", [])
        story_ids    = batch.get("story_ids", [])
        main_roles   = im.get("main_roles", [])
        cta          = im.get("cta_found", "")
        offer        = im.get("offer_found", "")
        sp           = im.get("social_proof_found", "")
        trust_mechs  = im.get("trust_mechanics", [])
        summary_text = im.get("summary", "")
        dss          = im.get("decision_support_score", None)
        evidence     = batch.get("evidence", [])
        visible_text = obs.get("visible_text", [])

        parts.append(f'<div class="card" id="{h(batch_id)}">')

        # batch header
        roles_html = " ".join(badge(r, "role") for r in main_roles)
        parts.append('<div class="batch-header">')
        parts.append(
            f'<h3>Batch {h(batch_idx)} '
            f'— stories {h(str(story_numbers))}</h3>'
        )
        dss_str = f' · DSS {h(str(dss))}/10' if dss is not None else ''
        parts.append(
            f'<div style="margin-top:5px">{roles_html} '
            f'{badge(status, status.lower())} '
            f'уверенность: {badge(confidence, confidence)}{h(dss_str)}</div>'
        )
        parts.append('</div>')

        parts.append('<div class="card-body">')

        if summary_text:
            parts.append(f'<p style="margin-bottom:12px;font-size:13px">{h(summary_text)}</p>')

        # two-col: fields | story grid
        parts.append('<div class="two-col">')

        # left: fields + evidence
        parts.append('<div>')
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">CTA</span>'
            f'<span class="field-value">{field_value_or_warning("CTA", cta)}</span>'
            f'</div>'
        )
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">Оффер</span>'
            f'<span class="field-value">{field_value_or_warning("Оффер", offer)}</span>'
            f'</div>'
        )
        parts.append(
            f'<div class="field-row">'
            f'<span class="field-label">Соц. докво</span>'
            f'<span class="field-value">{field_value_or_warning("Соц. докво", sp)}</span>'
            f'</div>'
        )

        if trust_mechs:
            parts.append('<h4>Механики доверия</h4>')
            parts.append('<ul class="evidence-list">')
            for tm in trust_mechs:
                parts.append(f'<li>{h(tm)}</li>')
            parts.append('</ul>')

        if visible_text:
            parts.append('<h4>Видимый текст в stories</h4>')
            parts.append('<ul class="evidence-list">')
            for vt in visible_text[:12]:
                parts.append(f'<li>&#8220;{h(vt)}&#8221;</li>')
            if len(visible_text) > 12:
                parts.append(f'<li class="dim">…ещё {len(visible_text)-12} строк</li>')
            parts.append('</ul>')

        parts.append('<div class="evidence-block">')
        parts.append('<h4>Evidence</h4>')
        parts.append(render_evidence_list(evidence))
        parts.append('</div>')
        parts.append('</div>')  # left

        # right: story grid
        parts.append('<div>')
        parts.append('<h4>Кадры и stories</h4>')
        parts.append('<div class="story-grid">')

        for i, (sid, snum) in enumerate(zip(story_ids, story_numbers)):
            s_info  = story_index.get(str(sid), {})
            s_paths = s_info.get("prepared_paths", [])

            # Fallback: divide batch prepared_paths across stories by index
            if not s_paths and prepared_paths:
                n_stories = max(1, len(story_ids))
                per = max(1, len(prepared_paths) // n_stories)
                s_paths = prepared_paths[i * per:(i + 1) * per]

            parts.append('<div class="story-cell">')
            if s_paths:
                parts.append(img_thumb(s_paths[0], f"Story {snum}"))
            else:
                parts.append(
                    '<div class="thumb" style="display:flex;align-items:center;'
                    'justify-content:center;color:#636e72;font-size:10px">нет</div>'
                )
            parts.append(f'<div class="story-num">#{h(str(snum))}</div>')
            sid_str = str(sid)
            sid_display = sid_str[:14] + "…" if len(sid_str) > 14 else sid_str
            parts.append(f'<div class="story-id-label">{h(sid_display)}</div>')
            parts.append('</div>')

        parts.append('</div>')  # story-grid
        parts.append('</div>')  # right
        parts.append('</div>')  # two-col
        parts.append('</div>')  # card-body
        parts.append('</div>')  # card

    parts.append('</section>')
    return "\n".join(parts)


def section_quotes(batches_data):
    parts = []
    parts.append('<section id="quotes">')
    parts.append('<h2>4. Все цитаты из хайлайта</h2>')
    parts.append(
        '<p class="dim" style="margin-bottom:14px">'
        '⚠ Цитаты привязаны к batch, не к конкретной story — '
        'Stage 4B анализировал batches.'
        '</p>'
    )

    seen = {}  # normalized_key → {text, source, roles}
    for batch_id, batch in batches_data:
        main_roles   = batch.get("inferred_meanings", {}).get("main_roles", [])
        visible_text = batch.get("observed_facts", {}).get("visible_text", [])
        for vt in visible_text:
            key = str(vt).strip().lower()
            if key and key not in seen:
                seen[key] = {
                    "text":   str(vt).strip(),
                    "source": batch_id,
                    "roles":  main_roles,
                }

    if not seen:
        parts.append('<p class="dim">visible_text не найден в JSON батчей.</p>')
    else:
        for item in seen.values():
            roles_html = " ".join(badge(r, "role") for r in item["roles"])
            parts.append('<div class="quote-item">')
            parts.append(f'&#8220;{h(item["text"])}&#8221;')
            parts.append(
                f'<div class="quote-meta">'
                f'<code class="ref">{h(item["source"])}</code> {roles_html}'
                f'</div>'
            )
            parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def section_trust(acc, hl):
    parts = []
    parts.append('<section id="trust">')
    parts.append('<h2>5. Механики доверия</h2>')

    # merge from both summaries
    merged = {}
    for tm in acc.get("trust_mechanics", []):
        key = tm.get("mechanic", "").strip().lower()
        if key:
            merged[key] = {
                "mechanic": tm.get("mechanic", ""),
                "source_refs": list(tm.get("source_refs", [])),
                "origin": ["account_summary"],
            }
    for tm in hl.get("trust_mechanics", []):
        key = tm.get("mechanic", "").strip().lower()
        if not key:
            continue
        if key in merged:
            existing = merged[key]["source_refs"]
            for ref in tm.get("source_refs", []):
                if ref not in existing:
                    existing.append(ref)
            if "highlight_summary" not in merged[key]["origin"]:
                merged[key]["origin"].append("highlight_summary")
        else:
            merged[key] = {
                "mechanic": tm.get("mechanic", ""),
                "source_refs": list(tm.get("source_refs", [])),
                "origin": ["highlight_summary"],
            }

    if not merged:
        parts.append('<p class="dim">Механики доверия не найдены в JSON.</p>')
    else:
        for item in merged.values():
            origins_html = " ".join(
                f'<code class="ref">{h(o)}</code>' for o in item["origin"]
            )
            parts.append('<div class="item-block">')
            parts.append(f'<div class="item-title">{h(item["mechanic"])}</div>')
            parts.append(f'<div style="font-size:11px;color:#7f8c8d">Из: {origins_html}</div>')
            parts.append(render_source_refs(item["source_refs"]))
            parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def section_ideas(acc):
    parts = []
    parts.append('<section id="ideas">')
    parts.append('<h2>6. Что можно забрать себе</h2>')

    ideas = acc.get("ideas_to_adapt", [])
    if not ideas:
        parts.append('<p class="dim">Данные отсутствуют в account_summary.json</p>')
    else:
        for idea in ideas:
            parts.append('<div class="item-block">')
            parts.append(f'<div class="item-title">{h(idea.get("idea", ""))}</div>')
            parts.append(render_source_refs(idea.get("source_refs", [])))
            parts.append('</div>')

    parts.append('</section>')
    return "\n".join(parts)


def section_limitations():
    items = [
        "Bio не анализировали — прямая ссылка и оффер в bio неизвестны.",
        "Pinned posts не анализировали отдельно.",
        "Только один хайлайт анализировался — полный профиль хайлайтов может отличаться.",
        "Сайт, бот, воронка не анализировались.",
        (
            "Часть связок quote → exact story недоступна: "
            "Stage 4B анализировал batches, а не отдельные stories. "
            "Видимый текст привязан к batch, не к конкретной story."
        ),
        "Score (1–10) в JSON постов ненадежен — не используется как сигнал качества.",
        "Синтез Stage 4C полностью локальный — LLM-интерпретация не применялась на этапе агрегации.",
    ]
    parts = []
    parts.append('<section id="limitations">')
    parts.append('<h2>7. Ограничения анализа</h2>')
    for item in items:
        parts.append(f'<div class="limitation-box">{h(item)}</div>')
    parts.append('</section>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

def build_html(body_html, acc, hl):
    status_acc = acc.get("status", "?")
    status_hl  = hl.get("status", "?")
    nav_items = [
        ("#summary",     "1. Резюме"),
        ("#posts",       "2. Посты"),
        ("#highlights",  "3. Хайлайт"),
        ("#quotes",      "4. Цитаты"),
        ("#trust",       "5. Доверие"),
        ("#ideas",       "6. Идеи"),
        ("#limitations", "7. Ограничения"),
    ]
    nav_html = "\n".join(
        f'<a href="{h(href)}">{h(label)}</a>' for href, label in nav_items
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Анализ Instagram-аккаунта vlada_kliuiko</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="page-header">
  <h1>Анализ Instagram-аккаунта: vlada_kliuiko</h1>
  <div class="meta">
    Stage 4D · HTML Evidence Report
    · account_summary: {badge(status_acc, status_acc.lower())}
    · highlight_summary: {badge(status_hl, status_hl.lower())}
  </div>
</div>
<nav>{nav_html}</nav>
<div class="container">
{body_html}
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("Stage 4D: создание HTML evidence report...")

    plan              = load_json(PLAN_PATH)
    manifest          = load_json(MANIFEST_PATH)
    account_summary   = load_json(ACCOUNT_SUMMARY)
    highlight_summary = load_json(HIGHLIGHT_SUMMARY)

    # Load post JSONs
    posts_data = []
    if POSTS_DIR.exists():
        for pf in sorted(POSTS_DIR.glob("*.json")):
            data = load_json(pf)
            if data:
                posts_data.append((pf.stem, data))
    else:
        print(f"  WARNING: {POSTS_DIR} не найдена", file=sys.stderr)

    # Load batch JSONs
    batches_data = []
    if BATCHES_DIR.exists():
        for bf in sorted(BATCHES_DIR.glob("*.json")):
            data = load_json(bf)
            if data:
                batches_data.append((bf.stem, data))
    else:
        print(f"  WARNING: {BATCHES_DIR} не найдена", file=sys.stderr)

    plan_index    = build_post_plan_index(plan)
    hl_plan_index = build_hl_plan_index(plan)
    story_index   = build_story_index(manifest)

    sections = [
        section_summary(account_summary, highlight_summary),
        section_posts(posts_data, plan_index),
        section_highlights(batches_data, hl_plan_index, story_index),
        section_quotes(batches_data),
        section_trust(account_summary, highlight_summary),
        section_ideas(account_summary),
        section_limitations(),
    ]

    html = build_html("\n\n".join(sections), account_summary, highlight_summary)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")

    kb = len(html.encode("utf-8")) // 1024
    print(f"  posts загружено:   {len(posts_data)}")
    print(f"  батчей загружено:  {len(batches_data)}")
    print(f"  HTML размер:       {kb} KB")
    print(f"  сохранено:         {OUT_PATH.relative_to(BASE)}")
    print()
    print("Открыть в браузере:")
    print("  open report/final_one_account_analysis_vlada_kliuiko.html")


if __name__ == "__main__":
    main()
