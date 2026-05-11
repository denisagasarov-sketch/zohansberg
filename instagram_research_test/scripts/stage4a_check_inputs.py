import json
from pathlib import Path

BASE = Path(__file__).parent.parent

POSTS_RAW      = BASE / "data/raw/posts_test_raw.json"
STORIES_RAW    = BASE / "data/raw/highlight_stories_manual_test_raw.json"
MANIFEST_PATH  = BASE / "data/normalized/stage3a_media_manifest.json"
PREVIEW_PATH   = BASE / "data/normalized/stage3b1_openai_input_preview.json"
GITIGNORE_PATH = BASE / ".gitignore"
OUT_PATH       = BASE / "data/normalized/stage4a_inputs_check.json"

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

errors = []

def check_json_file(path, label, expected_count=None):
    result = {"exists": False, "not_empty": False, "items_count": 0, "status": "FAIL"}
    if not path.exists():
        errors.append(f"{label}: file not found")
        return result
    result["exists"] = True
    if path.stat().st_size <= 2:
        errors.append(f"{label}: file is empty")
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"{label}: JSON parse error — {e}")
        return result
    if not isinstance(data, list) or len(data) == 0:
        errors.append(f"{label}: parsed JSON is empty or not a list")
        return result
    result["not_empty"] = True
    result["items_count"] = len(data)
    if expected_count and len(data) != expected_count:
        errors.append(f"{label}: expected {expected_count} items, got {len(data)}")
        result["status"] = "PARTIAL"
    else:
        result["status"] = "OK"
    return result

def check_exists(path, label):
    ok = path.exists()
    if not ok:
        errors.append(f"{label}: file not found")
    return {"exists": ok, "status": "OK" if ok else "FAIL"}

# Checks
posts_result   = check_json_file(POSTS_RAW,   "posts_test_raw.json",   expected_count=5)
stories_result = check_json_file(STORIES_RAW, "highlight_stories_manual_test_raw.json", expected_count=57)
manifest_result = check_exists(MANIFEST_PATH, "stage3a_media_manifest.json")
preview_result  = check_exists(PREVIEW_PATH,  "stage3b1_openai_input_preview.json")

gitignore_safe = False
if GITIGNORE_PATH.exists():
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    required = [".env", "data/raw/", "output/", "analysis/openai_responses/"]
    gitignore_safe = all(r in content for r in required)
if not gitignore_safe:
    errors.append(".gitignore missing required safety entries")

can_continue = (
    posts_result["status"] in ("OK", "PARTIAL") and posts_result["not_empty"]
    and stories_result["status"] in ("OK", "PARTIAL") and stories_result["not_empty"]
    and manifest_result["exists"]
    and preview_result["exists"]
    and gitignore_safe
)

output = {
    "posts_raw":             posts_result,
    "highlight_stories_raw": stories_result,
    "stage3a_manifest":      manifest_result,
    "stage3b1_preview":      preview_result,
    "gitignore_safe":        gitignore_safe,
    "stage4a_can_continue":  can_continue,
    "errors":                errors,
}
OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

for label, result in [
    ("posts_raw",             posts_result),
    ("highlight_stories_raw", stories_result),
    ("stage3a_manifest",      manifest_result),
    ("stage3b1_preview",      preview_result),
]:
    print(f"{label}: exists={result['exists']} | status={result['status']}"
          + (f" | count={result.get('items_count', 'n/a')}" if "items_count" in result else ""))

print(f"gitignore_safe:        {gitignore_safe}")
print(f"stage4a_can_continue:  {can_continue}")
if errors:
    print("errors:")
    for e in errors:
        print(f"  - {e}")
print(f"saved: {OUT_PATH.relative_to(BASE)}")
