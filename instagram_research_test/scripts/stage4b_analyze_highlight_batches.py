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

PLAN_CHECK_PATH   = BASE / "data/normalized/stage4b_plan_check.json"
PLAN_PATH         = BASE / "data/normalized/stage4a_openai_plan.json"
BATCHES_OUT_DIR   = BASE / "analysis/stage4b/highlight_batches"
RAW_RESP_DIR      = BASE / "analysis/openai_responses/stage4b/highlight_batches"
SUMMARY_PATH      = BASE / "data/normalized/stage4b_highlight_batches_summary.json"
NORM_SUMMARY_PATH = BASE / "data/normalized/stage4b_highlight_role_normalization_summary.json"
POLICY_PATH       = BASE / "prompts/analysis_language_policy_ru.md"

HIGHLIGHT_ID = "17874797856565339"

REQUIRED_KEYS = {
    "status", "account", "highlight_id", "analysis_scope", "batch_index",
    "story_ids", "story_numbers", "stories_analyzed", "visual_inputs_count",
    "observed_facts", "inferred_meanings", "evidence", "limitations", "confidence",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_ROLES = {
    "social_proof", "student_results", "course_trust", "community",
    "education", "reviews", "cases", "faq", "product", "pricing",
    "about", "process", "backstage", "lead_magnet", "unknown",
}
BATCH_LIMITATION = "This is one batch from a 57-story highlight, not full highlight synthesis"

DRY_RUN = "--dry-run" in sys.argv
FORCE   = "--force"   in sys.argv

# --only highlight_batch_1,highlight_batch_5,highlight_batch_8
_only_arg = next((a for a in sys.argv if a.startswith("--only=")), None)
if _only_arg is None and "--only" in sys.argv:
    _idx = sys.argv.index("--only")
    _only_arg = f"--only={sys.argv[_idx + 1]}" if _idx + 1 < len(sys.argv) else None
ONLY_IDS: set = (
    set(_only_arg.split("=", 1)[1].split(",")) if _only_arg else set()
)

load_dotenv(dotenv_path=BASE / ".env", override=True)

# ── Guards ────────────────────────────────────────────────────────────────────
if not PLAN_CHECK_PATH.exists():
    raise SystemExit("stage4b_plan_check.json not found — run stage4b_check_plan.py first")

plan_check = json.loads(PLAN_CHECK_PATH.read_text(encoding="utf-8"))
if not plan_check.get("stage4b_can_continue"):
    raise SystemExit("stage4b_can_continue = false — fix plan check errors first")

plan         = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
batches_plan = plan.get("highlight_batches_plan", [])

BATCHES_OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_RESP_DIR.mkdir(parents=True, exist_ok=True)

# ── Dry-run preview ───────────────────────────────────────────────────────────
if DRY_RUN:
    calls_needed = 0
    for req in batches_plan:
        rid  = req["request_id"]
        out  = BATCHES_OUT_DIR / f"{rid}.json"
        if ONLY_IDS and rid not in ONLY_IDS:
            print(f"  {rid}: [SKIP --only filter]")
            continue
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
        print(f"  {rid}: stories={len(req.get('story_ids',[]))} "
              f"images={req['images_count']} "
              f"{'[SKIP existing OK]' if skip else '[CALL]'}")
    print(f"dry-run: {calls_needed} OpenAI calls would be made")
    if ONLY_IDS:
        print(f"--only filter: {sorted(ONLY_IDS)}")
    sys.exit(0)

# ── OpenAI client ─────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("openai package not installed — run: pip install openai")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))

_policy = POLICY_PATH.read_text(encoding="utf-8").strip() if POLICY_PATH.exists() else ""
if not _policy:
    print(f"  WARNING: policy file not found at {POLICY_PATH}", file=sys.stderr)

SYSTEM_PROMPT = (
    (_policy + "\n\n---\n\n") if _policy else ""
) + (
    "You are an Instagram Stories analyst. "
    "Return ONLY valid JSON matching the provided schema. "
    "No markdown. No text outside JSON. "
    "Analyze only the provided story images/frames. "
    "Do not infer the full highlight from this batch alone. "
    "Evidence is required for every non-trivial claim. "
    "If CTA, offer, or social proof is not found, write 'not found'. "
    "If a conclusion is not supported by visible text or visual facts, "
    "write 'not enough evidence'. "
    "Always include in limitations: "
    "'This is one batch from a 57-story highlight, not full highlight synthesis'. "
    "\n\nCRITICAL: main_roles MUST contain enum values ONLY. "
    "Do not use free-text role names. "
    "Allowed values: social_proof, student_results, course_trust, community, "
    "education, reviews, cases, faq, product, pricing, about, process, "
    "backstage, lead_magnet, unknown. "
    "If unsure, use unknown. "
    "Testimonials / praise / feedback → social_proof or reviews. "
    "Student wins / sales / client results / money → student_results. "
    "Active chat / group / participants → community. "
    "Course/instructor credibility / support → course_trust. "
    "Lessons / learning / AI marketing / GPT tools → education."
)

SCHEMA_EXAMPLE = json.dumps({
    "status": "OK",
    "account": "vlada_kliuiko",
    "highlight_id": HIGHLIGHT_ID,
    "analysis_scope": "highlight_batch",
    "batch_index": 1,
    "story_ids": [],
    "story_numbers": [],
    "stories_analyzed": 0,
    "visual_inputs_count": 0,
    "observed_facts": {
        "visible_text": [],
        "visual_facts": [],
    },
    "inferred_meanings": {
        "main_roles": ["social_proof", "education", "unknown"],  # USE ENUM ONLY
        "summary": "...",
        "cta_found": "...",
        "offer_found": "...",
        "social_proof_found": "...",
        "trust_mechanics": [],
        "decision_support_score": 1,
    },
    "evidence": [],
    "limitations": [BATCH_LIMITATION],
    "confidence": "high|medium|low",
}, ensure_ascii=False)


def validate_batch_json(data):
    """Validates after normalization — main_roles are expected to be enum-clean."""
    errors = []
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")

    score = data.get("inferred_meanings", {}).get("decision_support_score")
    if not isinstance(score, (int, float)) or not (1 <= score <= 10):
        errors.append(f"decision_support_score must be 1–10, got: {score!r}")

    confidence = data.get("confidence", "")
    if confidence not in VALID_CONFIDENCE:
        errors.append(f"confidence must be high|medium|low, got: {confidence!r}")

    evidence = data.get("evidence", [])
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
        evidence = []

    if len(evidence) == 0 and confidence == "high":
        errors.append("evidence is empty but confidence is 'high'")

    # main_roles validated after normalization — only flag truly unmapped values
    roles = data.get("inferred_meanings", {}).get("main_roles", [])
    if isinstance(roles, list):
        invalid = [r for r in roles if r not in VALID_ROLES]
        if invalid:
            errors.append(f"invalid main_roles after normalization: {invalid}")

    if len(evidence) < 2:
        errors.append(f"evidence has {len(evidence)} items; minimum 2 required for OK status")

    limitations = data.get("limitations", [])
    has_batch_note = any(
        "batch" in str(lim).lower() and "57" in str(lim)
        for lim in limitations
    )
    if not has_batch_note:
        errors.append("limitations must state this is a batch from 57-story highlight")

    return errors


# Keyword → enum mapping (checked in order; first match wins per keyword group)
_ROLE_KEYWORD_MAP = [
    ({"testimonial", "praise", "feedback"},                        "social_proof"),
    ({"review", "отзыв"},                                          "reviews"),
    ({"student", "learner", "participant", "client",
      "sale", "money", "result", "win", "success"},                "student_results"),
    ({"chat", "group", "community", "participants", "member"},     "community"),
    ({"instructor", "creator", "credibility", "support",
      "course creator", "expert"},                                  "course_trust"),
    ({"lesson", "education", "learning", "ai ", "gpt",
      "marketing strategy", "strategy", "training"},               "education"),
    ({"faq", "question", "answer"},                                "faq"),
    ({"product", "tool", "feature"},                               "product"),
    ({"price", "pricing", "cost", "tariff"},                       "pricing"),
    ({"about", "story", "who", "team"},                            "about"),
    ({"process", "workflow", "step", "how"},                       "process"),
    ({"backstage", "behind", "bts"},                               "backstage"),
    ({"lead", "magnet", "freebie", "free"},                        "lead_magnet"),
    ({"case", "project"},                                          "cases"),
]


def normalize_roles(raw_roles):
    """
    Maps free-text role strings to VALID_ROLES enum values.
    Returns (normalized_roles, normalization_notes).
    normalized_roles is deduplicated; unmapped values become 'unknown'.
    """
    normalized = []
    notes      = []

    for raw in raw_roles:
        raw_str = str(raw).strip()
        if raw_str in VALID_ROLES:
            normalized.append(raw_str)
            continue

        raw_lower  = raw_str.lower()
        mapped_to  = None
        for keywords, enum_value in _ROLE_KEYWORD_MAP:
            if any(kw in raw_lower for kw in keywords):
                mapped_to = enum_value
                break

        if mapped_to is None:
            mapped_to = "unknown"

        normalized.append(mapped_to)
        notes.append({"original": raw_str, "mapped_to": mapped_to})

    # deduplicate preserving order
    seen: set = set()
    deduped   = []
    for r in normalized:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return deduped, notes


def parse_json_robust(raw_text):
    """
    Parse JSON from an OpenAI response that may contain trailing text.
    Strategy:
    1. Try json.loads() directly.
    2. Strip markdown fences (```json ... ```) and retry.
    3. Find the first '{', use raw_decode() to extract the first object,
       ignoring any trailing text.
    Returns (parsed_obj, parsing_notes).
    Raises ValueError if no valid JSON object can be found.
    """
    parsing_notes = []

    # Pass 1: clean parse
    try:
        return json.loads(raw_text), parsing_notes
    except json.JSONDecodeError:
        pass

    # Pass 2: strip markdown fences
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first line (```json or ```) and last closing ```
        inner_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner_lines.append(line)
        text = "\n".join(inner_lines).strip()
        try:
            return json.loads(text), ["json_salvaged_from_response"]
        except json.JSONDecodeError:
            pass

    # Pass 3: raw_decode from first '{'
    brace_idx = text.find("{")
    if brace_idx == -1:
        raise ValueError(f"No JSON object found in response. Preview: {raw_text[:300]}")

    text_from_brace = text[brace_idx:]
    try:
        obj, end_idx = json.JSONDecoder().raw_decode(text_from_brace)
        trailing = text_from_brace[end_idx:].strip()
        notes = ["json_salvaged_from_response"]
        if trailing:
            notes.append("trailing_text_ignored")
        return obj, notes
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not salvage JSON from response: {e}. Preview: {raw_text[:300]}"
        )


def analyze_batch(req):
    request_id   = req["request_id"]
    batch_index  = req.get("batch_index", 0)
    story_ids    = req.get("story_ids", [])
    story_numbers = req.get("story_numbers", [])

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
                f"highlight_id: {HIGHLIGHT_ID}\n"
                f"batch_index: {batch_index}\n"
                f"story_ids: {story_ids}\n"
                f"story_numbers: {story_numbers}\n"
                f"total images in this batch: {len(image_blocks)}\n"
                f"Note: this is one batch from a 57-story highlight, not full highlight synthesis.\n\n"
                f"Analyze these story images/frames using the JSON schema below. "
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
        "request_id":  request_id,
        "model":       response.model,
        "usage":       response.usage.model_dump() if response.usage else {},
        "raw_text":    raw_text,
    }
    (RAW_RESP_DIR / f"{request_id}_response.json").write_text(
        json.dumps(raw_resp, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Parse JSON — robust: tolerates trailing text after valid JSON object
    result, parsing_notes = parse_json_robust(raw_text)
    if parsing_notes:
        result.setdefault("parsing_notes", []).extend(parsing_notes)

    # Inject required fields
    result["account"]             = "vlada_kliuiko"
    result["highlight_id"]        = HIGHLIGHT_ID
    result["analysis_scope"]      = "highlight_batch"
    result["batch_index"]         = batch_index
    result["story_ids"]           = story_ids
    result["story_numbers"]       = story_numbers
    result["stories_analyzed"]    = len(story_ids)
    result["visual_inputs_count"] = len(image_blocks)

    # Ensure batch limitation note is present
    limitations = result.setdefault("limitations", [])
    has_batch_note = any(
        "batch" in str(lim).lower() and "57" in str(lim)
        for lim in limitations
    )
    if not has_batch_note:
        limitations.append(BATCH_LIMITATION)

    # Normalize main_roles before validation
    im = result.setdefault("inferred_meanings", {})
    raw_roles = im.get("main_roles", [])
    if isinstance(raw_roles, list):
        normalized_roles, norm_notes = normalize_roles(raw_roles)
        im["main_roles"] = normalized_roles
        if norm_notes:
            result["role_normalization_notes"] = norm_notes
    else:
        im["main_roles"] = ["unknown"]
        result["role_normalization_notes"] = [
            {"original": str(raw_roles), "mapped_to": "unknown"}
        ]

    # Validate (main_roles are enum-clean after normalization)
    val_errors = validate_batch_json(result)
    if val_errors:
        if len(result.get("evidence", [])) == 0:
            result["status"] = "FAIL"
        else:
            result["status"] = "PARTIAL"
        result["limitations"].extend(val_errors)
    else:
        result["status"] = "OK"

    return result


# ── Main loop ─────────────────────────────────────────────────────────────────
ok = partial = fail = skipped = calls_made = 0
loop_errors    = []
norm_summary   = []   # accumulates normalization notes across all batches

for req in batches_plan:
    request_id = req["request_id"]
    out_path   = BATCHES_OUT_DIR / f"{request_id}.json"

    # --only: skip requests not in the filter set; count their existing results below
    if ONLY_IDS and request_id not in ONLY_IDS:
        continue

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

    n_stories = len(req.get("story_ids", []))
    n_images  = len(req.get("prepared_paths", []))
    print(f"  {request_id}: calling OpenAI (stories={n_stories}, images={n_images})...")
    try:
        result     = analyze_batch(req)
        calls_made += 1
        status     = result.get("status", "FAIL")
        if status == "OK":
            ok += 1
        elif status == "PARTIAL":
            partial += 1
        else:
            fail += 1
        notes = result.get("role_normalization_notes", [])
        if notes:
            norm_summary.append({"request_id": request_id, "normalizations": notes})
        print(f"    → {status} | confidence={result.get('confidence')} "
              f"| evidence={len(result.get('evidence', []))} "
              f"| roles_normalized={len(notes)}")
    except Exception as e:
        calls_made += 1
        tb = traceback.format_exc()
        result = {
            "status":             "FAIL",
            "account":            "vlada_kliuiko",
            "highlight_id":       HIGHLIGHT_ID,
            "analysis_scope":     "highlight_batch",
            "batch_index":        req.get("batch_index", 0),
            "story_ids":          req.get("story_ids", []),
            "story_numbers":      req.get("story_numbers", []),
            "stories_analyzed":   len(req.get("story_ids", [])),
            "visual_inputs_count": len(req.get("prepared_paths", [])),
            "error":              str(e),
            "confidence":         "low",
            "evidence":           [],
            "limitations":        [BATCH_LIMITATION, str(e)],
        }
        fail += 1
        loop_errors.append(f"{request_id}: {e}")
        (RAW_RESP_DIR / f"{request_id}_error_traceback.txt").write_text(tb, encoding="utf-8")
        print(f"    → FAIL: {e}")

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

# When --only was used, recount status across all 8 output files so summary
# reflects the full picture, not just the re-run subset.
if ONLY_IDS:
    ok = partial = fail = 0
    for req in batches_plan:
        fp = BATCHES_OUT_DIR / f"{req['request_id']}.json"
        if fp.exists():
            try:
                s = json.loads(fp.read_text(encoding="utf-8")).get("status", "FAIL")
            except Exception:
                s = "FAIL"
        else:
            s = "FAIL"
        if s == "OK":
            ok += 1
        elif s == "PARTIAL":
            partial += 1
        else:
            fail += 1

if fail == 0 and partial == 0:
    summary_status = "OK"
elif ok > 0 or partial > 0:
    summary_status = "PARTIAL"
else:
    summary_status = "FAIL"

summary = {
    "batches_total":               len(batches_plan),
    "batches_ok":                  ok,
    "batches_partial":             partial,
    "batches_fail":                fail,
    "batches_skipped_existing_ok": skipped,
    "openai_calls_made":           calls_made,
    "only_filter":                 sorted(ONLY_IDS) if ONLY_IDS else None,
    "status":                      summary_status,
    "errors":                      loop_errors,
}

SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

total_norm = sum(len(e["normalizations"]) for e in norm_summary)
norm_out = {
    "batches_with_normalizations": len(norm_summary),
    "total_roles_normalized":      total_norm,
    "details":                     norm_summary,
}
NORM_SUMMARY_PATH.write_text(json.dumps(norm_out, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nbatches: OK={ok} PARTIAL={partial} FAIL={fail} skipped={skipped} calls={calls_made}")
print(f"roles normalized across all batches: {total_norm}")
print(f"status: {summary_status}")
print(f"saved: {SUMMARY_PATH.relative_to(BASE)}")
print(f"saved: {NORM_SUMMARY_PATH.relative_to(BASE)}")
