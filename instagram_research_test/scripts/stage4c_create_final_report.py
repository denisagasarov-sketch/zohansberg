import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

HL_SUMMARY_PATH  = BASE / "analysis/stage4c/highlight_summary.json"
ACC_SUMMARY_PATH = BASE / "analysis/stage4c/account_summary.json"
POSTS_DIR        = BASE / "analysis/stage4b/posts"
BATCHES_DIR      = BASE / "analysis/stage4b/highlight_batches"
REPORT_PATH      = BASE / "report/final_one_account_analysis_vlada_kliuiko.md"


def load_json(path, label):
    if not path.exists():
        return None, f"{label} not found"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, f"{label} parse error: {e}"


hl,  hl_err  = load_json(HL_SUMMARY_PATH,  "highlight_summary.json")
acc, acc_err = load_json(ACC_SUMMARY_PATH, "account_summary.json")

L = []   # report lines


def h(text):  L.append(f"\n{text}\n")
def li(text): L.append(f"- {text}")
def kv(k, v): L.append(f"- **{k}:** {v}")
def src(refs):
    if refs:
        L.append(f"  _sources: {', '.join(str(r) for r in refs)}_")


# ── Title ──────────────────────────────────────────────────────────────────────
L.append("# Instagram Account Analysis — vlada_kliuiko")
L.append(f"\n_Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}_\n")

# ── Scope ──────────────────────────────────────────────────────────────────────
h("## Scope")
L.append("| Field | Value |")
L.append("|-------|-------|")
L.append("| account | vlada_kliuiko |")
L.append("| posts analyzed | 5 |")
L.append("| highlight analyzed | 1 (ID: 17874797856565339) |")
L.append("| highlight stories analyzed | 57 |")
L.append("| method | local synthesis from Stage 4B JSON outputs — no new scraping, no image re-analysis |")
L.append("")
L.append("**Limitations:**")
for lim in [
    "Bio not analyzed",
    "Pinned posts not separately analyzed",
    "Only one highlight analyzed",
    "No website/bot funnel analysis",
    "Post score field unreliable (often 1) — not used as quality signal",
]:
    li(lim)

# ── Executive summary ──────────────────────────────────────────────────────────
h("## Executive Summary")
if acc_err:
    L.append(f"> ERROR: {acc_err}")
elif hl_err:
    L.append(f"> ERROR: {hl_err}")
else:
    po = acc.get("primary_offer", {})
    L.append(
        f"**vlada_kliuiko** is an Instagram account built around "
        f"**{po.get('value', 'not enough evidence')}**."
    )
    src(po.get("source_refs", []))
    L.append("")

    dom_role  = hl.get("dominant_role", "unknown") if hl else "unknown"
    hl_conf   = hl.get("confidence", "low")        if hl else "low"
    acc_conf  = acc.get("confidence", "low")

    L.append(f"The highlight (57 stories, 8 batches) is dominated by the **{dom_role}** role, "
             f"suggesting the account uses it as a primary trust-building and conversion asset.")
    src(["highlight_summary"])
    L.append("")

    tm_count = len(acc.get("trust_mechanics", []))
    sp_count = len(acc.get("social_proof_patterns", []))
    L.append(
        f"Trust is built through **{tm_count} distinct trust mechanics** and "
        f"**{sp_count} social proof patterns** identified across posts and highlight batches."
    )
    src(["highlight_summary", "posts (all)"])
    L.append("")

    funnel = acc.get("funnel_roles", {})
    active_roles = [r for r, ids in funnel.items() if ids]
    if active_roles:
        L.append(f"Active funnel roles in posts: **{', '.join(active_roles)}**.")
        src([id_ for r in active_roles for id_ in funnel[r]])

# ── Posts analysis ─────────────────────────────────────────────────────────────
h("## Posts Analysis")
post_files = sorted(POSTS_DIR.glob("*.json")) if POSTS_DIR.exists() else []
if not post_files:
    L.append("> No post JSON files found.")
else:
    for pf in post_files:
        try:
            pd = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            L.append(f"### {pf.stem}\n> ERROR: could not load file\n")
            continue
        im      = pd.get("inferred_meanings", {})
        of      = pd.get("observed_facts", {})
        ev_list = pd.get("evidence", [])

        L.append(f"### {pf.stem}")
        kv("url",          pd.get("url", "—"))
        kv("type",         pd.get("type", "—"))
        kv("topic",        im.get("topic", "—"))
        kv("format",       im.get("format", "—"))
        kv("hook",         im.get("hook", "—"))
        kv("CTA",          im.get("cta", "not found"))
        kv("offer",        im.get("offer", "not found"))
        kv("social proof", im.get("social_proof", "not found"))
        kv("funnel role",  im.get("funnel_role", "unknown"))
        kv("confidence",   pd.get("confidence", "—"))
        kv("evidence count", str(len(ev_list)))
        if ev_list:
            L.append(f"- **key evidence:** {str(ev_list[0])[:150]}")
            src([pf.stem])
        L.append("")

# ── Highlight analysis ─────────────────────────────────────────────────────────
h("## Highlight Analysis")
if hl_err:
    L.append(f"> ERROR: {hl_err}")
else:
    kv("highlight_id",         hl.get("highlight_id", "—"))
    kv("stories_total",        hl.get("stories_total", "—"))
    kv("batches_analyzed",     hl.get("batches_analyzed", "—"))
    kv("dominant_role",        hl.get("dominant_role", "—"))
    kv("decision_support_score", f"{hl.get('decision_support_score', '—')}/10")
    kv("confidence",           hl.get("confidence", "—"))
    kv("status",               hl.get("status", "—"))
    L.append("")

    L.append("**Role frequency:**")
    for role, cnt in sorted(
        hl.get("role_frequency", {}).items(), key=lambda x: x[1], reverse=True
    ):
        li(f"{role}: {cnt}")
    L.append("")

    if hl.get("cta_patterns"):
        L.append("**CTA patterns:**")
        for item in hl["cta_patterns"]:
            li(item["pattern"])
            src(item.get("source_refs", []))
        L.append("")

    if hl.get("offer_patterns"):
        L.append("**Offer patterns:**")
        for item in hl["offer_patterns"]:
            li(item["pattern"])
            src(item.get("source_refs", []))
        L.append("")

    if hl.get("social_proof_patterns"):
        L.append("**Social proof patterns:**")
        for item in hl["social_proof_patterns"]:
            li(item["pattern"])
            src(item.get("source_refs", []))
        L.append("")

    if hl.get("trust_mechanics"):
        L.append("**Trust mechanics:**")
        for item in hl["trust_mechanics"]:
            li(item["mechanic"])
            src(item.get("source_refs", []))
        L.append("")

    if hl.get("key_evidence"):
        L.append("**Key evidence (sample):**")
        for item in hl["key_evidence"][:6]:
            li(item["evidence"])
            src(item.get("source_refs", []))
        L.append("")

    if hl.get("limitations"):
        L.append("**Limitations:**")
        for lim in hl["limitations"]:
            li(lim)
        L.append("")

# ── Funnel interpretation ──────────────────────────────────────────────────────
h("## Funnel Interpretation")
if acc_err:
    L.append(f"> ERROR: {acc_err}")
else:
    funnel = acc.get("funnel_roles", {})
    funnel_order = ["reach", "expertise", "trust", "warmup", "leadgen", "sales"]
    for role in funnel_order:
        refs = funnel.get(role, [])
        if refs:
            L.append(f"**{role.capitalize()}:** {', '.join(refs)}")
            src(refs)
        else:
            L.append(f"**{role.capitalize()}:** not enough evidence")
    L.append("")

# ── What works ─────────────────────────────────────────────────────────────────
h("## What Works")
if acc_err:
    L.append(f"> ERROR: {acc_err}")
else:
    patterns_shown = 0

    for tm in acc.get("trust_mechanics", []):
        if patterns_shown >= 10:
            break
        L.append(f"**Trust mechanic:** {tm['mechanic']}")
        L.append("- Why it matters: visible trust signal that supports conversion decisions")
        src(tm.get("source_refs", []))
        L.append("")
        patterns_shown += 1

    for sp in acc.get("social_proof_patterns", []):
        if patterns_shown >= 10:
            break
        L.append(f"**Social proof:** {sp['pattern']}")
        L.append("- Why it matters: demonstrates real-world results or credibility")
        src(sp.get("source_refs", []))
        L.append("")
        patterns_shown += 1

    if hl:
        dom = hl.get("dominant_role", "")
        dss = hl.get("decision_support_score", 0)
        if dom and dom != "unknown" and patterns_shown < 10:
            L.append(f"**Highlight dominant role ({dom})** with avg decision support score {dss}/10")
            L.append("- Why it matters: strong highlight presence reinforces trust and conversion")
            src(["highlight_summary"])
            L.append("")
            patterns_shown += 1

# ── Weak spots ─────────────────────────────────────────────────────────────────
h("## Weak Spots")
if acc_err:
    L.append(f"> ERROR: {acc_err}")
else:
    for ws in acc.get("weak_spots", []):
        L.append(f"**{ws['spot']}**")
        L.append("- Why it matters: limits measurability of conversion or trust signals")
        src(ws.get("source_refs", []))
        L.append("")

# ── Ideas to adapt ─────────────────────────────────────────────────────────────
h("## Ideas to Adapt")
if acc_err:
    L.append(f"> ERROR: {acc_err}")
else:
    for idea in acc.get("ideas_to_adapt", []):
        L.append(f"**{idea['idea']}**")
        L.append("- How to adapt: take the mechanic, not the specific content")
        src(idea.get("source_refs", []))
        L.append("")

# ── Output files ───────────────────────────────────────────────────────────────
h("## Output Files")
L.append("```")
L.append("analysis/stage4c/highlight_summary.json")
L.append("analysis/stage4c/account_summary.json")
L.append("report/final_one_account_analysis_vlada_kliuiko.md")
L.append("```")

# ── Write ──────────────────────────────────────────────────────────────────────
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text("\n".join(L) + "\n", encoding="utf-8")

verdict = (acc or {}).get("status", "FAIL") if not acc_err else "FAIL"
print(f"verdict: {verdict}")
print(f"report saved: {REPORT_PATH.relative_to(BASE)}")
