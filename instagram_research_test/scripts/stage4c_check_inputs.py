import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent

POSTS_DIR         = BASE / "analysis/stage4b/posts"
BATCHES_DIR       = BASE / "analysis/stage4b/highlight_batches"
POSTS_SUMMARY     = BASE / "data/normalized/stage4b_posts_summary.json"
BATCHES_SUMMARY   = BASE / "data/normalized/stage4b_highlight_batches_summary.json"
OUT_PATH          = BASE / "data/normalized/stage4c_inputs_check.json"

REQUIRED_FIELDS   = {"observed_facts", "inferred_meanings", "evidence", "confidence"}

errors = []

# ── Posts ─────────────────────────────────────────────────────────────────────
post_files = sorted(POSTS_DIR.glob("*.json")) if POSTS_DIR.exists() else []
posts_found = len(post_files)
posts_ok    = 0

if posts_found == 0:
    errors.append("no post JSON files found in analysis/stage4b/posts/")
elif posts_found != 5:
    errors.append(f"expected 5 post JSON files, found {posts_found}")

for pf in post_files:
    try:
        data = json.loads(pf.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"{pf.name}: parse error — {e}")
        continue
    if data.get("status") != "OK":
        errors.append(f"{pf.name}: status is '{data.get('status')}', expected OK")
        continue
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"{pf.name}: missing required fields: {sorted(missing)}")
        continue
    posts_ok += 1

# ── Highlight batches ─────────────────────────────────────────────────────────
batch_files = sorted(BATCHES_DIR.glob("*.json")) if BATCHES_DIR.exists() else []
batches_found = len(batch_files)
batches_ok    = 0

if batches_found == 0:
    errors.append("no batch JSON files found in analysis/stage4b/highlight_batches/")
elif batches_found != 8:
    errors.append(f"expected 8 batch JSON files, found {batches_found}")

for bf in batch_files:
    try:
        data = json.loads(bf.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"{bf.name}: parse error — {e}")
        continue
    if data.get("status") != "OK":
        errors.append(f"{bf.name}: status is '{data.get('status')}', expected OK")
        continue
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        errors.append(f"{bf.name}: missing required fields: {sorted(missing)}")
        continue
    batches_ok += 1

# ── Summaries ─────────────────────────────────────────────────────────────────
if not POSTS_SUMMARY.exists():
    errors.append("stage4b_posts_summary.json not found")
else:
    try:
        ps = json.loads(POSTS_SUMMARY.read_text(encoding="utf-8"))
        if ps.get("status") != "OK":
            errors.append(f"stage4b_posts_summary.status = '{ps.get('status')}', expected OK")
    except Exception as e:
        errors.append(f"stage4b_posts_summary.json parse error: {e}")

if not BATCHES_SUMMARY.exists():
    errors.append("stage4b_highlight_batches_summary.json not found")
else:
    try:
        bs = json.loads(BATCHES_SUMMARY.read_text(encoding="utf-8"))
        if bs.get("status") != "OK":
            errors.append(
                f"stage4b_highlight_batches_summary.status = '{bs.get('status')}', expected OK"
            )
    except Exception as e:
        errors.append(f"stage4b_highlight_batches_summary.json parse error: {e}")

# ── Result ────────────────────────────────────────────────────────────────────
can_continue = (
    posts_ok == 5
    and batches_ok == 8
    and len(errors) == 0
)

result = {
    "stage":                   "stage4c_inputs_check",
    "posts_found":             posts_found,
    "posts_ok":                posts_ok,
    "highlight_batches_found": batches_found,
    "highlight_batches_ok":    batches_ok,
    "stage4c_can_continue":    can_continue,
    "errors":                  errors,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"posts_found:             {posts_found}")
print(f"posts_ok:                {posts_ok}")
print(f"highlight_batches_found: {batches_found}")
print(f"highlight_batches_ok:    {batches_ok}")
print(f"stage4c_can_continue:    {can_continue}")
if errors:
    print("errors:")
    for e in errors:
        print(f"  - {e}")
print(f"saved: {OUT_PATH.relative_to(BASE)}")

if not can_continue:
    sys.exit(1)
