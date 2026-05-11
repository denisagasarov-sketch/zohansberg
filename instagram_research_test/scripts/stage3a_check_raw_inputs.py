import json
from pathlib import Path

BASE = Path(__file__).parent.parent

POSTS_PATH   = BASE / "data/raw/posts_test_raw.json"
STORIES_PATH = BASE / "data/raw/highlight_stories_manual_test_raw.json"
OUT_PATH     = BASE / "data/normalized/stage3a_raw_inputs_check.json"

VISUAL_FIELDS = {
    "displayUrl", "imageUrl", "thumbnailUrl", "videoUrl", "videoSrc",
    "media_url", "display_url", "thumbnail", "images", "carouselMedia",
}

errors = []

def check_file(path, label):
    result = {
        "path": str(path.relative_to(BASE)),
        "exists": False,
        "not_empty": False,
        "items_count": 0,
        "sample_fields": [],
        "status": "FAIL",
    }
    if not path.exists():
        errors.append(f"{label}: file not found at {path}")
        return result

    result["exists"] = True
    size = path.stat().st_size

    if size <= 2:
        errors.append(f"{label}: file exists but is empty (size={size} bytes)")
        return result

    try:
        data = json.loads(path.read_text())
    except Exception as e:
        errors.append(f"{label}: JSON parse error — {e}")
        return result

    if not isinstance(data, list) or len(data) == 0:
        errors.append(f"{label}: parsed JSON is empty or not a list")
        return result

    result["not_empty"] = True
    result["items_count"] = len(data)
    result["sample_fields"] = list(data[0].keys()) if data else []
    return result, data

# ── Posts ─────────────────────────────────────────────────────────────────────
posts_result = check_file(POSTS_PATH, "posts_raw")
posts_data = None
if isinstance(posts_result, tuple):
    posts_result, posts_data = posts_result

if posts_data:
    sample = posts_data[0]
    has_vis = bool(VISUAL_FIELDS & set(sample.keys()))
    posts_result["has_visual_or_media_fields"] = has_vis
    posts_result["status"] = "OK" if has_vis else "PARTIAL"
else:
    posts_result["has_visual_or_media_fields"] = False

# ── Stories ───────────────────────────────────────────────────────────────────
stories_result = check_file(STORIES_PATH, "highlight_stories_raw")
stories_data = None
if isinstance(stories_result, tuple):
    stories_result, stories_data = stories_result

if stories_data:
    sample = stories_data[0]
    has_img = any(k in sample for k in ("imageUrl", "image_url", "displayUrl"))
    has_vid = any(k in sample for k in ("videoUrl", "video_url", "videoSrc"))
    stories_result["has_imageUrl"] = has_img
    stories_result["has_videoUrl"] = has_vid
    stories_result["status"] = "OK" if (has_img or has_vid) else "PARTIAL"
else:
    stories_result["has_imageUrl"] = False
    stories_result["has_videoUrl"] = False

# ── Output ────────────────────────────────────────────────────────────────────
can_continue = (
    posts_result["status"] in ("OK", "PARTIAL")
    and posts_result["not_empty"]
    and stories_result["status"] in ("OK", "PARTIAL")
    and stories_result["not_empty"]
)

output = {
    "posts_raw": posts_result,
    "highlight_stories_raw": stories_result,
    "stage3a_can_continue": can_continue,
    "errors": errors,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))

print(f"posts:   exists={posts_result['exists']} | count={posts_result['items_count']} | status={posts_result['status']}")
print(f"stories: exists={stories_result['exists']} | count={stories_result['items_count']} | status={stories_result['status']}")
print(f"stage3a_can_continue: {can_continue}")
if errors:
    print("errors:")
    for e in errors:
        print(f"  - {e}")
print(f"saved: {OUT_PATH.relative_to(BASE)}")
