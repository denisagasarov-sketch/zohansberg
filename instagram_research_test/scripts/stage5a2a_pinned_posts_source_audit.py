"""Stage 5A-2A: Pinned Posts Source Audit.

Audits data/normalized/pinned_posts_index.json to determine:
- which fields are available per post,
- what is missing,
- which Google Sheets fields can be filled now vs later,
- whether a new Apify call is needed.

Does NOT call Apify, OpenAI, or any external API.
Does NOT write to Google Sheets.
Does NOT download media.
"""

import json
import re
from pathlib import Path

BASE     = Path(__file__).parent.parent
import argparse as _argparse
_ap = _argparse.ArgumentParser(add_help=False)
_ap.add_argument("--account", default="vlada_kliuiko")
_args, _ = _ap.parse_known_args()
ACCOUNT  = _args.account
NORM_DIR = BASE / "data" / ACCOUNT / "normalized"
OUT_DIR  = NORM_DIR

PINNED_INDEX_PATH    = NORM_DIR / "pinned_posts_index.json"
PROFILE_SUMMARY_PATH = NORM_DIR / "profile_summary.json"
BIO_ANALYSIS_PATH    = NORM_DIR / "bio_analysis.json"

AUDIT_JSON_PATH   = OUT_DIR / "stage5a2a_pinned_posts_source_audit.json"
AUDIT_REPORT_PATH = BASE / "report" / "stage_5a2a_pinned_posts_source_audit.md"

EXPECTED_PINNED_COUNT = 3

GOOGLE_SHEETS_FIELDS = [
    "Конкурент",
    "Ссылка на пост",
    "Позиция закрепа",
    "Тема поста",
    "Почему закреплен",
    "Хук / первый экран",
    "Что в тексте поста",
    "Ключевые смыслы",
    "Какой CTA",
    "Куда ведет CTA",
    "Роль в воронке",
]

# CTA signal words (Russian Instagram conventions)
_CTA_KEYWORDS = [
    "записаться", "ссылка", "переходи", "жми", "нажми", "напиши",
    "пиши", "директ", "dm ", "в директ", "подписаться", "регистрация",
    "скачать", "получить", "узнать", "курс", "консультация", "разбор",
    "сохрани", "поделись", "комментируй", "отмечай",
]

_TRUNCATION_SIGNALS = ["...", "…", "[truncated]"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fval(d, *keys):
    """Extract .value from field-wrapper or plain value."""
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict) and "value" in v:
            val = v["value"]
            if val is not None and val != "" and val != []:
                return val
        elif v is not None and v != "" and v != []:
            return v
    return None


def _fstatus(d, *keys) -> str | None:
    if not isinstance(d, dict):
        return None
    for k in keys:
        v = d.get(k)
        if isinstance(v, dict):
            s = v.get("data_status")
            if s:
                return s
    return None


def _has_field(item: dict, key: str) -> bool:
    """Return True if field exists with status ok or partial and non-null value."""
    v = item.get(key)
    if isinstance(v, dict):
        return v.get("data_status") in ("ok", "partial") and v.get("value") not in (None, "", [])
    return v is not None and v != "" and v != []


def _detect_cta_signals(text: str) -> list[str]:
    if not text:
        return []
    t = text.lower()
    return [kw for kw in _CTA_KEYWORDS if kw in t]


def _has_truncation(text: str | None) -> bool:
    if not text:
        return False
    return any(sig in text for sig in _TRUNCATION_SIGNALS)


# ---------------------------------------------------------------------------
# Per-post audit
# ---------------------------------------------------------------------------

def audit_post(item: dict) -> dict:
    position      = item.get("position")
    permalink     = _fval(item, "url")
    shortcode     = _fval(item, "shortcode")
    post_id       = _fval(item, "content_id")
    caption_prev  = _fval(item, "caption_preview")
    media_type    = _fval(item, "type")
    timestamp     = _fval(item, "timestamp")

    cap_len        = len(caption_prev) if caption_prev else 0
    cap_truncated  = _has_truncation(caption_prev) or (cap_len == 300)
    cta_signals    = _detect_cta_signals(caption_prev or "")

    # What fields are present
    present = []
    missing = []
    for key in ("url", "content_id", "shortcode", "caption_preview", "type", "timestamp"):
        if _has_field(item, key):
            present.append(key)
        else:
            missing.append(key)

    # position is plain int, not wrapped
    if position is not None:
        present.append("position")
    else:
        missing.append("position")

    # Fields definitely NOT collected by build_pinned_posts_index
    not_collected = [
        "full_caption",
        "cover_url",
        "thumbnail_url",
        "display_url",
        "media_urls",
        "video_url",
        "carousel_items",
        "carousel_slides",
        "likes_count",
        "comments_count",
        "location",
    ]

    limitations = []
    if cap_truncated:
        limitations.append(
            "caption_preview is truncated at 300 chars — full caption not stored; "
            "semantic analysis limited"
        )
    if not caption_prev:
        limitations.append("caption_preview is missing entirely")
    if not shortcode and not post_id:
        limitations.append("neither shortcode nor content_id available — cannot construct permalink reliably")
    limitations.append("cover_url / thumbnail_url not collected — visual hook analysis impossible without new Apify call")
    limitations.append("carousel_items not collected — cannot inspect slide-level content")
    limitations.append("full caption not stored — only 300-char preview")

    return {
        "position":                    position,
        "permalink":                   permalink,
        "shortcode":                   shortcode,
        "post_id":                     post_id,
        "caption_available":           caption_prev is not None,
        "caption_is_full":             False,           # never full — build_pinned_posts_index stores only [:300]
        "caption_length":              cap_len,
        "caption_preview_length":      cap_len,
        "has_caption_truncation_signals": cap_truncated,
        "media_type_available":        media_type is not None,
        "media_type":                  media_type,
        "has_cover_url":               False,
        "has_thumbnail_url":           False,
        "has_video_url":               False,
        "has_carousel_items":          False,
        "carousel_items_count":        0,
        "has_media_urls":              False,
        "has_cta_signals_in_caption":  bool(cta_signals),
        "cta_signals_found":           cta_signals,
        "source_fields_present":       present,
        "source_fields_missing":       missing,
        "source_fields_not_collected": not_collected,
        "timestamp":                   timestamp,
        "limitations":                 limitations,
    }


# ---------------------------------------------------------------------------
# Google Sheets field assessment
# ---------------------------------------------------------------------------

def assess_google_sheets_fields(posts_audits: list) -> dict:
    """
    Classify each Google Sheets "Закрепленные посты" field by what is needed.

    Rules per spec:
    - Хук / первый экран: cannot be high-confidence without media/cover/OCR
    - Почему закреплен: always inferred, not factual
    - Какой CTA: caption-only if explicit CTA words exist, limited by 300-char cutoff
    - Куда ведет CTA: needs full caption or semantic analysis
    - Роль в воронке: requires semantic analysis
    - Full caption sufficient for caption-only semantic, not for visual hook
    """
    any_caption      = any(p["caption_available"]    for p in posts_audits)
    any_cta_signals  = any(p["has_cta_signals_in_caption"] for p in posts_audits)

    return {
        "Конкурент": {
            "can_fill_now":              True,
            "can_fill_caption_only":     True,
            "needs_full_caption":        False,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   False,
            "missing_source":            False,
            "notes": "Always filled from ACCOUNT constant or profile_summary.username",
        },
        "Ссылка на пост": {
            "can_fill_now":              True,
            "can_fill_caption_only":     False,
            "needs_full_caption":        False,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   False,
            "missing_source":            False,
            "notes": "url field available in pinned_posts_index when data_status=ok",
        },
        "Позиция закрепа": {
            "can_fill_now":              True,
            "can_fill_caption_only":     False,
            "needs_full_caption":        False,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   False,
            "missing_source":            False,
            "notes": "position plain int from enumerate; always present when posts detected",
        },
        "Тема поста": {
            "can_fill_now":              False,
            "can_fill_caption_only":     True,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   True,
            "missing_source":            False,
            "notes": (
                "300-char preview may be insufficient for reliable topic extraction; "
                "full caption + semantic analysis (OpenAI) recommended"
            ),
        },
        "Почему закреплен": {
            "can_fill_now":              False,
            "can_fill_caption_only":     False,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   True,
            "missing_source":            False,
            "notes": (
                "Always inferred, never factual. "
                "Requires full caption + semantic reasoning about post strategy role; "
                "rule-based detection not reliable"
            ),
        },
        "Хук / первый экран": {
            "can_fill_now":              False,
            "can_fill_caption_only":     False,
            "needs_full_caption":        False,
            "needs_visual_or_ocr":       True,
            "needs_semantic_analysis":   True,
            "missing_source":            True,
            "notes": (
                "Cannot be high-confidence without cover image or first slide. "
                "cover_url/thumbnail_url not collected in current pinned_posts_index. "
                "Requires new Apify call to collect displayUrl or cover, then OCR/Vision analysis"
            ),
        },
        "Что в тексте поста": {
            "can_fill_now":              True,
            "can_fill_caption_only":     True,
            "needs_full_caption":        False,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   False,
            "notes": (
                "Partially fillable now from caption_preview (first 300 chars). "
                "Marked as partial — full caption gives complete picture"
            ),
            "missing_source":            False,
        },
        "Ключевые смыслы": {
            "can_fill_now":              False,
            "can_fill_caption_only":     True,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   True,
            "missing_source":            False,
            "notes": (
                "Needs full caption for reliable extraction; "
                "300-char preview likely truncates key content; "
                "semantic analysis (OpenAI) required"
            ),
        },
        "Какой CTA": {
            "can_fill_now":              any_cta_signals,
            "can_fill_caption_only":     True,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   False,
            "missing_source":            False,
            "notes": (
                f"CTA signals {'detected in some caption previews' if any_cta_signals else 'not detected in 300-char previews'}. "
                "Explicit CTA words (записаться/переходи/ссылка) can be extracted rule-based from caption. "
                "Full caption needed because CTA often appears near the end of post text"
            ),
        },
        "Куда ведет CTA": {
            "can_fill_now":              False,
            "can_fill_caption_only":     True,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   True,
            "missing_source":            False,
            "notes": (
                "Can only fill if caption explicitly names destination (bio/direct/site/course/etc). "
                "300-char preview likely cuts off destination context. "
                "Full caption + semantic analysis needed for reliable extraction"
            ),
        },
        "Роль в воронке": {
            "can_fill_now":              False,
            "can_fill_caption_only":     False,
            "needs_full_caption":        True,
            "needs_visual_or_ocr":       False,
            "needs_semantic_analysis":   True,
            "missing_source":            False,
            "notes": (
                "Requires semantic analysis of full caption; "
                "cannot be inferred from raw structure alone; "
                "needs full caption + OpenAI reasoning about funnel role"
            ),
        },
    }


# ---------------------------------------------------------------------------
# Apify needs assessment
# ---------------------------------------------------------------------------

def assess_apify_needs(posts_audits: list) -> dict:
    all_have_caption      = all(p["caption_available"] for p in posts_audits)
    any_caption_truncated = any(p["has_caption_truncation_signals"] for p in posts_audits)

    return {
        "new_apify_call_needed": True,
        "reason": (
            "pinned_posts_index stores only 300-char caption preview. "
            "Full caption is needed for semantic analysis of all content fields. "
            "Media fields (cover_url, display_url, carousel slides) are not collected. "
            "A dedicated pinned posts detail collector is required."
        ),
        "current_caption_coverage": {
            "all_have_caption_preview": all_have_caption,
            "any_truncated":            any_caption_truncated,
            "max_chars_stored":         300,
            "full_caption_stored":      False,
        },
        "needed_from_actor": [
            "full_caption (entire post text without truncation)",
            "shortcode / id (for reliable post URL reconstruction)",
            "media_type (Image / Video / Sidecar — currently 'type' field)",
            "displayUrl or cover_image_url (first frame / cover for visual hook)",
            "thumbnailUrl / thumbnail_src (cover thumbnail)",
            "carousel slides (sidecars: first and last slide at minimum)",
            "media_urls (all image/video URLs if available)",
            "taken_at / timestamp (post date for recency context)",
        ],
        "suggested_actor": "apify/instagram-scraper with resultsType=posts, resultsLimit=30 — same as Stage 5A-1 Call 2, but save full caption without truncation and collect displayUrl",
        "can_reuse_stage5a1_actor": True,
        "stage5a1_change_needed": "Remove [:300] truncation from caption; add displayUrl, carouselMedia fields to build_pinned_posts_index",
    }


# ---------------------------------------------------------------------------
# Source quality summary
# ---------------------------------------------------------------------------

def build_source_quality_summary(index: dict, posts_audits: list) -> str:
    if not posts_audits:
        return "POOR: no pinned posts in index"
    n = len(posts_audits)
    all_url   = all(p["permalink"] for p in posts_audits)
    any_cap   = any(p["caption_available"] for p in posts_audits)
    any_trunc = any(p["has_caption_truncation_signals"] for p in posts_audits)
    any_type  = any(p["media_type_available"] for p in posts_audits)

    if all_url and any_cap and not any_trunc and any_type:
        return "GOOD: all posts have permalink, caption, type; not truncated"
    if all_url and any_cap and any_trunc:
        return "PARTIAL: all posts have permalink and partial caption (300-char preview, truncated); media fields absent"
    if all_url and not any_cap:
        return "MINIMAL: posts identified by URL only; no caption data"
    return f"PARTIAL: {n} posts; some fields missing"


# ---------------------------------------------------------------------------
# Main audit builder
# ---------------------------------------------------------------------------

def build_audit(index: dict) -> dict:
    pinned_posts  = index.get("pinned_posts") or []
    pinned_count  = index.get("pinned_count", 0)
    detection_method = index.get("detection_method", "unknown")
    manual_needed = index.get("manual_needed", False)

    posts_audits  = [audit_post(item) for item in pinned_posts]
    gs_assessment = assess_google_sheets_fields(posts_audits)
    apify_needs   = assess_apify_needs(posts_audits) if posts_audits else {
        "new_apify_call_needed": True,
        "reason": "No posts found to audit; Apify call needed to collect data",
    }

    can_now = [f for f, v in gs_assessment.items() if v.get("can_fill_now")]
    need_full_cap = [f for f, v in gs_assessment.items() if v.get("needs_full_caption") and not v.get("can_fill_now")]
    need_visual   = [f for f, v in gs_assessment.items() if v.get("needs_visual_or_ocr")]
    need_semantic = [f for f, v in gs_assessment.items() if v.get("needs_semantic_analysis") and not v.get("can_fill_now")]

    # Determine recommended next stage
    if apify_needs.get("new_apify_call_needed"):
        recommended_next_stage = (
            "Stage 5A-2B (Pinned Posts Details Collector): "
            "new Apify call to collect full caption + displayUrl/cover + carousel slides; "
            "then Stage 5A-2C (caption-only semantic analyzer using OpenAI) for text fields, "
            "and Stage 5A-2D (visual/OCR analyzer) for Хук / первый экран"
        )
    else:
        recommended_next_stage = (
            "Stage 5A-2C (caption-only semantic analyzer): "
            "full caption available; run OpenAI analysis for "
            "Тема поста, Почему закреплен, Ключевые смыслы, Какой CTA, Куда ведет CTA, Роль в воронке"
        )

    return {
        "account":                           ACCOUNT,
        "stage":                             "stage5a2a",
        "source_file":                       str(PINNED_INDEX_PATH.relative_to(BASE)),
        "detection_method":                  detection_method,
        "total_pinned_posts":                pinned_count,
        "expected_pinned_posts":             EXPECTED_PINNED_COUNT,
        "count_matches_expected":            pinned_count == EXPECTED_PINNED_COUNT,
        "manual_needed_flag":                manual_needed,
        "source_quality_summary":            build_source_quality_summary(index, posts_audits),
        "posts":                             posts_audits,
        "google_sheets_field_assessment":    gs_assessment,
        "google_sheet_fields_possible_now":  can_now,
        "google_sheet_fields_need_full_caption":  need_full_cap,
        "google_sheet_fields_need_visual_or_ocr": need_visual,
        "google_sheet_fields_need_semantic_analysis": need_semantic,
        "apify_needs":                       apify_needs,
        "recommended_next_stage":            recommended_next_stage,
        "caption_only_analyzer_possible":    False,
        "caption_only_analyzer_notes":       (
            "NOT YET POSSIBLE: current index stores only 300-char caption preview. "
            "Full caption is required for reliable semantic analysis. "
            "Run Stage 5A-2B first to collect full captions."
        ),
    }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_pinned_index() -> tuple[dict, list[str]]:
    errors = []
    if not PINNED_INDEX_PATH.exists():
        errors.append(f"pinned_posts_index.json not found at {PINNED_INDEX_PATH}")
        return {}, errors
    try:
        index = json.loads(PINNED_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Cannot parse pinned_posts_index.json: {e}")
        return {}, errors

    pinned_posts = index.get("pinned_posts")
    if not isinstance(pinned_posts, list):
        errors.append("pinned_posts_index.json: 'pinned_posts' field is missing or not a list")
        return index, errors

    if len(pinned_posts) == 0:
        errors.append("pinned_posts_index.json: 0 pinned posts found")
        return index, errors

    # Validate each post has at least permalink or shortcode
    for i, item in enumerate(pinned_posts):
        has_url       = _has_field(item, "url")
        has_shortcode = _has_field(item, "shortcode")
        has_id        = _has_field(item, "content_id")
        if not has_url and not has_shortcode and not has_id:
            errors.append(
                f"Post at index {i} has neither permalink (url), shortcode, nor content_id"
            )

    n = index.get("pinned_count", 0)
    if n != EXPECTED_PINNED_COUNT:
        errors.append(
            f"WARNING: expected {EXPECTED_PINNED_COUNT} pinned posts, found {n}. "
            "Proceeding with audit."
        )

    # Validate all 11 Google Sheets fields will be assessed
    assessed = set(GOOGLE_SHEETS_FIELDS)
    if len(assessed) != 11:
        errors.append("Internal: GOOGLE_SHEETS_FIELDS does not cover all 11 fields")

    return index, errors


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(audit: dict):
    AUDIT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Stage 5A-2A: Pinned Posts Source Audit Report")
    lines.append("")
    lines.append(f"Account: {audit['account']}")
    lines.append(f"Source: `{audit['source_file']}`")
    lines.append(f"Detection method: {audit['detection_method']}")
    lines.append("")

    # Summary
    lines.append("## 1. Summary")
    lines.append("")
    lines.append(f"- **Total pinned posts found**: {audit['total_pinned_posts']}")
    lines.append(f"- **Expected**: {audit['expected_pinned_posts']}")
    lines.append(f"- **Count matches expected**: {audit['count_matches_expected']}")
    lines.append(f"- **Source quality**: {audit['source_quality_summary']}")
    lines.append(f"- **Caption-only analyzer possible now**: {audit['caption_only_analyzer_possible']}")
    lines.append(f"  → {audit['caption_only_analyzer_notes']}")
    lines.append("")

    # Per-post
    lines.append("## 2. Per-Post Source Audit")
    lines.append("")
    for p in audit.get("posts", []):
        lines.append(f"### Post {p['position']} — {p['permalink'] or '(no permalink)'}")
        lines.append(f"- **Shortcode**: {p['shortcode'] or '—'}")
        lines.append(f"- **Post ID**: {p['post_id'] or '—'}")
        lines.append(f"- **Media type**: {p['media_type'] or '—'}")
        lines.append(f"- **Caption available**: {p['caption_available']}")
        lines.append(f"- **Caption is full**: {p['caption_is_full']} (always False — index stores max 300 chars)")
        lines.append(f"- **Caption length stored**: {p['caption_length']} chars")
        lines.append(f"- **Caption truncated**: {p['has_caption_truncation_signals']}")
        lines.append(f"- **CTA signals in caption**: {p['has_cta_signals_in_caption']}")
        if p['cta_signals_found']:
            lines.append(f"  → Signals: {', '.join(p['cta_signals_found'])}")
        lines.append(f"- **Has cover/thumbnail**: False (not collected)")
        lines.append(f"- **Has carousel items**: False (not collected)")
        lines.append(f"- **Fields present**: {', '.join(p['source_fields_present']) or '—'}")
        lines.append(f"- **Fields missing**: {', '.join(p['source_fields_missing']) or 'none'}")
        lines.append("- **Limitations**:")
        for lim in p["limitations"]:
            lines.append(f"  - {lim}")
        lines.append("")

    # What can fill now
    lines.append("## 3. What Can Be Filled Now")
    lines.append("")
    fields_now = audit.get("google_sheet_fields_possible_now", [])
    if fields_now:
        for f in fields_now:
            lines.append(f"- **{f}**")
    else:
        lines.append("_None beyond Конкурент / Ссылка / Позиция._")
    lines.append("")

    # What needs full caption
    lines.append("## 4. What Requires Full Caption")
    lines.append("")
    for f in audit.get("google_sheet_fields_need_full_caption", []):
        note = audit["google_sheets_field_assessment"][f].get("notes", "")
        lines.append(f"- **{f}**: {note}")
    lines.append("")

    # What needs media/OCR
    lines.append("## 5. What Requires Media / Visual / OCR")
    lines.append("")
    for f in audit.get("google_sheet_fields_need_visual_or_ocr", []):
        note = audit["google_sheets_field_assessment"][f].get("notes", "")
        lines.append(f"- **{f}**: {note}")
    lines.append("")

    # Caption-only analyzer readiness
    lines.append("## 6. Caption-Only Analyzer Readiness")
    lines.append("")
    lines.append(f"**Possible now**: {audit['caption_only_analyzer_possible']}")
    lines.append("")
    lines.append(audit["caption_only_analyzer_notes"])
    lines.append("")

    # Apify needs
    lines.append("## 7. New Apify Call Assessment")
    lines.append("")
    an = audit.get("apify_needs", {})
    lines.append(f"**New Apify call needed**: {an.get('new_apify_call_needed', True)}")
    lines.append("")
    lines.append(an.get("reason", ""))
    lines.append("")
    needed = an.get("needed_from_actor", [])
    if needed:
        lines.append("**Data needed from actor:**")
        for n in needed:
            lines.append(f"- {n}")
        lines.append("")
    if an.get("can_reuse_stage5a1_actor"):
        lines.append(f"**Can reuse Stage 5A-1 actor**: Yes — {an.get('stage5a1_change_needed', '')}")
    lines.append("")

    # Google Sheets field assessment table
    lines.append("## 8. Google Sheets Field Assessment")
    lines.append("")
    lines.append("| Field | Now | Caption only | Needs full caption | Needs visual/OCR | Needs semantic | Missing source |")
    lines.append("|---|---|---|---|---|---|---|")
    for field, v in audit["google_sheets_field_assessment"].items():
        lines.append(
            f"| {field} "
            f"| {v['can_fill_now']} "
            f"| {v['can_fill_caption_only']} "
            f"| {v['needs_full_caption']} "
            f"| {v['needs_visual_or_ocr']} "
            f"| {v['needs_semantic_analysis']} "
            f"| {v['missing_source']} |"
        )
    lines.append("")

    # Notes per field
    lines.append("### Field notes")
    lines.append("")
    for field, v in audit["google_sheets_field_assessment"].items():
        lines.append(f"- **{field}**: {v.get('notes', '')}")
    lines.append("")

    # Recommended next step
    lines.append("## 9. Recommended Next Step")
    lines.append("")
    lines.append(audit.get("recommended_next_stage", ""))
    lines.append("")

    AUDIT_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_audit() -> dict:
    """Load pinned_posts_index, build audit, write JSON + report. Returns audit dict."""
    index, errors = load_pinned_index()

    # Separate hard errors from warnings
    hard_errors = [e for e in errors if not e.startswith("WARNING")]
    warnings    = [e for e in errors if e.startswith("WARNING")]

    if hard_errors:
        raise ValueError("\n".join(hard_errors))

    audit = build_audit(index)

    # Validate all 11 GS fields are assessed
    assessed_fields = set(audit["google_sheets_field_assessment"].keys())
    required_fields = set(GOOGLE_SHEETS_FIELDS)
    missing_assessment = required_fields - assessed_fields
    if missing_assessment:
        raise ValueError(f"Audit does not assess all 11 Google Sheets fields. Missing: {missing_assessment}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(audit)

    return audit
