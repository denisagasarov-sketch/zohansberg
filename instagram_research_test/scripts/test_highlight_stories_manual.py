import json
import os
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

BASE = Path(__file__).parent.parent
load_dotenv(BASE / ".env")

HIGHLIGHT_ID = "17874797856565339"
ACTOR_ID = "igview-owner/instagram-highlights-stories-viewer"

RAW_PATH     = "data/raw/highlight_stories_manual_test_raw.json"
SAMPLE_PATH  = "data/raw/sample_story_manual_item.json"
SUMMARY_PATH = "data/normalized/highlight_stories_manual_summary.json"

def save_json(rel, data):
    p = BASE / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# ── Validate highlightId ──────────────────────────────────────────────────────
if not HIGHLIGHT_ID.isdigit():
    raise SystemExit(f"Invalid highlightId — must be digits only: {HIGHLIGHT_ID}")
if len(HIGHLIGHT_ID) != 17:
    raise SystemExit(f"Invalid highlightId — must be exactly 17 digits, got {len(HIGHLIGHT_ID)}")

print(f"highlightId: {HIGHLIGHT_ID} — valid (17 digits)")

# ── Show payload, then run once ───────────────────────────────────────────────
actor_input = {"highlightId": HIGHLIGHT_ID}

print(f"\n{'='*60}")
print(f"actor id: {ACTOR_ID}")
print(f"input payload:\n{json.dumps(actor_input, indent=2)}")
print("Running this actor once")
print('='*60)

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
if not APIFY_TOKEN:
    raise SystemExit("APIFY_TOKEN missing in .env — aborting")

errors = []
items = None

try:
    client = ApifyClient(APIFY_TOKEN)
    run = client.actor(ACTOR_ID).call(run_input=actor_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
except Exception as e:
    errors.append(str(e))
    print(f"[ERROR] {e}")

# ── Save raw output ───────────────────────────────────────────────────────────
save_json(RAW_PATH, items if items is not None else [])

sample = items[0] if items else None
save_json(SAMPLE_PATH, sample)

# ── Build summary ─────────────────────────────────────────────────────────────
def has(*keys):
    if not sample:
        return False
    return any(k in sample for k in keys)

count = len(items) if items else 0
has_img = has("imageUrl", "image_url", "displayUrl")
has_vid = has("videoUrl", "video_url", "videoSrc")
has_any = has_img or has_vid

if count > 0 and has_any:
    status = "OK"
elif count > 0:
    status = "PARTIAL"
else:
    status = "FAIL"

summary = {
    "status": status,
    "actor_id": ACTOR_ID,
    "highlight_id_tested": HIGHLIGHT_ID,
    "stories_count": count,
    "sample_item_fields": list(sample.keys()) if sample else [],
    "has_storyNumber":  has("storyNumber"),
    "has_storyId":      has("storyId", "story_id", "id"),
    "has_storyType":    has("storyType", "story_type", "type", "mediaType"),
    "has_imageUrl":     has_img,
    "has_videoUrl":     has_vid,
    "has_any_media_url": has_any,
    "has_takenAt":      has("takenAt", "taken_at", "timestamp", "publishDate"),
    "has_duration":     has("duration"),
    "has_rawStoryData": has("rawStoryData", "raw_story_data"),
    "raw_path":    RAW_PATH,
    "sample_path": SAMPLE_PATH,
    "errors": errors,
}
save_json(SUMMARY_PATH, summary)

# ── Print result ──────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"status:        {status}")
print(f"stories_count: {count}")
print(f"has_imageUrl:  {has_img}")
print(f"has_videoUrl:  {has_vid}")
print(f"raw output:    {RAW_PATH}")
print(f"summary:       {SUMMARY_PATH}")
print('='*60)
