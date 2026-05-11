import base64
import json
import os
import sys
os.environ["PYTHONUTF8"] = "1"

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE = Path(__file__).parent.parent
load_dotenv(BASE / ".env")

MODEL = "gpt-4.1-mini"

# ── Output paths ──────────────────────────────────────────────────────────────
RESPONSES_DIR  = BASE / "analysis/openai_responses"
ANALYSIS_DIR   = BASE / "analysis"
REPORT_DIR     = BASE / "report"
for d in (RESPONSES_DIR, ANALYSIS_DIR, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)

POST_RESPONSE_PATH  = RESPONSES_DIR / "post_analysis_response.json"
HL_RESPONSE_PATH    = RESPONSES_DIR / "highlight_analysis_response.json"
POST_ANALYSIS_PATH  = ANALYSIS_DIR  / "content_analysis_test.json"
HL_ANALYSIS_PATH    = ANALYSIS_DIR  / "highlights_analysis_test.json"
REPORT_PATH         = REPORT_DIR    / "stage_3b2_openai_analysis_test_report.md"

preflight_errors   = []
preflight_warnings = []

def ts():
    return datetime.now(timezone.utc).isoformat()

def yesno(v):
    return "yes" if v else "no"

# ── A. Preflight checks ───────────────────────────────────────────────────────
print("Running preflight checks...")

# .env
env_path = BASE / ".env"
env_ok = env_path.exists()
if not env_ok:
    preflight_errors.append(".env not found")

# OPENAI_API_KEY
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
key_ok = bool(OPENAI_API_KEY)
if not key_ok:
    preflight_errors.append("OPENAI_API_KEY missing or empty in .env")

# preview file
preview_path = BASE / "data/normalized/stage3b1_openai_input_preview.json"
preview_ok = preview_path.exists()
if not preview_ok:
    preflight_errors.append("stage3b1_openai_input_preview.json not found — run Stage 3B-1 first")

preview = {}
if preview_ok:
    preview = json.loads(preview_path.read_text(encoding="utf-8"))

# readiness
can_run = preview.get("readiness", {}).get("can_run_stage3b2_openai_call", False)
if not can_run:
    preflight_errors.append("readiness.can_run_stage3b2_openai_call = false in preview — fix Stage 3B-1 blockers")

# openai_call_allowed must be false (Stage 3B-1 should not have called API)
if preview.get("openai_call_allowed") is not False:
    preflight_warnings.append("openai_call_allowed != false in preview — unexpected")

# collect prepared paths
post_media    = preview.get("post_sample", {}).get("selected_media", [])
story_media   = preview.get("highlight_sample", {}).get("selected_stories", [])

planned_count = preview.get("limits_applied", {}).get("images_sent_count_planned", 0)
if planned_count > 10:
    preflight_errors.append(f"planned image count {planned_count} exceeds max 10")

# verify each prepared file
all_prepared = (
    [m["prepared_path"] for m in post_media if m.get("used_for_openai_preview") and m.get("prepared_path")]
    + [m["prepared_path"] for m in story_media if m.get("used_for_openai_preview") and m.get("prepared_path")]
)

VALID_EXTS   = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_MB  = 5
MAX_TOTAL_MB = 20
total_bytes  = 0
missing_files = []
oversized     = []
bad_format    = []

for rel in all_prepared:
    p = BASE / rel
    if not p.exists():
        missing_files.append(rel)
        continue
    ext = p.suffix.lower()
    if ext not in VALID_EXTS:
        bad_format.append(rel)
    sz = p.stat().st_size
    if sz > MAX_FILE_MB * 1024 * 1024:
        oversized.append(f"{rel} ({sz // 1024} KB)")
    total_bytes += sz

if missing_files:
    preflight_errors.append(f"Missing prepared files: {missing_files}")
if oversized:
    preflight_errors.append(f"Files exceed {MAX_FILE_MB} MB: {oversized}")
if bad_format:
    preflight_errors.append(f"Unsupported image format: {bad_format}")
if total_bytes > MAX_TOTAL_MB * 1024 * 1024:
    preflight_errors.append(f"Total payload size {total_bytes // 1024 // 1024} MB exceeds {MAX_TOTAL_MB} MB")

total_mb = round(total_bytes / 1024 / 1024, 2)

# .gitignore safety check
gitignore_path = BASE / ".gitignore"
gitignore_safe = False
if gitignore_path.exists():
    content = gitignore_path.read_text(encoding="utf-8")
    required = [".env", "data/raw/", "output/", "analysis/openai_responses/"]
    gitignore_safe = all(r in content for r in required)
if not gitignore_safe:
    preflight_errors.append(".gitignore missing required entries — risk of committing secrets or raw data")

# print preflight summary
print(f"  OPENAI_API_KEY:        {'found' if key_ok else 'MISSING'}")
print(f"  preview file:          {'found' if preview_ok else 'MISSING'}")
print(f"  can_run_stage3b2:      {can_run}")
print(f"  planned image count:   {planned_count}")
print(f"  total payload size:    {total_mb} MB")
print(f"  all prepared found:    {yesno(not missing_files)}")
print(f"  gitignore safe:        {yesno(gitignore_safe)}")
if preflight_warnings:
    for w in preflight_warnings:
        print(f"  [WARN] {w}")

if preflight_errors:
    print("\nPreflight FAILED — OpenAI will NOT be called:")
    for e in preflight_errors:
        print(f"  [ERROR] {e}")
    # write minimal report and exit
    REPORT_PATH.write_text(f"""# Stage 3B-2 OpenAI Analysis Test Report

## Preflight

FAILED — OpenAI was not called.

Errors:
{chr(10).join(f'- {e}' for e in preflight_errors)}
""", encoding="utf-8")
    raise SystemExit(1)

print("Preflight OK — proceeding to OpenAI calls\n")

# ── Debug: encoding info (no secrets) ────────────────────────────────────────
_cap_preview = (preview.get("post_sample") or {}).get("caption") or ""
print(f"  [debug] python default encoding:  {sys.getdefaultencoding()}")
print(f"  [debug] filesystem encoding:      {sys.getfilesystemencoding()}")
print(f"  [debug] caption length:           {len(_cap_preview)}")
print(f"  [debug] caption contains non-ascii: {not _cap_preview.isascii()}")
print(f"  [debug] caption preview (120 ch): {_cap_preview[:120]!r}")
print()

# ── C. File encoding helper ───────────────────────────────────────────────────
def encode_image(rel_path):
    p = BASE / rel_path
    if not p.exists():
        raise FileNotFoundError(f"Prepared image not found: {rel_path}")
    ext = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
    data = base64.b64encode(p.read_bytes()).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}

def image_block(rel_path):
    return encode_image(rel_path)

# ── B. Build payloads ─────────────────────────────────────────────────────────
post_info = preview["post_sample"]
hl_info   = preview["highlight_sample"]

# post: take first image/frame with used_for_openai_preview = true
post_images_to_send = [
    m["prepared_path"] for m in post_info["selected_media"]
    if m.get("used_for_openai_preview") and m.get("prepared_path")
][:1]   # max 1 image for post

# highlight: all prepared story images/frames
hl_images_to_send = [
    m["prepared_path"] for m in hl_info["selected_stories"]
    if m.get("used_for_openai_preview") and m.get("prepared_path")
]

client = OpenAI(api_key=OPENAI_API_KEY)

POST_SCHEMA = """{
  "account": "vlada_kliuiko",
  "analysis_scope": "single_post_sample",
  "content_id": "...",
  "url": "...",
  "type": "...",
  "observed_facts": {"caption_facts": [], "visual_facts": []},
  "inferred_meanings": {
    "topic": "...", "format": "...", "hook": "...", "main_message": "...",
    "audience_pain": "...", "audience_desire": "...",
    "barrier_or_objection": "...", "cta": "...", "offer": "...",
    "social_proof": "...",
    "funnel_role": "reach|trust|warmup|sales|engagement|leadgen|expertise|unknown",
    "target_segment": "..."
  },
  "evidence": [],
  "visual_summary": "...",
  "score": 1,
  "limitations": [],
  "confidence": "high|medium|low"
}"""

HL_SCHEMA = """{
  "account": "vlada_kliuiko",
  "analysis_scope": "highlight_sample_only",
  "not_full_highlight_analysis": true,
  "highlight_id": "17874797856565339",
  "stories_total_in_raw": 57,
  "stories_analyzed": 2,
  "visual_inputs_count": 6,
  "observed_facts": {"visible_text": [], "visual_facts": []},
  "inferred_meanings": {
    "main_role": "reviews|cases|faq|product|pricing|about|results|education|process|backstage|lead_magnet|unknown",
    "summary": "...", "cta_found": "...", "offer_found": "...",
    "social_proof_found": "...", "decision_support_score": 1
  },
  "evidence": [],
  "limitations": ["Only N stories from a 57-story highlight were analyzed"],
  "confidence": "high|medium|low"
}"""

POST_REQUIRED = ["observed_facts", "inferred_meanings", "evidence", "score", "confidence", "limitations"]
HL_REQUIRED   = ["observed_facts", "inferred_meanings", "evidence", "limitations", "confidence",
                 "stories_analyzed", "visual_inputs_count"]

# ── D/E. Request 1: Post analysis ─────────────────────────────────────────────
print("Request 1: Post analysis...")

caption_text = post_info.get("caption") or ""
post_url     = post_info.get("url", "")
post_type    = post_info.get("type", "unknown")
content_id   = post_info.get("content_id", "unknown")

post_messages = [
    {
        "role": "system",
        "content": (
            "You are a precise content analyst. Analyze only what is directly visible in the "
            "caption and image. Separate observed facts from inferred meanings. "
            "Return ONLY valid JSON. No markdown. No explanations outside JSON. "
            f"Follow this schema exactly:\n{POST_SCHEMA}"
        ),
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    f"Analyze this Instagram post.\n"
                    f"Account: vlada_kliuiko\n"
                    f"Content ID: {content_id}\n"
                    f"URL: {post_url}\n"
                    f"Type: {post_type}\n"
                    f"Caption (do not translate or rewrite): {caption_text or '[no caption]'}\n\n"
                    "Rules:\n"
                    "- Do not invent facts not present in caption or image.\n"
                    "- If CTA not found, write 'not found'.\n"
                    "- If offer not found, write 'not found'.\n"
                    "- If social proof not found, write 'not found'.\n"
                    "- evidence must reference specific visible text or visual details.\n"
                    "- score: 1–10 where 5 = average.\n"
                    "- If evidence is empty, confidence cannot be high.\n"
                    "Return ONLY valid JSON."
                ),
            },
            *[image_block(p) for p in post_images_to_send],
        ],
    },
]

post_raw_response = None
post_analysis     = None
post_status       = "FAIL"
post_err          = None

try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=post_messages,
        max_tokens=1200,
        temperature=0,
    )
    post_raw_response = resp.model_dump()
    raw_text = resp.choices[0].message.content or ""
    POST_RESPONSE_PATH.write_text(json.dumps(post_raw_response, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        post_analysis = json.loads(raw_text)
    except json.JSONDecodeError:
        # try stripping markdown fences
        import re
        clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()
        try:
            post_analysis = json.loads(clean)
        except json.JSONDecodeError as je:
            post_err = f"JSON parse error: {je} | raw: {raw_text[:200]}"
            post_status = "FAIL"

    if post_analysis:
        missing_keys = [k for k in POST_REQUIRED if k not in post_analysis]
        if missing_keys:
            post_err = f"Missing required keys: {missing_keys}"
            post_status = "PARTIAL"
        else:
            # validate score
            score = post_analysis.get("score")
            if not isinstance(score, (int, float)) or not (1 <= score <= 10):
                post_analysis["limitations"] = post_analysis.get("limitations", []) + [f"score {score} out of range 1–10"]
                post_status = "PARTIAL"
            else:
                post_status = "OK"
            # evidence + confidence guard
            if not post_analysis.get("evidence") and post_analysis.get("confidence") == "high":
                post_analysis["confidence"] = "medium"
                post_analysis.setdefault("limitations", []).append("confidence downgraded: evidence is empty")

    POST_ANALYSIS_PATH.write_text(json.dumps(post_analysis or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  post status: {post_status}")
except Exception as e:
    post_err = str(e)
    print(f"  [ERROR] post analysis: {post_err}")
    if "model" in post_err.lower() and ("not found" in post_err.lower() or "does not exist" in post_err.lower()):
        raise SystemExit(f"Model '{MODEL}' is not available: {post_err}")
    _fail_stub = {"status": "FAIL", "error": post_err, "account": "vlada_kliuiko",
                  "analysis_scope": "single_post_sample", "confidence": "low"}
    POST_ANALYSIS_PATH.write_text(json.dumps(_fail_stub, ensure_ascii=False, indent=2), encoding="utf-8")

# ── D/E. Request 2: Highlight sample analysis ─────────────────────────────────
print("Request 2: Highlight sample analysis...")

stories_selected = hl_info.get("stories_selected_count", 0)
stories_total    = hl_info.get("stories_total_in_raw", 57)
visual_count     = len(hl_images_to_send)

hl_messages = [
    {
        "role": "system",
        "content": (
            "You are a precise content analyst. Analyze only the provided story images/frames. "
            "Do NOT infer content for the remaining stories. "
            "Return ONLY valid JSON. No markdown. No explanations outside JSON. "
            f"Follow this schema exactly:\n{HL_SCHEMA}"
        ),
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    f"Analyze this Instagram Highlights sample.\n"
                    f"Account: vlada_kliuiko\n"
                    f"Highlight ID: {hl_info.get('highlight_id', '17874797856565339')}\n"
                    f"IMPORTANT: This is a SAMPLE ONLY. You are seeing {visual_count} visual inputs "
                    f"from {stories_selected} selected stories out of {stories_total} total stories.\n"
                    "Do not infer the full highlight content.\n\n"
                    "Rules:\n"
                    "- observed_facts: only what is directly visible.\n"
                    "- inferred_meanings: clearly labeled as inference.\n"
                    "- evidence must reference specific visible text or visual detail.\n"
                    "- decision_support_score: 1–10.\n"
                    f"- limitations must include: 'Only {stories_selected} stories from a {stories_total}-story highlight were analyzed'.\n"
                    "- If evidence is empty, confidence cannot be high.\n"
                    "Return ONLY valid JSON."
                ),
            },
            *[image_block(p) for p in hl_images_to_send],
        ],
    },
]

hl_raw_response = None
hl_analysis     = None
hl_status       = "FAIL"
hl_err          = None

try:
    resp = client.chat.completions.create(
        model=MODEL,
        messages=hl_messages,
        max_tokens=1200,
        temperature=0,
    )
    hl_raw_response = resp.model_dump()
    raw_text = resp.choices[0].message.content or ""
    HL_RESPONSE_PATH.write_text(json.dumps(hl_raw_response, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        hl_analysis = json.loads(raw_text)
    except json.JSONDecodeError:
        import re
        clean = re.sub(r"```(?:json)?|```", "", raw_text).strip()
        try:
            hl_analysis = json.loads(clean)
        except json.JSONDecodeError as je:
            hl_err = f"JSON parse error: {je} | raw: {raw_text[:200]}"
            hl_status = "FAIL"

    if hl_analysis:
        missing_keys = [k for k in HL_REQUIRED if k not in hl_analysis]
        if missing_keys:
            hl_err = f"Missing required keys: {missing_keys}"
            hl_status = "PARTIAL"
        else:
            dss = hl_analysis.get("inferred_meanings", {}).get("decision_support_score")
            if not isinstance(dss, (int, float)) or not (1 <= dss <= 10):
                hl_analysis.setdefault("limitations", []).append(f"decision_support_score {dss} out of range")
                hl_status = "PARTIAL"
            else:
                hl_status = "OK"
            if not hl_analysis.get("evidence") and hl_analysis.get("confidence") == "high":
                hl_analysis["confidence"] = "medium"
                hl_analysis.setdefault("limitations", []).append("confidence downgraded: evidence is empty")

    HL_ANALYSIS_PATH.write_text(json.dumps(hl_analysis or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  highlight status: {hl_status}")
except Exception as e:
    hl_err = str(e)
    print(f"  [ERROR] highlight analysis: {hl_err}")
    if "model" in hl_err.lower() and ("not found" in hl_err.lower() or "does not exist" in hl_err.lower()):
        raise SystemExit(f"Model '{MODEL}' is not available: {hl_err}")
    _fail_stub = {"status": "FAIL", "error": hl_err, "account": "vlada_kliuiko",
                  "analysis_scope": "highlight_sample_only", "confidence": "low"}
    HL_ANALYSIS_PATH.write_text(json.dumps(_fail_stub, ensure_ascii=False, indent=2), encoding="utf-8")

# ── I. Report ─────────────────────────────────────────────────────────────────
def safe(d, *keys, default="n/a"):
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, {})
        else:
            return default
    return d if d not in ({}, None, "") else default

p_im = safe(post_analysis, "inferred_meanings")
h_im = safe(hl_analysis,   "inferred_meanings")

if post_status == "OK" and hl_status == "OK":
    verdict = "OK — OpenAI proof of concept works"
elif post_status != "FAIL" or hl_status != "FAIL":
    verdict = "PARTIAL — OpenAI returned output, but quality/schema has issues"
else:
    verdict = "FAIL — OpenAI analysis failed"

can_stage4 = post_status in ("OK", "PARTIAL") and hl_status in ("OK", "PARTIAL")

recs = []
if can_stage4:
    recs.append("- Можно переходить к Stage 4: full one-account analysis.")
    recs.append("- Перед полным отчётом: добавить анализ всех 5 posts, добавить highlights с валидными highlight IDs.")
    recs.append("- Ограничения: highlights анализируются только при наличии clean_highlight_id; scrapio actor требует paid rental.")
else:
    recs.append("- Stage 4 пока недоступен — устранить FAIL в анализах выше.")
    if post_status == "FAIL":
        recs.append(f"  - Post error: {post_err}")
    if hl_status == "FAIL":
        recs.append(f"  - Highlight error: {hl_err}")

report_md = f"""# Stage 3B-2 OpenAI Analysis Test Report

## Scope

Stage 3B-2 проверяет только:
- OpenAI-анализ одного post sample;
- OpenAI-анализ одного highlight sample;
- строгий JSON output;
- schema validation.

Stage 3B-2 НЕ проверяет:
- все posts;
- все highlights;
- весь highlight из 57 stories;
- сайт;
- bio;
- pinned posts;
- bot funnel;
- полную стратегию конкурента.

## Preflight

- OPENAI_API_KEY: {'found' if key_ok else 'missing'}
- preview file: {'found' if preview_ok else 'missing'}
- planned image count: {planned_count}
- total payload size: {total_mb} MB
- all prepared files found: {yesno(not missing_files)}
- gitignore safe: {yesno(gitignore_safe)}

## Inputs

- post analyzed: {content_id}
- post media used: {len(post_images_to_send)} image(s)
- post caption used: {yesno(bool(caption_text))}
- highlight id: {hl_info.get('highlight_id', '17874797856565339')}
- stories analyzed: {stories_selected}
- visual inputs count: {visual_count}

## Post analysis result

- status: {post_status}
- topic: {safe(p_im, 'topic')}
- hook: {safe(p_im, 'hook')}
- main_message: {safe(p_im, 'main_message')}
- cta: {safe(p_im, 'cta')}
- offer: {safe(p_im, 'offer')}
- social_proof: {safe(p_im, 'social_proof')}
- funnel_role: {safe(p_im, 'funnel_role')}
- score: {safe(post_analysis, 'score')}
- confidence: {safe(post_analysis, 'confidence')}
- evidence count: {len(post_analysis.get('evidence', [])) if isinstance(post_analysis, dict) else 0}
- limitations: {'; '.join(post_analysis.get('limitations', [])) if isinstance(post_analysis, dict) else post_err or 'n/a'}

## Highlight sample analysis result

- status: {hl_status}
- main_role: {safe(h_im, 'main_role')}
- summary: {safe(h_im, 'summary')}
- cta_found: {safe(h_im, 'cta_found')}
- offer_found: {safe(h_im, 'offer_found')}
- social_proof_found: {safe(h_im, 'social_proof_found')}
- decision_support_score: {safe(h_im, 'decision_support_score')}
- confidence: {safe(hl_analysis, 'confidence')}
- evidence count: {len(hl_analysis.get('evidence', [])) if isinstance(hl_analysis, dict) else 0}
- limitations: {'; '.join(hl_analysis.get('limitations', [])) if isinstance(hl_analysis, dict) else hl_err or 'n/a'}

## Output files

- analysis/content_analysis_test.json — exists: {yesno(POST_ANALYSIS_PATH.exists())} | status: {post_status}
- analysis/highlights_analysis_test.json — exists: {yesno(HL_ANALYSIS_PATH.exists())} | status: {hl_status}
- analysis/openai_responses/post_analysis_response.json — exists: {yesno(POST_RESPONSE_PATH.exists())}
- analysis/openai_responses/highlight_analysis_response.json — exists: {yesno(HL_RESPONSE_PATH.exists())}

## Final verdict

{verdict}

## Recommendation

{chr(10).join(recs)}
"""

REPORT_PATH.write_text(report_md, encoding="utf-8")
print(f"\nReport: {REPORT_PATH.relative_to(BASE)}")
print(f"Final verdict: {verdict}")
