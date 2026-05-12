#!/usr/bin/env python3
"""
Stage 5A-1: Create Markdown report from normalized JSON outputs.

Читает:
  data/normalized/profile_summary.json
  data/normalized/bio_analysis.json
  data/normalized/pinned_posts_index.json
  data/normalized/stage5a_summary.json

Пишет:
  report/stage_5a1_profile_pinned_report.md

Запускать после stage5a1_collect_profile_and_pinned.py.
"""

import json
import sys
from pathlib import Path

os_import = __import__("os")
os_import.environ["PYTHONUTF8"] = "1"

BASE      = Path(__file__).parent.parent
NORM_DIR  = BASE / "data/normalized"
REPORT_DIR = BASE / "report"


def load(filename: str) -> dict:
    path = NORM_DIR / filename
    if not path.exists():
        print(f"[WARN] {path.relative_to(BASE)} not found — skipping", file=sys.stderr)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def val(field: dict) -> str:
    if not field:
        return "—"
    v = field.get("value")
    if v is None:
        return f"—  [{field.get('data_status', '')}]"
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return str(v)


def status_badge(field: dict) -> str:
    if not field:
        return ""
    s = field.get("data_status", "")
    badges = {
        "ok":           "✓ ok",
        "partial":      "~ partial",
        "missing":      "✗ missing",
        "manual_needed": "⚠ manual_needed",
    }
    return badges.get(s, s)


def build_report(ps: dict, ba: dict, pi: dict, ss: dict) -> str:
    run_ts    = ps.get("run_timestamp", "—")
    planned   = ps.get("planned_apify_calls", "—")
    actual    = ps.get("actual_apify_calls", "—")
    account   = ps.get("account", "vlada_kliuiko")

    lines = []
    a = lines.append

    a("# Stage 5A-1 — Profile + Pinned Index Report")
    a("")
    a("## Scope")
    a("")
    a("Что сделал:")
    a("- собрал профиль через `apify/instagram-scraper` режим `details`")
    a("- собрал posts (limit 30) через `apify/instagram-scraper` режим `posts` для pinned detection")
    a("- создал normalized JSON: `profile_summary.json`, `bio_analysis.json`, `pinned_posts_index.json`, `stage5a_summary.json`")
    a("")
    a("Что НЕ сделал:")
    a("- не анализировал highlights")
    a("- не анализировал landing")
    a("- не заполнял XLSX")
    a("- не запускал OpenAI")
    a("- не скачивал media")
    a("")
    a("## Run metadata")
    a("")
    a(f"- account: `{account}`")
    a(f"- run_timestamp: `{run_ts}`")
    a(f"- planned_apify_calls: {planned}")
    a(f"- actual_apify_calls: {actual}")
    run_ids = ps.get("apify_run_ids", [])
    a(f"- apify_run_ids: {run_ids if run_ids else '[]'}")
    a("")
    a("## Profile")
    a("")

    profile_fields = [
        ("username",        "username"),
        ("full_name",       "full_name"),
        ("bio_text",        "bio_text"),
        ("external_url",    "external_url"),
        ("external_url_type","external_url_type"),
        ("followers_count", "followers_count"),
        ("following_count", "following_count"),
        ("posts_count",     "posts_count"),
    ]

    a("| Field | Value | Status |")
    a("|---|---|---|")
    for label, key in profile_fields:
        field = ps.get(key, {})
        a(f"| {label} | {val(field)} | {status_badge(field)} |")
    a("")

    a("## Bio rule-based analysis")
    a("")
    a("> **Note:** This is rule-based analysis only — partial, not final interpretation.")
    a("> Fields marked `partial` or `manual_needed` require human review or OpenAI analysis (Stage 5D).")
    a("")

    bio_fields = [
        "niche", "target_audience", "result_promise", "positioning",
        "social_proof", "trust_arguments", "cta_text", "cta_destination",
    ]

    a("| Field | Value | Status |")
    a("|---|---|---|")
    for key in bio_fields:
        field = ba.get(key, {})
        a(f"| {key} | {val(field)} | {status_badge(field)} |")
    a("")

    a("## Pinned posts")
    a("")
    posts_checked = pi.get("posts_checked", 0)
    pinned_count  = pi.get("pinned_count", 0)
    detection     = pi.get("detection_method", "not_detected")
    manual_needed = pi.get("manual_needed", True)
    pinned_notes  = pi.get("notes", "")

    a(f"- posts_checked: {posts_checked}")
    a(f"- pinned_count: {pinned_count}")
    a(f"- detection_method: `{detection}`")
    a(f"- manual_needed: {manual_needed}")
    if pinned_notes:
        a(f"- notes: {pinned_notes}")
    a("")

    pinned_posts = pi.get("pinned_posts", [])
    if pinned_posts:
        a("| # | URL | Shortcode | Type | Timestamp | Caption preview |")
        a("|---|---|---|---|---|---|")
        for p in pinned_posts:
            pos       = p.get("position", "?")
            url_v     = val(p.get("url", {}))
            sc_v      = val(p.get("shortcode", {}))
            type_v    = val(p.get("type", {}))
            ts_v      = val(p.get("timestamp", {}))
            cap_v     = val(p.get("caption_preview", {}))
            cap_short = cap_v[:80] + "..." if len(cap_v) > 80 else cap_v
            a(f"| {pos} | {url_v} | {sc_v} | {type_v} | {ts_v} | {cap_short} |")
    else:
        a("No pinned posts detected.")
    a("")

    a("## Coverage by sheet")
    a("")
    coverage = ss.get("coverage_by_sheet", {})
    a("| Sheet | Status |")
    a("|---|---|")
    for sheet, status in coverage.items():
        a(f"| {sheet} | {status} |")
    a("")

    a("## Output files")
    a("")
    a("```")
    a("data/raw/stage5a1_profile_details_raw.json      ← raw details actor output (not committed)")
    a("data/raw/stage5a1_posts_for_pinned_raw.json     ← raw posts actor output (not committed)")
    a("data/normalized/profile_summary.json            ← structured profile fields")
    a("data/normalized/bio_analysis.json               ← rule-based bio analysis")
    a("data/normalized/pinned_posts_index.json         ← pinned posts list")
    a("data/normalized/stage5a_summary.json            ← stage coverage summary")
    a("report/stage_5a1_profile_pinned_report.md       ← this report")
    a("```")
    a("")

    a("## Final verdict")
    a("")
    profile_status = ss.get("profile_status", "missing")
    bio_status     = ss.get("bio_status", "missing")
    pinned_status  = ss.get("pinned_posts_status", "missing")

    if profile_status in ("ok", "partial") and pinned_count >= 3:
        verdict = "**OK** — Profile collected and 3+ pinned posts detected."
    elif profile_status in ("ok", "partial") and (pinned_count in (1, 2) or manual_needed):
        verdict = "**PARTIAL** — Profile collected, pinned posts incomplete or manual_needed."
    else:
        verdict = "**FAIL** — Profile missing. Cannot proceed."

    a(verdict)
    a("")
    a(f"- profile_status: {profile_status}")
    a(f"- bio_status: {bio_status}")
    a(f"- pinned_posts_status: {pinned_status}")
    a("")

    a("## Recommendation")
    a("")
    can_profile = ss.get("can_fill_profile_sheet", "missing")
    can_pinned  = ss.get("can_fill_pinned_posts_sheet", "manual_needed")
    blockers    = ss.get("blockers", [])
    next_rec    = ss.get("next_recommendation", "")

    a(f"- Лист 'Описание профиля': **{can_profile}** — можно заполнять факты; интерпретация (niche/positioning) требует проверки.")
    a(f"- Лист 'Закрепленные посты': **{can_pinned}**")

    if blockers:
        a("")
        a("Blockers:")
        for b in blockers:
            a(f"- {b}")

    if next_rec:
        a("")
        a(next_rec)

    a("")
    return "\n".join(lines)


def main():
    ps = load("profile_summary.json")
    ba = load("bio_analysis.json")
    pi = load("pinned_posts_index.json")
    ss = load("stage5a_summary.json")

    if not ps:
        print("[ERROR] profile_summary.json not found — run collect script first.", file=sys.stderr)
        sys.exit(1)

    report_text = build_report(ps, ba, pi, ss)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "stage_5a1_profile_pinned_report.md"
    report_path.write_text(report_text, encoding="utf-8")
    print(f"Report saved: {report_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
