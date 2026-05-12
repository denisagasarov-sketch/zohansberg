"""Stage 5A-2B: Report generator for pinned posts details collection.

Reads data/normalized/stage5a2b_pinned_posts_details.json and writes
report/stage_5a2b_pinned_post_details_report.md.

Does NOT call Apify, OpenAI, or any external API.
"""

import json
from pathlib import Path

BASE = Path(__file__).parent.parent

NORM_OUTPUT_PATH    = BASE / "data" / "normalized" / "stage5a2b_pinned_posts_details.json"
SCHEMA_SUMMARY_PATH = BASE / "data" / "normalized" / "stage5a2b_pinned_posts_schema_summary.json"
REPORT_PATH         = BASE / "report" / "stage_5a2b_pinned_post_details_report.md"

_CDN_MARKERS = ("cdninstagram.com", "scontent", "fbcdn.net", "lookaside.fbsbx.com")


def _redact(url) -> str:
    if not isinstance(url, str) or not url.startswith("http"):
        return str(url) if url else "—"
    if any(m in url for m in _CDN_MARKERS):
        return "<instagram_cdn_redacted>"
    return url


def create_report() -> Path:
    """Build markdown report from normalized output. Returns report path."""
    if not NORM_OUTPUT_PATH.exists():
        raise ValueError(
            f"Normalized output not found: {NORM_OUTPUT_PATH}. "
            "Run --collect or --from-existing-raw first."
        )

    output = json.loads(NORM_OUTPUT_PATH.read_text(encoding="utf-8"))
    schema = {}
    if SCHEMA_SUMMARY_PATH.exists():
        try:
            schema = json.loads(SCHEMA_SUMMARY_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    lines = []
    lines.append("# Stage 5A-2B: Pinned Posts Details Collection Report")
    lines.append("")
    lines.append(f"Account:    {output.get('account', '—')}")
    lines.append(f"Stage:      {output.get('stage', '—')}")
    lines.append(f"Run at:     {output.get('run_timestamp', '—')}")
    lines.append(f"Source:     {output.get('source', '—')}")
    lines.append(f"Actor:      {output.get('actor', '—')}")
    lines.append(f"Run ID:     {output.get('run_id') or '—'}")
    lines.append(f"Strategy:   {output.get('strategy', '—')}")
    lines.append("")

    # Summary table
    s = output.get("summary", {})
    lines.append("## 1. Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total posts collected | {output.get('total_pinned_posts', 0)} |")
    lines.append(f"| Posts with full caption | {s.get('posts_with_full_caption', 0)} |")
    lines.append(f"| Posts with cover/thumbnail | {s.get('posts_with_cover_or_thumbnail', 0)} |")
    lines.append(f"| Posts with carousel items | {s.get('posts_with_carousel_items', 0)} |")
    lines.append(f"| Caption semantic analysis possible | {s.get('caption_semantic_possible', False)} |")
    lines.append(f"| Visual/OCR input possible | {s.get('visual_ocr_input_possible', False)} |")
    lines.append("")

    warns = output.get("warnings") or []
    if warns:
        lines.append("### Warnings")
        for w in warns:
            lines.append(f"- {w}")
        lines.append("")

    # Schema summary
    lines.append("## 2. Actor Schema Summary")
    lines.append("")
    if schema:
        lines.append(f"Items inspected: {schema.get('items_count', 0)}")
        lines.append(f"Schema confidence: **{schema.get('schema_confidence', 'unknown')}**")
        lines.append("")
        confirmed_present = schema.get("confirmed_fields_present") or []
        confirmed_missing = schema.get("confirmed_fields_missing") or []
        lines.append("### Confirmed fields (from Stage 5A-1 source code)")
        lines.append("")
        lines.append("| Field | Present in output |")
        lines.append("|---|---|")
        all_confirmed = list(set(confirmed_present + confirmed_missing))
        for f in sorted(all_confirmed):
            present = "✓" if f in confirmed_present else "✗ MISSING"
            lines.append(f"| `{f}` | {present} |")
        lines.append("")

        lines.append("### Candidate media fields (discovered at runtime)")
        lines.append("")
        cand = schema.get("candidate_fields_present", {})
        lines.append(f"- display_url candidates found:  `{cand.get('display_url', [])}`")
        lines.append(f"- thumbnail candidates found:    `{cand.get('thumbnail', [])}`")
        lines.append(f"- video_url candidates found:    `{cand.get('video_url', [])}`")
        lines.append(f"- carousel candidates found:     `{cand.get('carousel', [])}`")
        lines.append("")

        cap_lengths = schema.get("caption_lengths_observed") or []
        if cap_lengths:
            lines.append(f"Caption lengths observed: {cap_lengths}")
            lines.append(f"Max caption length: {max(cap_lengths)} chars")
            lines.append("")
    else:
        lines.append("_Schema summary not available._")
        lines.append("")

    # Per-post
    lines.append("## 3. Per-Post Detail")
    lines.append("")
    for p in output.get("posts", []):
        lines.append(f"### Post {p['position']} — {_redact(p.get('permalink'))}")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append("|---|---|")
        lines.append(f"| Shortcode | `{p.get('shortcode') or '—'}` |")
        lines.append(f"| Post ID | `{p.get('post_id') or '—'}` |")
        lines.append(f"| Media type | {p.get('media_type') or '—'} |")
        lines.append(f"| Timestamp | {p.get('timestamp') or '—'} |")
        lines.append(f"| Caption available | {p.get('has_full_caption', False)} |")
        lines.append(f"| Caption length | {p.get('caption_length', 0)} chars |")
        lines.append(f"| Caption is full | {p.get('caption_is_full', 'unknown')} |")
        lines.append(f"| Has cover/thumbnail | {p.get('has_cover_or_thumbnail', False)} |")
        lines.append(f"| Display URL | {_redact(p.get('display_url'))} |")
        lines.append(f"| Thumbnail URL | {_redact(p.get('thumbnail_url'))} |")
        lines.append(f"| Video URL | {_redact(p.get('video_url'))} |")
        lines.append(f"| Carousel items | {p.get('carousel_items_count', 0)} |")
        lines.append(f"| Source quality | **{p.get('source_quality', '—')}** |")
        ar = p.get("analysis_readiness", {})
        lines.append(f"| Caption semantic possible | {ar.get('caption_semantic_possible', False)} |")
        lines.append(f"| Visual/OCR possible | {ar.get('visual_ocr_input_possible', False)} |")
        lines.append("")

        if p.get("carousel_items"):
            lines.append(f"**Carousel slides ({p['carousel_items_count']}):**")
            for slide in p["carousel_items"]:
                lines.append(
                    f"- Slide {slide['position']}: type={slide.get('media_type') or '—'}, "
                    f"display={_redact(slide.get('display_url'))}"
                )
            lines.append("")

        limitations = p.get("limitations") or []
        if limitations:
            lines.append("**Limitations:**")
            for lim in limitations:
                lines.append(f"- {lim}")
            lines.append("")

        missing = p.get("missing_fields") or []
        if missing:
            lines.append(f"**Missing fields:** {', '.join(missing)}")
            lines.append("")

    # Google Sheets improvement
    lines.append("## 4. Google Sheets Fields Improvable After This Stage")
    lines.append("")

    posts = output.get("posts", [])
    any_full_cap  = any(p.get("has_full_caption") for p in posts)
    any_cover     = any(p.get("has_cover_or_thumbnail") for p in posts)
    any_carousel  = any(p.get("has_carousel_items") for p in posts)
    cap_sem_ok    = s.get("caption_semantic_possible", False)
    vis_ok        = s.get("visual_ocr_input_possible", False)

    lines.append("| Field | Improvable now | Condition |")
    lines.append("|---|---|---|")
    lines.append(f"| Конкурент | ✓ always | — |")
    lines.append(f"| Ссылка на пост | ✓ always | — |")
    lines.append(f"| Позиция закрепа | ✓ always | — |")
    lines.append(f"| Что в тексте поста | {'✓ if full caption' if any_full_cap else '✗'} | full_caption required |")
    lines.append(f"| Тема поста | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append(f"| Почему закреплен | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append(f"| Хук / первый экран | {'✓ after Stage 5A-2D' if vis_ok else '✗ still need cover/display URL'} | cover/display URL + Vision |")
    lines.append(f"| Ключевые смыслы | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append(f"| Какой CTA | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append(f"| Куда ведет CTA | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append(f"| Роль в воронке | {'✓ after Stage 5A-2C' if cap_sem_ok else '✗ still need full caption'} | full_caption + OpenAI |")
    lines.append("")

    # Next step
    lines.append("## 5. Recommended Next Step")
    lines.append("")
    lines.append(s.get("next_stage_recommendation", "—"))
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
