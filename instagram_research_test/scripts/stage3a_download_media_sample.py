import json
import re
import urllib.request
from pathlib import Path
from urllib.error import URLError

BASE = Path(__file__).parent.parent

CHECK_PATH   = BASE / "data/normalized/stage3a_raw_inputs_check.json"
POSTS_PATH   = BASE / "data/raw/posts_test_raw.json"
STORIES_PATH = BASE / "data/raw/highlight_stories_manual_test_raw.json"
MANIFEST_PATH = BASE / "data/normalized/stage3a_media_manifest.json"
ERRORS_PATH   = BASE / "data/normalized/stage3a_media_download_errors.json"

POSTS_DIR     = BASE / "output/media/stage3a/posts"
HIGHLIGHTS_DIR = BASE / "output/media/stage3a/highlights"

for d in (POSTS_DIR, HIGHLIGHTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Guard: check stage3a_can_continue ────────────────────────────────────────
if not CHECK_PATH.exists():
    raise SystemExit("stage3a_raw_inputs_check.json not found — run stage3a_check_raw_inputs.py first")

check = json.loads(CHECK_PATH.read_text())
if not check.get("stage3a_can_continue"):
    print("stage3a_can_continue = false — skipping media download")
    manifest = {
        "post_media": [], "highlight_media": [],
        "summary": {
            "post_image_downloaded": False, "post_video_downloaded": False,
            "highlight_image_downloaded": False, "highlight_video_downloaded": False,
            "total_files_downloaded": 0, "status": "FAIL",
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    ERRORS_PATH.write_text(json.dumps(check.get("errors", []), ensure_ascii=False, indent=2))
    raise SystemExit(0)

# ── Helpers ───────────────────────────────────────────────────────────────────
download_errors = []

def safe_filename(s):
    return re.sub(r"[^\w\-.]", "_", str(s))[:80]

def download(url, dest_path, label):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        dest_path.write_bytes(data)
        return len(data), None
    except (URLError, Exception) as e:
        err = str(e)
        download_errors.append({"label": label, "error": err})
        print(f"[WARN] {label}: {err}")
        return 0, err

def find_field(item, *keys):
    for k in keys:
        if k in item and item[k]:
            return k, item[k]
    return None, None

def content_id(item):
    for k in ("shortCode", "shortcode", "id", "storyId", "story_id"):
        if k in item:
            return str(item[k])[:40]
    return "unknown"

# ── Posts: 1 image + 1 video ──────────────────────────────────────────────────
posts = json.loads(POSTS_PATH.read_text())
post_media = []

img_done = vid_done = False

for item in posts:
    if img_done and vid_done:
        break

    cid = content_id(item)

    if not img_done:
        field, url = find_field(item, "displayUrl", "imageUrl", "thumbnailUrl", "media_url")
        if url:
            ext = ".jpg"
            dest = POSTS_DIR / f"{safe_filename(cid)}_image{ext}"
            size, err = download(url, dest, f"post image {cid}")
            post_media.append({
                "source": "post", "content_id": cid, "media_type": "image",
                "source_url_field": field, "source_url": url,
                "local_path": str(dest.relative_to(BASE)),
                "downloaded": err is None, "file_size_bytes": size, "error": err,
            })
            img_done = True

    if not vid_done:
        field, url = find_field(item, "videoUrl", "video_url", "videoSrc")
        if url:
            ext = ".mp4"
            dest = POSTS_DIR / f"{safe_filename(cid)}_video{ext}"
            size, err = download(url, dest, f"post video {cid}")
            post_media.append({
                "source": "post", "content_id": cid, "media_type": "video",
                "source_url_field": field, "source_url": url,
                "local_path": str(dest.relative_to(BASE)),
                "downloaded": err is None, "file_size_bytes": size, "error": err,
            })
            vid_done = True

# ── Highlight stories: 1 image + 1 video ─────────────────────────────────────
stories = json.loads(STORIES_PATH.read_text())
highlight_media = []

hl_img_done = hl_vid_done = False

for item in stories:
    if hl_img_done and hl_vid_done:
        break

    sid = content_id(item)

    if not hl_img_done:
        field, url = find_field(item, "imageUrl", "image_url", "displayUrl")
        if url:
            dest = HIGHLIGHTS_DIR / f"{safe_filename(sid)}_image.jpg"
            size, err = download(url, dest, f"story image {sid}")
            highlight_media.append({
                "source": "highlight_story", "story_id": sid, "media_type": "image",
                "source_url_field": field, "source_url": url,
                "local_path": str(dest.relative_to(BASE)),
                "downloaded": err is None, "file_size_bytes": size, "error": err,
            })
            hl_img_done = True

    if not hl_vid_done:
        field, url = find_field(item, "videoUrl", "video_url", "videoSrc")
        if url:
            dest = HIGHLIGHTS_DIR / f"{safe_filename(sid)}_video.mp4"
            size, err = download(url, dest, f"story video {sid}")
            highlight_media.append({
                "source": "highlight_story", "story_id": sid, "media_type": "video",
                "source_url_field": field, "source_url": url,
                "local_path": str(dest.relative_to(BASE)),
                "downloaded": err is None, "file_size_bytes": size, "error": err,
            })
            hl_vid_done = True

# ── Manifest ──────────────────────────────────────────────────────────────────
def any_downloaded(items, media_type):
    return any(i["downloaded"] and i["media_type"] == media_type for i in items)

total = sum(1 for i in post_media + highlight_media if i["downloaded"])

pi = any_downloaded(post_media, "image")
pv = any_downloaded(post_media, "video")
hi = any_downloaded(highlight_media, "image")
hv = any_downloaded(highlight_media, "video")

if (pi or pv) and (hi or hv):
    status = "OK"
elif pi or pv or hi or hv:
    status = "PARTIAL"
else:
    status = "FAIL"

manifest = {
    "post_media": post_media,
    "highlight_media": highlight_media,
    "summary": {
        "post_image_downloaded": pi,
        "post_video_downloaded": pv,
        "highlight_image_downloaded": hi,
        "highlight_video_downloaded": hv,
        "total_files_downloaded": total,
        "status": status,
    },
}

MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
ERRORS_PATH.write_text(json.dumps(download_errors, ensure_ascii=False, indent=2))

print(f"post image:      {'OK' if pi else 'not downloaded'}")
print(f"post video:      {'OK' if pv else 'not downloaded'}")
print(f"highlight image: {'OK' if hi else 'not downloaded'}")
print(f"highlight video: {'OK' if hv else 'not downloaded'}")
print(f"total downloaded: {total}")
print(f"status: {status}")
print(f"manifest: {MANIFEST_PATH.relative_to(BASE)}")
