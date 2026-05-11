import base64
import json
import os
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv

os.environ["PYTHONUTF8"] = "1"

BASE = Path(__file__).parent.parent

MODEL = "gpt-4.1-mini"

PLAN_CHECK_PATH  = BASE / "data/normalized/stage4b_plan_check.json"
PLAN_PATH        = BASE / "data/normalized/stage4a_openai_plan.json"
POSTS_RAW_PATH   = BASE / "data/raw/posts_test_raw.json"
POSTS_OUT_DIR    = BASE / "analysis/stage4b/posts"
RAW_RESP_DIR     = BASE / "analysis/openai_responses/stage4b/posts"
SUMMARY_PATH     = BASE / "data/normalized/stage4b_posts_summary.json"

REQUIRED_KEYS = {
    "status", "account", "analysis_scope", "content_id", "url", "type",
    "observed_facts", "inferred_meanings", "evidence", "visual_summary",
    "score", "limitations", "confidence",
}
VALID_CONFIDENCE  = {"high", "medium", "low"}
VALID_FUNNEL_ROLE = {
    "reach", "trust", "warmup", "sales", "engagement",
    "leadgen", "expertise", "unknown",
}

DRY_RUN = "--dry-run" in sys.argv
FORCE   = "--force"   in sys.argv

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ── Guards ────────────────────────────────────────────────────────────────────
if not PLAN_CHECK_PATH.exists():
    raise SystemExit("stage4b_plan_check.json not found — run stage4b_check_plan.py first")

plan_check = json.loads(PLAN_CHECK_PATH.read_text(encoding="utf-8"))
if not plan_check.get("stage4b_can_continue"):
    raise SystemExit("stage4b_can_continue = false — fix plan check errors first")

plan      = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
posts_raw = json.loads(POSTS_RAW_PATH.read_text(encoding="utf-8")) if POSTS_RAW_PATH.exists() else []

# Build caption lookup: content_id / shortcode / url → caption
caption_map: dict = {}
for p in posts_raw:
    cap = p.get("caption") or p.get("text") or None
    for key in ("shortCode", "shortcode", "id"):
        if p.get(key):
            caption_map[str(p[key])] = cap
    if p.get("url"):
        caption_map[p["url"]] = cap
    if p.get("postUrl"):
        caption_map[p["postUrl"]] = cap

POSTS_OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_RESP_DIR.mkdir(parents=True, exist_ok=True)

posts_plan = plan.get("posts_plan", [])

# ── Dry-run preview ───────────────────────────────────────────────────────────
if DRY_RUN:
    calls_needed = 0
    for req in posts_plan:
        out = POSTS_OUT_DIR / f"{req['request_id']}.json"
        skip = False
        if out.exists() and not FORCE:
            try:
                ex = json.loads(out.read_text(encoding="utf-8"))
                if ex.get("status") == "OK":
                    skip = True
            except Exception:
                pass
        if not skip:
            calls_needed += 1
        print(f"  {req['request_id']}: images={req['images_count']} "
              f"{'[SKIP existing OK]' if skip else '[CALL]'}")
    print(f"dry-run: {calls_needed} OpenAI calls would be made")
    sys.exit(0)

# ── OpenAI client ─────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("openai package not installed — run: pip install openai")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

SYSTEM_PROMPT = (
    "You are an Instagram content analyst. "
    "Return ONLY valid JSON matching the provided schema. "
    "No markdown. No text outside JSON. "
    "Analyze only the caption and provided images/frames. "
    "Separate observed facts from inferred meanings. "
    "Do not invent what is not visible in the images or written in the caption. "
    "If a field is not supported by caption/image evidence, write 'not enough evidence'. "
    "Evidence is required for every non-trivial claim. "
    "If CTA, offer, or social proof is not found, write 'not found'."
)

SCHEMA_EXAMPLE = json.dumps({
    "status": "OK",
    "account": "vlada_kliuiko",
    "analysis_scope": "single_post",
    "content_id": "...",
    "url": "...",
    "type": "...",
    "observed_facts": {
        "caption_facts": [],
        "visual_facts": [],
    },
    "inferred_meanings": {
        "topic": "...",
        "format": "...",
        "hook": "...",
        "main_message": "...",
        "audience_pain": "...",
        "audience_desire": "...",
        "barrier_or_objection": "...",
        "cta": "...",
        "offer": "...",
        "social_proof": "...",
        "funnel_role": "reach|trust|warmup|sales|engagement|leadgen|expertise|unknown",
        "target_segment": "...",
    },
    "evidence": [],
    "visual_summary": "...",
    "score": 1,
    "limitations": [],
    "confidence": "high|medium|low",
}, ensure_ascii=False)


def validate_post_json(data):
    errors = []
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")

    score = data.get("score")
    if not isinstance(score, (int, float)) or not (1 <= score <= 10):
        errors.append(f"score must be 1–10, got: {score!r}")

    confidence = data.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(f"confidence must be high|medium|low, got: {confidence!r}")

    evidence = data.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []

    if len(evidence) == 0 and confidence == "high":
        errors.append("evidence is empty but confidence is 'high'")

    funnel = data.get("inferred_meanings", {}).get("funnel_role", "")
    if funnel and funnel not in VALID_FUNNEL_ROLE:
        errors.append(f"funnel_role '{funnel}' not in allowed enum")

    if len(evidence) < 2:
        errors.append(f"evidence has {len(evidence)} items; minimum 2 required for OK status")

    return errors


def analyze_post(req):
    request_id = req["request_id"]
    content_id = req.get("content_id", "")
    url        = req.get("url", "")
    ptype      = req.get("type", "unknown")
    caption    = (
        caption_map.get(content_id)
        or caption_map.get(url)
        or "(caption not found)"
    )

    # Build image content blocks
    image_blocks = []
    for path_str in req.get("prepared_paths", []):
        fp = BASE / path_str
        if not fp.exists():
            continue
        data = base64.b64encode(fp.read_bytes()).decode("utf-8")
        image_blocks.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{data}",
                "detail": "low",
            },
        })

    user_content = [
        {
            "type": "text",
            "text": (
                f"Account: vlada_kliuiko\n"
                f"content_id: {content_id}\n"
                f"url: {url}\n"
                f"type: {ptype}\n"
                f"caption:\n{caption}\n\n"
                f"Analyze this post using the JSON schema below. "
                f"Fill every field. Do not omit fields.\n\n"
                f"Schema:\n{SCHEMA_EXAMPLE}"
            ),
        },
        *image_blocks,
    ]

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_content},
        ],
        max_tokens=2000,
        temperature=0,
    )

    raw_text = response.choices[0].message.content or ""

    # Save raw response (no base64)
    raw_resp = {
        "request_id": request_id,
        "model":      response.model,
        "usage":      response.usage.model_dump() if response.usage else {},
        "raw_text":   raw_text,
    }
    (RAW_RESP_DIR / f"{request_id}_response.json").write_text(
        json.dumps(raw_resp, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Parse JSON
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI returned invalid JSON: {e}\n---\n{raw_text[:500]}")

    # Inject required fields
    result["account"]        = "vlada_kliuiko"
    result["analysis_scope"] = "single_post"
    result["content_id"]     = content_id
    result["url"]            = url
    result["type"]           = ptype

    # Validate
    val_errors = validate_post_json(result)
    if val_errors:
        if len(result.get("evidence", [])) == 0:
            result["status"] = "FAIL"
        else:
            result["status"] = "PARTIAL"
        result.setdefault("limitations", [])
        result["limitations"].extend(val_errors)
    else:
        result["status"] = "OK"

    return result


# ── Main loop ─────────────────────────────────────────────────────────────────
ok = partial = fail = skipped = calls_made = 0
loop_errors = []

for req in posts_plan:
    request_id = req["request_id"]
    out_path   = POSTS_OUT_DIR / f"{request_id}.json"

    # Resume: skip existing OK unless --force
    if out_path.exists() and not FORCE:
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if existing.get("status") == "OK":
                print(f"  {request_id}: SKIP (existing OK)")
                skipped += 1
                ok += 1
                continue
        except Exception:
            pass

    print(f"  {request_id}: calling OpenAI ({len(req.get('prepared_paths', []))} images)...")
    try:
        result = analyze_post(req)
        calls_made += 1
        status = result.get("status", "FAIL")
        if status == "OK":
            ok += 1
        elif status == "PARTIAL":
            partial += 1
        else:
            fail += 1
        print(f"    → {status} | confidence={result.get('confidence')} "
              f"| evidence={len(result.get('evidence', []))}")
    except Exception as e:
        calls_made += 1
        tb = traceback.format_exc()
        result = {
            "status":          "FAIL",
            "account":         "vlada_kliuiko",
            "analysis_scope":  "single_post",
            "content_id":      req.get("content_id", ""),
            "url":             req.get("url", ""),
            "type":            req.get("type", "unknown"),
            "error":           str(e),
            "confidence":      "low",
            "evidence":        [],
            "limitations":     [str(e)],
        }
        fail += 1
        loop_errors.append(f"{request_id}: {e}")
        (RAW_RESP_DIR / f"{request_id}_error_traceback.txt").write_text(tb, encoding="utf-8")
        print(f"    → FAIL: {e}")

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

total = ok + partial + fail
if fail == 0 and partial == 0:
    summary_status = "OK"
elif ok > 0 or partial > 0:
    summary_status = "PARTIAL"
else:
    summary_status = "FAIL"

summary = {
    "posts_total":               len(posts_plan),
    "posts_ok":                  ok,
    "posts_partial":             partial,
    "posts_fail":                fail,
    "posts_skipped_existing_ok": skipped,
    "openai_calls_made":         calls_made,
    "status":                    summary_status,
    "errors":                    loop_errors,
}

SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nposts: OK={ok} PARTIAL={partial} FAIL={fail} skipped={skipped} calls={calls_made}")
print(f"status: {summary_status}")
print(f"saved: {SUMMARY_PATH.relative_to(BASE)}")
