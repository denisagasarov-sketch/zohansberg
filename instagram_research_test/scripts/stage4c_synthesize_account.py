import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

CHECK_PATH      = BASE / "data/normalized/stage4c_inputs_check.json"
POSTS_DIR       = BASE / "analysis/stage4b/posts"
HL_SUMMARY_PATH = BASE / "analysis/stage4c/highlight_summary.json"
OUT_DIR         = BASE / "analysis/stage4c"
OUT_PATH        = OUT_DIR / "account_summary.json"

VALID_FUNNEL = {"reach", "trust", "warmup", "sales", "engagement", "leadgen", "expertise", "unknown"}

# ── Guards ────────────────────────────────────────────────────────────────────
if not CHECK_PATH.exists():
    raise SystemExit("stage4c_inputs_check.json not found — run stage4c_check_inputs.py first")
check = json.loads(CHECK_PATH.read_text(encoding="utf-8"))
if not check.get("stage4c_can_continue"):
    raise SystemExit("stage4c_can_continue = false — fix input errors first")

if not HL_SUMMARY_PATH.exists():
    raise SystemExit("highlight_summary.json not found — run stage4c_synthesize_highlight.py first")
hl = json.loads(HL_SUMMARY_PATH.read_text(encoding="utf-8"))

if hl.get("status") == "FAIL":
    result = {
        "status":  "FAIL",
        "account": "vlada_kliuiko",
        "error":   "highlight_summary status is FAIL — account synthesis aborted",
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FAIL: highlight_summary status is FAIL — account synthesis aborted")
    sys.exit(1)

# ── Load posts ────────────────────────────────────────────────────────────────
post_files  = sorted(POSTS_DIR.glob("*.json"))
posts_data  = []
for pf in post_files:
    try:
        posts_data.append((pf.stem, json.loads(pf.read_text(encoding="utf-8"))))
    except Exception as e:
        print(f"  WARNING: could not load {pf.name}: {e}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_empty_value(v):
    return not v or str(v).strip().lower() in (
        "not found", "not enough evidence", "n/a", "unknown", ""
    )


def add_pattern(registry, text, source):
    """Add text+source to a {text_lower: {text, sources}} registry."""
    text = str(text).strip()
    if is_empty_value(text):
        return
    key = text.lower()
    if key not in registry:
        registry[key] = {"text": text, "sources": []}
    if source not in registry[key]["sources"]:
        registry[key]["sources"].append(source)


def registry_to_list(registry, key_name="pattern"):
    return [
        {key_name: v["text"], "source_refs": v["sources"]}
        for v in registry.values()
        if v["sources"]
    ]


# ── Collect from posts ────────────────────────────────────────────────────────
cta_reg           = {}
offer_reg         = {}
sp_reg            = {}
trust_reg         = {}
funnel_map: dict  = {r: [] for r in ("reach", "expertise", "trust", "warmup", "leadgen", "sales")}
content_roles_reg = {}

for src, pd in posts_data:
    im = pd.get("inferred_meanings", {})

    add_pattern(cta_reg,   im.get("cta"),          src)
    add_pattern(offer_reg, im.get("offer"),         src)
    add_pattern(sp_reg,    im.get("social_proof"),  src)

    topic  = im.get("topic",  "")
    fmt    = im.get("format", "")
    if not is_empty_value(topic):
        add_pattern(content_roles_reg, topic, src)
    if not is_empty_value(fmt):
        add_pattern(content_roles_reg, fmt, src)

    funnel_role = im.get("funnel_role", "unknown")
    if funnel_role in funnel_map:
        funnel_map[funnel_role].append(src)
    elif funnel_role and funnel_role not in ("unknown", "engagement"):
        funnel_map.setdefault(funnel_role, []).append(src)

# ── Merge highlight patterns ──────────────────────────────────────────────────
for item in hl.get("cta_patterns", []):
    for ref in item.get("source_refs", []):
        add_pattern(cta_reg, item["pattern"], ref)

for item in hl.get("offer_patterns", []):
    for ref in item.get("source_refs", []):
        add_pattern(offer_reg, item["pattern"], ref)

for item in hl.get("social_proof_patterns", []):
    for ref in item.get("source_refs", []):
        add_pattern(sp_reg, item["pattern"], ref)

for item in hl.get("trust_mechanics", []):
    for ref in item.get("source_refs", []):
        add_pattern(trust_reg, item.get("mechanic", ""), ref)

# ── Primary offer ─────────────────────────────────────────────────────────────
# Prefer offers with most source_refs; fallback to first non-empty offer pattern
offer_list = registry_to_list(offer_reg)
offer_list_sorted = sorted(offer_list, key=lambda x: len(x["source_refs"]), reverse=True)
if offer_list_sorted:
    primary_offer = {
        "value":       offer_list_sorted[0]["pattern"],
        "source_refs": offer_list_sorted[0]["source_refs"],
    }
else:
    primary_offer = {"value": "not enough evidence", "source_refs": []}

# ── Content roles (from posts topics/formats) ─────────────────────────────────
content_roles = [
    {"role": v["text"], "source_refs": v["sources"]}
    for v in content_roles_reg.values()
    if v["sources"]
]

# ── Trust mechanics ────────────────────────────────────────────────────────────
trust_mechanics = registry_to_list(trust_reg, key_name="mechanic")

# ── Weak spots ────────────────────────────────────────────────────────────────
weak_spots = []

# CTA weak: posts where CTA = not found
no_cta_posts = [src for src, pd in posts_data
                if is_empty_value(pd.get("inferred_meanings", {}).get("cta"))]
if no_cta_posts:
    weak_spots.append({
        "spot":        f"CTA not found in {len(no_cta_posts)} out of {len(posts_data)} posts",
        "source_refs": no_cta_posts,
    })

# Offer weak: posts where offer = not found
no_offer_posts = [src for src, pd in posts_data
                  if is_empty_value(pd.get("inferred_meanings", {}).get("offer"))]
if no_offer_posts:
    weak_spots.append({
        "spot":        f"Explicit offer not found in {len(no_offer_posts)} out of {len(posts_data)} posts",
        "source_refs": no_offer_posts,
    })

# Pricing weak: no pricing role in highlight
hl_roles = set(hl.get("main_roles", []))
if "pricing" not in hl_roles:
    weak_spots.append({
        "spot":        "pricing role not observed in highlight stories",
        "source_refs": ["highlight_summary"],
    })

# Standard unanalyzed scope limitations
weak_spots.extend([
    {"spot": "bio not analyzed — direct link / offer in bio unknown", "source_refs": ["limitation"]},
    {"spot": "direct funnel link from posts not analyzed",            "source_refs": ["limitation"]},
    {"spot": "website/bot funnel not analyzed",                       "source_refs": ["limitation"]},
    {"spot": "only one highlight analyzed — full highlight profile may differ",
     "source_refs": ["limitation"]},
])

# ── Ideas to adapt ────────────────────────────────────────────────────────────
ideas_to_adapt = []

# From trust mechanics
for tm in trust_mechanics[:3]:
    ideas_to_adapt.append({
        "idea":        f"Adapt trust mechanic: {tm['mechanic']}",
        "source_refs": tm["source_refs"],
    })

# From dominant highlight role
dom_role = hl.get("dominant_role", "unknown")
if dom_role not in ("unknown", ""):
    ideas_to_adapt.append({
        "idea":        (
            f"Use '{dom_role}' as a primary highlight role — "
            f"this account demonstrates it across {hl.get('batches_analyzed', 0)} batches"
        ),
        "source_refs": ["highlight_summary"],
    })

# From social proof patterns
for sp in registry_to_list(sp_reg)[:3]:
    ideas_to_adapt.append({
        "idea":        f"Social proof mechanic to adapt: {sp['pattern']}",
        "source_refs": sp["source_refs"],
    })

# ── Limitations ───────────────────────────────────────────────────────────────
limitations = [
    "Bio not analyzed",
    "Pinned posts not separately analyzed",
    "Only one highlight analyzed",
    "No website/bot funnel analysis",
    "Post score field unreliable (often 1) — not used as quality signal",
    "Synthesis is fully local — no LLM interpretation applied at Stage 4C",
]

# ── Confidence ────────────────────────────────────────────────────────────────
hl_confidence    = hl.get("confidence", "low")
post_confidences = [pd.get("confidence", "low") for _, pd in posts_data]
conf_order       = {"low": 0, "medium": 1, "high": 2}
all_conf         = post_confidences + [hl_confidence]
agg_confidence   = min(all_conf, key=lambda c: conf_order.get(c, 0)) if all_conf else "low"

# ── Quality gates / status ────────────────────────────────────────────────────
sp_list    = registry_to_list(sp_reg)
cta_list   = registry_to_list(cta_reg)
offer_list = registry_to_list(offer_reg)

most_empty = sum(
    1 for v in list(content_roles_reg.values()) + list(trust_reg.values())
    if not v["sources"]
)

if primary_offer["value"] == "not enough evidence":
    status = "PARTIAL"
elif len(trust_mechanics) < 3:
    status = "PARTIAL"
elif len(sp_list) < 3:
    status = "PARTIAL"
elif most_empty > len(content_roles_reg) // 2:
    status = "FAIL"
else:
    status = "OK"

result = {
    "status":                          status,
    "account":                         "vlada_kliuiko",
    "analyzed_posts_count":            len(posts_data),
    "analyzed_highlights_count":       1,
    "analyzed_highlight_stories_count": 57,
    "primary_offer":                   primary_offer,
    "content_roles":                   content_roles,
    "funnel_roles":                    funnel_map,
    "cta_patterns":                    cta_list,
    "offer_patterns":                  offer_list,
    "social_proof_patterns":           sp_list,
    "trust_mechanics":                 trust_mechanics,
    "weak_spots":                      weak_spots,
    "ideas_to_adapt":                  ideas_to_adapt,
    "limitations":                     limitations,
    "confidence":                      agg_confidence,
}

OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"primary_offer:         {primary_offer['value'][:60]}")
print(f"content_roles:         {len(content_roles)}")
print(f"cta_patterns:          {len(cta_list)}")
print(f"offer_patterns:        {len(offer_list)}")
print(f"social_proof_patterns: {len(sp_list)}")
print(f"trust_mechanics:       {len(trust_mechanics)}")
print(f"weak_spots:            {len(weak_spots)}")
print(f"ideas_to_adapt:        {len(ideas_to_adapt)}")
print(f"confidence:            {agg_confidence}")
print(f"status:                {status}")
print(f"saved: {OUT_PATH.relative_to(BASE)}")

if status == "FAIL":
    sys.exit(1)
