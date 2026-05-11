import json
import re
import urllib.request
from pathlib import Path
from urllib.error import URLError

BASE = Path(__file__).parent.parent

POSTS_RAW      = BASE / "data/raw/posts_test_raw.json"
STORIES_RAW    = BASE / "data/raw/highlight_stories_manual_test_raw.json"
CHECK_PATH     = BASE / "data/normalized/stage4a_inputs_check.json"
MANIFEST_OUT   = BASE / "data/normalized/stage4a_media_manifest.json"
ERRORS_OUT     = BASE / "data/normalized/stage4a_media_errors.json"

POSTS_DL_DIR   = BASE / "output/media/stage4/posts"
HL_DL_DIR      = BASE / "output/media/stage4/highlights"
POSTS_OAI_DIR  = BASE / "output/openai_inputs/stage4/posts"
HL_OAI_DIR     = BASE / "output/openai_inputs/stage4/highlights"
FRAMES_DIR     = BASE / "output/openai_inputs/stage4/frames"
for d in (POSTS_DL_DIR, HL_DL_DIR, POSTS_OAI_DIR, HL_OAI_DIR, FRAMES_DIR):
    d.mkdir(parents=True, exist_ok=True)

HIGHLIGHT_ID   = "17874797856565339"
MAX_POSTS      = 5
MAX_STORIES    = 57
MAX_CAROUSEL   = 3
MAX_FRAMES     = 5
MAX_WIDTH      = 1280
JPEG_QUALITY   = 85

# ── Guard ─────────────────────────────────────────────────────────────────────
if not CHECK_PATH.exists():
    raise SystemExit("stage4a_inputs_check.json not found — run stage4a_check_inputs.py first")
check = json.loads(CHECK_PATH.read_text(encoding="utf-8"))
if not check.get("stage4a_can_continue"):
    raise SystemExit("stage4a_can_continue = false — fix input errors first")

posts_data   = json.loads(POSTS_RAW.read_text(encoding="utf-8"))
stories_data = json.loads(STORIES_RAW.read_text(encoding="utf-8"))

all_errors = []
downloaded_urls: set = set()   # dedup tracker

# ── Helpers ───────────────────────────────────────────────────────────────────
def safe_stem(s):
    return re.sub(r"[^\w\-]", "_", str(s))[:60]

def compress_image(src, dest_dir, stem):
    try:
        from PIL import Image
        img = Image.open(src).convert("RGB")
        w, h = img.size
        if w > MAX_WIDTH:
            h = int(h * MAX_WIDTH / w); w = MAX_WIDTH
            img = img.resize((w, h))
        dest = dest_dir / f"{stem}.jpg"
        img.save(dest, "JPEG", quality=JPEG_QUALITY)
        return str(dest.relative_to(BASE)), None
    except Exception as e:
        return None, str(e)

def extract_frames(video_path, stem):
    frames = []
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        if total <= 0:
            cap.release()
            return [], "could not read frame count"
        indices = sorted(set(min(int(i * total / MAX_FRAMES), total - 1) for i in range(MAX_FRAMES)))
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            sec = round(idx / fps, 1)
            dest = FRAMES_DIR / f"{stem}_f{idx}_t{sec}s.jpg"
            h, w = frame.shape[:2]
            if w > MAX_WIDTH:
                import cv2 as _cv; frame = _cv.resize(frame, (MAX_WIDTH, int(h * MAX_WIDTH / w)))
            import cv2 as _cv; _cv.imwrite(str(dest), frame, [_cv.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            frames.append(str(dest.relative_to(BASE)))
        cap.release()
        return frames, None
    except ImportError:
        return [], "opencv-python not installed"
    except Exception as e:
        return [], str(e)

def download(url, dest):
    if url in downloaded_urls:
        return str(dest.relative_to(BASE)) if dest.exists() else None, "duplicate URL skipped"
    if dest.exists():
        downloaded_urls.add(url)
        return str(dest.relative_to(BASE)), None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            dest.write_bytes(r.read())
        downloaded_urls.add(url)
        return str(dest.relative_to(BASE)), None
    except (URLError, Exception) as e:
        return None, str(e)

def get_field(item, *keys):
    for k in keys:
        if k in item and item[k]:
            return k, item[k]
    return None, None

def item_id(item, *keys):
    for k in keys:
        if k in item:
            return str(item[k])[:50]
    return "unknown"

def make_prepared_entry(input_type, source_type, url_field, dl_path, prep_path, size, error):
    return {
        "input_type": input_type,
        "source_type": source_type,
        "original_media_url_field": url_field,
        "downloaded_path": dl_path,
        "prepared_path": prep_path,
        "file_size_bytes": size,
        "used_for_openai_plan": prep_path is not None,
        "error": error,
    }

# ── A. Posts ──────────────────────────────────────────────────────────────────
posts_manifest = []
print(f"Processing {min(len(posts_data), MAX_POSTS)} posts...")

for post in posts_data[:MAX_POSTS]:
    pid        = item_id(post, "shortCode", "shortcode", "id")
    purl       = post.get("url") or post.get("postUrl") or f"https://www.instagram.com/p/{pid}/"
    ptype      = post.get("type") or post.get("productType") or "unknown"
    pcap       = post.get("caption") or post.get("text") or None
    pts        = post.get("timestamp") or post.get("date") or post.get("takenAt") or None
    prepared   = []
    post_errors = []
    sources_found = 0

    # Collect media sources
    media_sources = []  # list of (url_field, url, source_type)

    # Primary image
    f, url = get_field(post, "displayUrl", "imageUrl", "thumbnailUrl", "thumbnail")
    if url:
        media_sources.append((f, url, "post_image"))

    # Video
    vf, vurl = get_field(post, "videoUrl", "video_url", "videoSrc")
    if vurl:
        media_sources.append((vf, vurl, "post_video"))

    # Carousel: up to MAX_CAROUSEL child images
    carousel = post.get("images") or post.get("carouselMedia") or post.get("childPosts") or []
    if isinstance(carousel, list):
        for child in carousel[:MAX_CAROUSEL]:
            if isinstance(child, dict):
                cf, curl = get_field(child, "displayUrl", "imageUrl", "src")
                if curl:
                    media_sources.append((cf, curl, "carousel_image"))

    sources_found = len(media_sources)

    for url_field, url, source_type in media_sources:
        is_video = source_type == "post_video"
        ext  = ".mp4" if is_video else ".jpg"
        dest = POSTS_DL_DIR / f"{safe_stem(pid)}_{source_type}{ext}"
        dl_path, dl_err = download(url, dest)

        if dl_err and dl_path is None:
            post_errors.append(f"{source_type}: {dl_err}")
            all_errors.append({"post_id": pid, "source_type": source_type, "error": dl_err})
            prepared.append(make_prepared_entry(
                "image" if not is_video else "video",
                source_type, url_field, None, None, 0, dl_err))
            continue

        if is_video:
            frames, ferr = extract_frames(BASE / dl_path, f"post_{safe_stem(pid)}")
            if ferr:
                post_errors.append(f"frame extraction: {ferr}")
            for fr in frames:
                comp, cerr = compress_image(BASE / fr, POSTS_OAI_DIR, Path(fr).stem)
                sz = (BASE / comp).stat().st_size if comp else 0
                prepared.append(make_prepared_entry("frame", "post_video_frame", url_field, dl_path, comp, sz, cerr))
            if not frames:
                prepared.append(make_prepared_entry("frame", "post_video_frame", url_field, dl_path, None, 0, ferr or "no frames"))
        else:
            comp, cerr = compress_image(BASE / dl_path, POSTS_OAI_DIR, f"{safe_stem(pid)}_{source_type}")
            sz = (BASE / comp).stat().st_size if comp else 0
            if cerr:
                post_errors.append(f"compress: {cerr}")
            prepared.append(make_prepared_entry("image", source_type, url_field, dl_path, comp, sz, cerr))

    ok_inputs = [p for p in prepared if p["prepared_path"]]
    if len(ok_inputs) >= sources_found and sources_found > 0:
        pstatus = "OK"
    elif ok_inputs:
        pstatus = "PARTIAL"
    else:
        pstatus = "FAIL"

    posts_manifest.append({
        "content_id": pid,
        "shortcode": post.get("shortCode") or post.get("shortcode") or pid,
        "url": purl, "type": ptype, "caption": pcap, "timestamp": pts,
        "raw_media_sources_found": sources_found,
        "prepared_inputs": prepared,
        "status": pstatus, "errors": post_errors,
    })
    print(f"  post {pid}: sources={sources_found} | prepared={len(ok_inputs)} | status={pstatus}")

# ── B. Highlight stories ──────────────────────────────────────────────────────
stories_manifest = []
print(f"\nProcessing {min(len(stories_data), MAX_STORIES)} highlight stories...")

for i, story in enumerate(stories_data[:MAX_STORIES]):
    sid      = item_id(story, "storyId", "story_id", "id")
    stype    = story.get("storyType") or story.get("type") or "unknown"
    taken_at = story.get("takenAt") or story.get("timestamp") or story.get("publishDate") or None
    prepared  = []
    st_errors = []

    img_field, img_url = get_field(story, "imageUrl", "image_url", "displayUrl")
    vid_field, vid_url = get_field(story, "videoUrl", "video_url", "videoSrc")

    # Prefer video; fall back to image
    primary = ("video", vid_field, vid_url) if vid_url else ("image", img_field, img_url)
    p_kind, p_field, p_url = primary

    if not p_url:
        st_errors.append("no imageUrl or videoUrl found")
        all_errors.append({"story_id": sid, "story_number": i + 1, "error": "no media URL"})
        stories_manifest.append({
            "story_id": sid, "story_number": i + 1, "story_type": stype, "takenAt": taken_at,
            "prepared_inputs": [], "status": "FAIL", "errors": st_errors,
        })
        continue

    ext  = ".mp4" if p_kind == "video" else ".jpg"
    dest = HL_DL_DIR / f"story_{safe_stem(sid)}{ext}"
    dl_path, dl_err = download(p_url, dest)

    if dl_err and dl_path is None:
        # try image fallback for video stories
        if p_kind == "video" and img_url:
            dest2 = HL_DL_DIR / f"story_{safe_stem(sid)}_img.jpg"
            dl_path, dl_err2 = download(img_url, dest2)
            if dl_path:
                p_kind, p_field = "image", img_field
                dl_err = None
            else:
                st_errors.append(f"video dl failed: {dl_err} | image fallback failed: {dl_err2}")
        if dl_path is None:
            st_errors.append(f"download failed: {dl_err}")
            all_errors.append({"story_id": sid, "story_number": i + 1, "error": dl_err})
            prepared.append(make_prepared_entry(p_kind, f"story_{p_kind}", p_field, None, None, 0, dl_err))
            stories_manifest.append({
                "story_id": sid, "story_number": i + 1, "story_type": stype, "takenAt": taken_at,
                "prepared_inputs": prepared, "status": "FAIL", "errors": st_errors,
            })
            continue

    if p_kind == "video":
        frames, ferr = extract_frames(BASE / dl_path, f"story_{safe_stem(sid)}")
        if ferr:
            st_errors.append(f"frame extraction: {ferr}")
        for fr in frames:
            comp, cerr = compress_image(BASE / fr, HL_OAI_DIR, Path(fr).stem)
            sz = (BASE / comp).stat().st_size if comp else 0
            prepared.append(make_prepared_entry("frame", "story_video_frame", p_field, dl_path, comp, sz, cerr))
        if not frames:
            # image fallback if video has no frames
            if img_url and img_url != p_url:
                dest3 = HL_DL_DIR / f"story_{safe_stem(sid)}_img_fallback.jpg"
                dl3, err3 = download(img_url, dest3)
                if dl3:
                    comp, cerr = compress_image(BASE / dl3, HL_OAI_DIR, f"story_{safe_stem(sid)}_img")
                    sz = (BASE / comp).stat().st_size if comp else 0
                    prepared.append(make_prepared_entry("image", "story_image", img_field, dl3, comp, sz, cerr))
                else:
                    prepared.append(make_prepared_entry("frame", "story_video_frame", p_field, dl_path, None, 0, ferr or "no frames"))
            else:
                prepared.append(make_prepared_entry("frame", "story_video_frame", p_field, dl_path, None, 0, ferr or "no frames"))
    else:
        comp, cerr = compress_image(BASE / dl_path, HL_OAI_DIR, f"story_{safe_stem(sid)}_image")
        sz = (BASE / comp).stat().st_size if comp else 0
        if cerr:
            st_errors.append(f"compress: {cerr}")
        prepared.append(make_prepared_entry("image", "story_image", p_field, dl_path, comp, sz, cerr))

    ok_inputs = [p for p in prepared if p["prepared_path"]]
    if ok_inputs:
        sstatus = "OK" if not st_errors else "PARTIAL"
    else:
        sstatus = "FAIL"

    stories_manifest.append({
        "story_id": sid, "story_number": i + 1, "story_type": stype, "takenAt": taken_at,
        "prepared_inputs": prepared, "status": sstatus, "errors": st_errors,
    })
    if (i + 1) % 10 == 0 or i == 0:
        print(f"  stories processed: {i + 1}/{min(len(stories_data), MAX_STORIES)}")

# ── Summary ───────────────────────────────────────────────────────────────────
def count_status(items, s): return sum(1 for x in items if x["status"] == s)

p_ok = count_status(posts_manifest, "OK")
p_pa = count_status(posts_manifest, "PARTIAL")
p_fa = count_status(posts_manifest, "FAIL")
s_ok = count_status(stories_manifest, "OK")
s_pa = count_status(stories_manifest, "PARTIAL")
s_fa = count_status(stories_manifest, "FAIL")

all_prepared = [
    inp for p in posts_manifest for inp in p["prepared_inputs"] if inp.get("prepared_path")
] + [
    inp for s in stories_manifest for inp in s["prepared_inputs"] if inp.get("prepared_path")
]
imgs   = sum(1 for x in all_prepared if x["input_type"] == "image")
frames = sum(1 for x in all_prepared if x["input_type"] == "frame")

if p_fa == 0 and s_fa == 0:
    overall = "OK"
elif len(all_prepared) > 0:
    overall = "PARTIAL"
else:
    overall = "FAIL"

manifest = {
    "account": "vlada_kliuiko",
    "posts": posts_manifest,
    "highlight": {
        "highlight_id": HIGHLIGHT_ID,
        "stories_total": len(stories_data),
        "stories": stories_manifest,
    },
    "summary": {
        "posts_total": len(posts_manifest),
        "posts_ok": p_ok, "posts_partial": p_pa, "posts_fail": p_fa,
        "stories_total": len(stories_manifest),
        "stories_ok": s_ok, "stories_partial": s_pa, "stories_fail": s_fa,
        "prepared_images_total": imgs,
        "prepared_frames_total": frames,
        "errors_total": len(all_errors),
        "status": overall,
    },
}

MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
MANIFEST_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
ERRORS_OUT.write_text(json.dumps(all_errors, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nSummary: posts OK={p_ok} PARTIAL={p_pa} FAIL={p_fa} | "
      f"stories OK={s_ok} PARTIAL={s_pa} FAIL={s_fa} | "
      f"images={imgs} frames={frames} | overall={overall}")
print(f"manifest: {MANIFEST_OUT.relative_to(BASE)}")
print(f"errors:   {ERRORS_OUT.relative_to(BASE)}")
