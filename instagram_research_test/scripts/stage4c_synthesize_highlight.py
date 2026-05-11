import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent.parent

CHECK_PATH   = BASE / "data/normalized/stage4c_inputs_check.json"
BATCHES_DIR  = BASE / "analysis/stage4b/highlight_batches"
OUT_DIR      = BASE / "analysis/stage4c"
OUT_PATH     = OUT_DIR / "highlight_summary.json"

HIGHLIGHT_ID  = "17874797856565339"
STORIES_TOTAL = 57

VALID_ROLES = {
    "social_proof", "student_results", "course_trust", "community",
    "education", "reviews", "cases", "faq", "product", "pricing",
    "about", "process", "backstage", "lead_magnet", "unknown",
}

# ── Guard ─────────────────────────────────────────────────────────────────────
if not CHECK_PATH.exists():
    raise SystemExit("stage4c_inputs_check.json not found — run stage4c_check_inputs.py first")
check = json.loads(CHECK_PATH.read_text(encoding="utf-8"))
if not check.get("stage4c_can_continue"):
    raise SystemExit("stage4c_can_continue = false — fix input errors first")

# ── Load batches ──────────────────────────────────────────────────────────────
batch_files  = sorted(BATCHES_DIR.glob("*.json"))
batches_data = []
for bf in batch_files:
    try:
        batches_data.append((bf.stem, json.loads(bf.read_text(encoding="utf-8"))))
    except Exception as e:
        print(f"  WARNING: could not load {bf.name}: {e}")

batches_analyzed = len(batches_data)

# ── Aggregate roles ───────────────────────────────────────────────────────────
all_roles_flat: list = []
for src, bd in batches_data:
    roles = bd.get("inferred_meanings", {}).get("main_roles", [])
    for r in roles:
        if r in VALID_ROLES:
            all_roles_flat.append(r)

role_counter   = Counter(all_roles_flat)
role_frequency = dict(role_counter.most_common())
all_roles_dedup = list(dict.fromkeys(all_roles_flat))  # ordered, deduplicated

dominant_role = role_counter.most_common(1)[0][0] if role_counter else "unknown"

# ── Collect patterns with source_refs ─────────────────────────────────────────
def collect_patterns(field, sub_key=None):
    """
    Collects non-empty values from inferred_meanings[field] across all batches.
    Returns list of {pattern/mechanic, source_refs} dicts with source_refs populated.
    sub_key: if field value is a dict, use this key.
    """
    seen: dict = {}   # normalized_value → list of source_refs
    for src, bd in batches_data:
        im  = bd.get("inferred_meanings", {})
        val = im.get(field)
        if not val:
            continue
        if isinstance(val, list):
            items = val
        else:
            items = [val]
        for item in items:
            if sub_key and isinstance(item, dict):
                text = item.get(sub_key, "")
            else:
                text = str(item).strip()
            if not text or text.lower() in ("not found", "not enough evidence", "n/a", ""):
                continue
            key = text.lower()
            if key not in seen:
                seen[key] = {"text": text, "sources": []}
            if src not in seen[key]["sources"]:
                seen[key]["sources"].append(src)
    return [
        {"pattern": v["text"], "source_refs": v["sources"]}
        for v in seen.values()
        if v["sources"]
    ]


def collect_string_field(field):
    """Collects a single string field from inferred_meanings, deduplicated."""
    seen: dict = {}
    for src, bd in batches_data:
        val = bd.get("inferred_meanings", {}).get(field, "")
        if not val or str(val).lower() in ("not found", "not enough evidence", ""):
            continue
        key = str(val).strip().lower()
        if key not in seen:
            seen[key] = {"text": str(val).strip(), "sources": []}
        if src not in seen[key]["sources"]:
            seen[key]["sources"].append(src)
    return [
        {"pattern": v["text"], "source_refs": v["sources"]}
        for v in seen.values()
        if v["sources"]
    ]


cta_patterns         = collect_string_field("cta_found")
offer_patterns       = collect_string_field("offer_found")
social_proof_patterns = collect_string_field("social_proof_found")

# trust_mechanics: list field
trust_seen: dict = {}
for src, bd in batches_data:
    mechanics = bd.get("inferred_meanings", {}).get("trust_mechanics", [])
    if isinstance(mechanics, list):
        for m in mechanics:
            text = str(m).strip()
            if not text or text.lower() in ("not found", "not enough evidence", ""):
                continue
            key = text.lower()
            if key not in trust_seen:
                trust_seen[key] = {"text": text, "sources": []}
            if src not in trust_seen[key]["sources"]:
                trust_seen[key]["sources"].append(src)
trust_mechanics = [
    {"mechanic": v["text"], "source_refs": v["sources"]}
    for v in trust_seen.values()
    if v["sources"]
]

# key_evidence: take up to 2 items per batch, keep short
evidence_seen: dict = {}
for src, bd in batches_data:
    evidence_list = bd.get("evidence", [])
    if isinstance(evidence_list, list):
        for ev in evidence_list[:2]:
            text = str(ev).strip()
            if len(text) > 200:
                text = text[:197] + "..."
            if not text:
                continue
            key = text.lower()[:80]
            if key not in evidence_seen:
                evidence_seen[key] = {"text": text, "sources": []}
            if src not in evidence_seen[key]["sources"]:
                evidence_seen[key]["sources"].append(src)
key_evidence = [
    {"evidence": v["text"], "source_refs": v["sources"]}
    for v in evidence_seen.values()
    if v["sources"]
]

# ── Aggregate scores ──────────────────────────────────────────────────────────
dss_values = []
for _, bd in batches_data:
    dss = bd.get("inferred_meanings", {}).get("decision_support_score")
    if isinstance(dss, (int, float)) and 1 <= dss <= 10:
        dss_values.append(dss)
avg_dss = round(sum(dss_values) / len(dss_values), 1) if dss_values else 1

# Confidence: lowest wins (most conservative)
confidence_order = {"low": 0, "medium": 1, "high": 2}
confidences = [
    bd.get("confidence", "low")
    for _, bd in batches_data
    if bd.get("confidence") in confidence_order
]
agg_confidence = min(confidences, key=lambda c: confidence_order[c]) if confidences else "low"

# ── Limitations ───────────────────────────────────────────────────────────────
limitations = [
    "Synthesis based on 8 batches of 57 stories; batch boundaries may split context",
    "No bio analysis",
    "No pinned posts analysis",
    "No website/bot funnel analysis",
    "Analysis limited to visual content and visible text in stories",
]

# ── Build summary text ────────────────────────────────────────────────────────
top_roles_str = ", ".join(
    f"{r} ({c})" for r, c in role_counter.most_common(5)
) or "unknown"
summary_text = (
    f"Highlight ({STORIES_TOTAL} stories, {batches_analyzed} batches). "
    f"Dominant role: {dominant_role}. "
    f"Top roles: {top_roles_str}. "
    f"Avg decision support score: {avg_dss}/10."
)

# ── Status ────────────────────────────────────────────────────────────────────
if batches_analyzed < 8:
    status = "FAIL"
elif len(key_evidence) < 5:
    status = "PARTIAL"
else:
    status = "OK"

result = {
    "status":               status,
    "account":              "vlada_kliuiko",
    "highlight_id":         HIGHLIGHT_ID,
    "stories_total":        STORIES_TOTAL,
    "batches_analyzed":     batches_analyzed,
    "dominant_role":        dominant_role,
    "main_roles":           all_roles_dedup,
    "role_frequency":       role_frequency,
    "summary":              summary_text,
    "cta_patterns":          cta_patterns,
    "offer_patterns":        offer_patterns,
    "social_proof_patterns": social_proof_patterns,
    "trust_mechanics":       trust_mechanics,
    "key_evidence":          key_evidence,
    "decision_support_score": avg_dss,
    "confidence":            agg_confidence,
    "limitations":           limitations,
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"batches_analyzed:       {batches_analyzed}")
print(f"dominant_role:          {dominant_role}")
print(f"top 5 roles:            {top_roles_str}")
print(f"cta_patterns:           {len(cta_patterns)}")
print(f"offer_patterns:         {len(offer_patterns)}")
print(f"social_proof_patterns:  {len(social_proof_patterns)}")
print(f"trust_mechanics:        {len(trust_mechanics)}")
print(f"key_evidence:           {len(key_evidence)}")
print(f"decision_support_score: {avg_dss}")
print(f"confidence:             {agg_confidence}")
print(f"status:                 {status}")
print(f"saved: {OUT_PATH.relative_to(BASE)}")

if status == "FAIL":
    sys.exit(1)
