"""Stage 5A-2C: Report generator for caption-only semantic analysis.

Reads data/normalized/stage5a2c_pinned_posts_semantic.json and writes
report/stage_5a2c_pinned_posts_caption_analysis_report.md.

Does NOT call OpenAI, Apify, or any external API.
"""

import json
from pathlib import Path

BASE = Path(__file__).parent.parent

SEMANTIC_PATH    = BASE / "data" / "normalized" / "stage5a2c_pinned_posts_semantic.json"
GS_ROWS_PATH     = BASE / "data" / "normalized" / "stage5a2c_pinned_posts_google_sheet_rows.json"
REPORT_PATH      = BASE / "report" / "stage_5a2c_pinned_posts_caption_analysis_report.md"

_CONFIDENCE_ICON = {"high": "✓✓", "medium": "✓", "low": "~"}


def _conf(val: str | None) -> str:
    return _CONFIDENCE_ICON.get(str(val).lower() if val else "", "?")


def _trunc(s: str, n: int = 120) -> str:
    if not s:
        return "—"
    return s[:n] + ("…" if len(s) > n else "")


def create_report() -> Path:
    """Build markdown report from semantic output. Returns report path."""
    if not SEMANTIC_PATH.exists():
        raise ValueError(
            f"Semantic output not found: {SEMANTIC_PATH}. "
            "Run --analyze first."
        )

    output = json.loads(SEMANTIC_PATH.read_text(encoding="utf-8"))
    gs_rows = {}
    if GS_ROWS_PATH.exists():
        try:
            gs_rows = json.loads(GS_ROWS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    lines = []
    lines.append("# Stage 5A-2C: Pinned Posts Caption Analysis Report")
    lines.append("")
    lines.append(f"Account:         {output.get('account', '—')}")
    lines.append(f"Stage:           {output.get('stage', '—')}")
    lines.append(f"Run at:          {output.get('run_timestamp', '—')}")
    lines.append(f"Model:           {output.get('model', '—')}")
    lines.append(f"Prompt version:  {output.get('prompt_version', '—')}")
    lines.append(f"Visual analyzed: {output.get('visual_analyzed', False)}")
    lines.append(f"OCR analyzed:    {output.get('ocr_analyzed', False)}")
    lines.append("")

    # Summary
    cache = output.get("cache_summary", {})
    lines.append("## 1. Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total posts | {output.get('total_posts', 0)} |")
    lines.append(f"| Cache hits | {cache.get('hits', 0)} |")
    lines.append(f"| New API calls | {cache.get('new', 0)} |")
    lines.append(f"| Failed | {cache.get('failed', 0)} |")
    lines.append(f"| Total tokens used | {output.get('total_tokens_used', 0)} |")
    lines.append(f"| Estimated cost | ${output.get('estimated_cost_usd', 0):.4f} |")
    lines.append("")

    n_analyzed = sum(
        1 for p in (output.get("posts") or [])
        if p.get("openai_status") == "analyzed"
    )
    n_failed = sum(
        1 for p in (output.get("posts") or [])
        if p.get("openai_status") not in ("analyzed",)
    )
    if n_failed:
        lines.append(f"> **{n_failed} post(s) failed analysis** — see Per-Post section for details.")
        lines.append("")

    # Per-post analysis
    lines.append("## 2. Per-Post Semantic Analysis")
    lines.append("")

    for sem in output.get("posts") or []:
        pos     = sem.get("position")
        status  = sem.get("openai_status")
        gf      = sem.get("google_sheet_fields") or {}
        conf    = sem.get("confidence") or {}
        ev      = sem.get("evidence") or {}
        warns   = sem.get("validation_warnings") or []
        limits  = sem.get("limitations") or []

        lines.append(f"### Post {pos} — {sem.get('permalink') or '—'}")
        lines.append("")
        lines.append(f"| Meta | Value |")
        lines.append("|---|---|")
        lines.append(f"| Shortcode | `{sem.get('shortcode') or '—'}` |")
        lines.append(f"| Post ID | `{sem.get('post_id') or '—'}` |")
        lines.append(f"| Media type | {sem.get('media_type') or '—'} |")
        lines.append(f"| Caption length | {sem.get('caption_length', 0)} chars |")
        lines.append(f"| OpenAI status | **{status}** |")
        lines.append(f"| Cache status | {sem.get('cache_status')} |")
        lines.append(f"| Tokens used | {sem.get('tokens_used') or 0} |")
        lines.append("")

        if status == "analyzed":
            lines.append("**Google Sheets fields:**")
            lines.append("")
            lines.append("| Field | Value | Confidence |")
            lines.append("|---|---|---|")
            gs_fields_to_show = [
                "Тема поста",
                "Почему закреплен",
                "Хук / первый экран",
                "Что в тексте поста",
                "Ключевые смыслы",
                "Какой CTA",
                "Куда ведет CTA",
                "Роль в воронке",
            ]
            for field in gs_fields_to_show:
                val     = gf.get(field, "")
                c       = _conf(conf.get(field))
                display = _trunc(val, 100) if val else "_empty_"
                lines.append(f"| {field} | {display} | {c} |")
            lines.append("")

            # Evidence quotes
            cap_quotes = ev.get("caption_quotes") or []
            cta_quotes = ev.get("cta_quotes") or []
            if cap_quotes or cta_quotes:
                lines.append("**Evidence from caption:**")
                for q in cap_quotes:
                    lines.append(f"> {q}")
                for q in cta_quotes:
                    lines.append(f"> CTA: {q}")
                lines.append("")
        else:
            lines.append(f"> **Analysis failed** — status: `{status}`")
            err = sem.get("error") or ""
            if err:
                lines.append(f"> Error: {err}")
            lines.append("")

        if warns:
            lines.append(f"**Validation warnings ({len(warns)}):**")
            for w in warns:
                lines.append(f"- {w}")
            lines.append("")

        if limits:
            lines.append("**Limitations:**")
            for lim in limits:
                lines.append(f"- {lim}")
            lines.append("")

    # Google Sheets rows preview
    lines.append("## 3. Google Sheets Rows Preview")
    lines.append("")
    headers = gs_rows.get("headers") or []
    rows_as_dicts = gs_rows.get("rows_as_dicts") or []
    if headers and rows_as_dicts:
        lines.append(f"Sheet: **{gs_rows.get('sheet', '—')}**")
        lines.append("")
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join("---" for _ in headers) + "|")
        for row_dict in rows_as_dicts:
            cells = [_trunc(str(row_dict.get(h, "") or ""), 60) for h in headers]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        note = gs_rows.get("integration_note", "")
        if note:
            lines.append(f"> {note}")
            lines.append("")
    else:
        lines.append("_Google Sheets rows output not available._")
        lines.append("")

    # Field coverage summary
    lines.append("## 4. Field Coverage After This Stage")
    lines.append("")
    posts = output.get("posts") or []
    any_analyzed = any(p.get("openai_status") == "analyzed" for p in posts)

    lines.append("| Field | Filled | Notes |")
    lines.append("|---|---|---|")
    lines.append("| Конкурент | ✓ | Always filled |")
    lines.append("| Ссылка на пост | ✓ | Always filled |")
    lines.append("| Позиция закрепа | ✓ | Always filled |")
    lines.append(f"| Тема поста | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append(f"| Почему закреплен | {'✓ (inference)' if any_analyzed else '✗'} | Starts with 'Вероятно' |")
    lines.append(f"| Хук / первый экран | ✗ empty | Requires Stage 5A-2D visual/OCR |")
    lines.append(f"| Что в тексте поста | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append(f"| Ключевые смыслы | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append(f"| Какой CTA | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append(f"| Куда ведет CTA | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append(f"| Роль в воронке | {'✓' if any_analyzed else '✗'} | Caption analysis |")
    lines.append("")

    # Next step
    lines.append("## 5. Recommended Next Steps")
    lines.append("")
    lines.append("1. **Stage 5A-2D** — Visual/OCR analysis for 'Хук / первый экран'")
    lines.append("   (requires cover/displayUrl from Stage 5A-2B)")
    lines.append("2. **Stage 5D-1.1** — Update Stage 5D-1 exporter to prefer")
    lines.append("   `stage5a2c_pinned_posts_google_sheet_rows.json` for semantic fields")
    lines.append("   in 'Закрепленные посты'")
    lines.append("3. **Stage 5D-3 re-run** — Rewrite only 'Закрепленные посты' sheet")
    lines.append("   after Stage 5D-1.1 integrates semantic fields")
    lines.append("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


if __name__ == "__main__":
    try:
        path = create_report()
        print(f"Report written: {path.relative_to(BASE)}")
    except ValueError as e:
        print(f"[ERROR] {e}")
        import sys; sys.exit(1)
