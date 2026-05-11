import json
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent

# ── Paths ─────────────────────────────────────────────────────────────────────
POSTS_RAW      = BASE / "data/raw/posts_test_raw.json"
STORIES_RAW    = BASE / "data/raw/highlight_stories_manual_test_raw.json"
MANIFEST_PATH  = BASE / "data/normalized/stage3a_media_manifest.json"
PREVIEW_PATH   = BASE / "data/normalized/stage3b1_openai_input_preview.json"
REPORT_PATH    = BASE / "report/stage_3b1_openai_input_preview.md"

FRAMES_DIR = BASE / "output/openai_inputs/stage3b1/frames"
IMAGES_DIR = BASE / "output/openai_inputs/stage3b1/images"
for d in (FRAMES_DIR, IMAGES_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_POSTS           = 1
MAX_HIGHLIGHT_STORIES = 5
MAX_FRAMES_PER_VIDEO  = 5
MAX_TOTAL_IMAGES      = 10

HIGHLIGHT_ID = "17874797856565339"

errors   = []
warnings = []

# ── A. Validate inputs ────────────────────────────────────────────────────────
def require_file(p, label):
    if not p.exists():
        raise SystemExit(f"MISSING: {label} at {p}")
    if p.stat().st_size <= 2:
        raise SystemExit(f"EMPTY: {label} at {p} — re-run Stage 2 locally")

require_file(POSTS_RAW,   "posts_test_raw.json")
require_file(STORIES_RAW, "highlight_stories_manual_test_raw.json")
require_file(MANIFEST_PATH, "stage3a_media_manifest.json")

posts_data   = json.loads(POSTS_RAW.read_text())
stories_data = json.loads(STORIES_RAW.read_text())
manifest     = json.loads(MANIFEST_PATH.read_text())

dl_posts  = [m for m in manifest.get("post_media", [])      if m.get("downloaded")]
dl_hl     = [m for m in manifest.get("highlight_media", []) if m.get("downloaded")]

if not dl_posts:
    raise SystemExit("No downloaded post media in stage3a manifest — re-run Stage 3A locally")
if not dl_hl:
    raise SystemExit("No downloaded highlight media in stage3a manifest — re-run Stage 3A locally")

print(f"posts raw: {len(posts_data)} items")
print(f"stories raw: {len(stories_data)} items")
print(f"downloaded post media: {len(dl_posts)}")
print(f"downloaded highlight media: {len(dl_hl)}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def compress_image(src_path, dest_dir, stem):
    try:
        from PIL import Image
        img = Image.open(src_path).convert("RGB")
        w, h = img.size
        if w > 1280:
            h = int(h * 1280 / w)
            w = 1280
            img = img.resize((w, h))
        dest = dest_dir / f"{stem}.jpg"
        img.save(dest, "JPEG", quality=85)
        return str(dest.relative_to(BASE)), None
    except Exception as e:
        return None, str(e)

def extract_frames(video_path, dest_dir, stem, max_frames=5):
    frames = []
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 30
        if total <= 0:
            cap.release()
            return frames, "could not read frame count"
        # spread frames evenly
        indices = [int(i * total / max_frames) for i in range(max_frames)]
        indices = sorted(set(min(i, total - 1) for i in indices))
        for idx in indices[:max_frames]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            sec = round(idx / fps, 1)
            frame_dest = dest_dir / f"{stem}_f{idx}_t{sec}s.jpg"
            cv2.imwrite(str(frame_dest), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            # resize if needed
            h, w = frame.shape[:2]
            if w > 1280:
                new_w, new_h = 1280, int(h * 1280 / w)
                import cv2 as _cv2
                frame_resized = _cv2.resize(frame, (new_w, new_h))
                _cv2.imwrite(str(frame_dest), frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frames.append(str(frame_dest.relative_to(BASE)))
        cap.release()
        return frames, None
    except ImportError:
        return [], "opencv-python not installed"
    except Exception as e:
        return [], str(e)

# ── B. Select test post ───────────────────────────────────────────────────────
# prefer post whose content_id appears in manifest
manifest_ids = {m.get("content_id") for m in dl_posts}

def post_id(p):
    for k in ("shortCode", "shortcode", "id"):
        if k in p:
            return str(p[k])
    return None

selected_post = None
for p in posts_data:
    if post_id(p) in manifest_ids:
        selected_post = p
        break
if selected_post is None:
    selected_post = posts_data[0]

pid   = post_id(selected_post) or "unknown"
purl  = selected_post.get("url") or selected_post.get("postUrl") or f"https://www.instagram.com/p/{pid}/"
ptype = selected_post.get("type") or selected_post.get("productType") or "unknown"
pcap  = selected_post.get("caption") or selected_post.get("text") or None
pts   = selected_post.get("timestamp") or selected_post.get("date") or selected_post.get("takenAt") or None

# find matching manifest entries for this post
post_manifest_entries = [m for m in dl_posts if m.get("content_id") == pid]
if not post_manifest_entries:
    post_manifest_entries = dl_posts[:1]   # fallback to first downloaded

post_media_prepared = []
image_files_total   = 0

for entry in post_manifest_entries:
    orig = BASE / entry["local_path"]
    mtype = entry.get("media_type", "unknown")

    if mtype == "video" and orig.exists():
        frs, err = extract_frames(orig, FRAMES_DIR, f"post_{pid}", MAX_FRAMES_PER_VIDEO)
        if err:
            warnings.append(f"post video frame extraction: {err}")
        for fr in frs:
            if image_files_total >= MAX_TOTAL_IMAGES:
                warnings.append("MAX_TOTAL_IMAGES reached — truncating post frames")
                break
            comp, cerr = compress_image(BASE / fr, IMAGES_DIR, Path(fr).stem)
            post_media_prepared.append({
                "media_type": "frame",
                "source": "post",
                "original_path": entry["local_path"],
                "prepared_path": comp,
                "used_for_openai_preview": comp is not None,
                "error": cerr,
            })
            if comp:
                image_files_total += 1

    elif mtype == "image" and orig.exists():
        comp, cerr = compress_image(orig, IMAGES_DIR, f"post_{pid}_image")
        post_media_prepared.append({
            "media_type": "image",
            "source": "post",
            "original_path": entry["local_path"],
            "prepared_path": comp,
            "used_for_openai_preview": comp is not None,
            "error": cerr,
        })
        if comp:
            image_files_total += 1

print(f"post selected: {pid} | media prepared: {len(post_media_prepared)}")

# ── C/D/E. Select highlight stories ──────────────────────────────────────────
stories_total = len(stories_data)

# pick up to MAX_HIGHLIGHT_STORIES from downloaded highlight media
selected_stories_raw = stories_data[:MAX_HIGHLIGHT_STORIES]

# also use downloaded media files from manifest (up to limit)
hl_entries = dl_hl[:MAX_HIGHLIGHT_STORIES]

def story_id(s):
    for k in ("storyId", "story_id", "id"):
        if k in s:
            return str(s[k])
    return None

highlight_stories_prepared = []

for i, entry in enumerate(hl_entries):
    if image_files_total >= MAX_TOTAL_IMAGES:
        warnings.append("MAX_TOTAL_IMAGES reached — truncating highlight stories")
        break

    orig  = BASE / entry["local_path"]
    mtype = entry.get("media_type", "unknown")
    sid   = story_id(selected_stories_raw[i]) if i < len(selected_stories_raw) else f"story_{i}"
    stype = selected_stories_raw[i].get("storyType") or selected_stories_raw[i].get("type") if i < len(selected_stories_raw) else "unknown"

    if mtype == "video" and orig.exists():
        frs, err = extract_frames(orig, FRAMES_DIR, f"hl_{sid}", MAX_FRAMES_PER_VIDEO)
        if err:
            warnings.append(f"highlight video frame extraction (story {sid}): {err}")
        for fr in frs:
            if image_files_total >= MAX_TOTAL_IMAGES:
                warnings.append("MAX_TOTAL_IMAGES reached — truncating highlight frames")
                break
            comp, cerr = compress_image(BASE / fr, IMAGES_DIR, Path(fr).stem)
            highlight_stories_prepared.append({
                "story_id": sid,
                "story_number": i + 1,
                "story_type": stype,
                "media_type": "frame",
                "original_path": entry["local_path"],
                "prepared_path": comp,
                "used_for_openai_preview": comp is not None,
                "error": cerr,
            })
            if comp:
                image_files_total += 1

    elif mtype == "image" and orig.exists():
        comp, cerr = compress_image(orig, IMAGES_DIR, f"hl_{sid}_image")
        highlight_stories_prepared.append({
            "story_id": sid,
            "story_number": i + 1,
            "story_type": stype,
            "media_type": "image",
            "original_path": entry["local_path"],
            "prepared_path": comp,
            "used_for_openai_preview": comp is not None,
            "error": cerr,
        })
        if comp:
            image_files_total += 1

print(f"highlight stories prepared: {len(highlight_stories_prepared)} | images total: {image_files_total}")

# ── F/G. Readiness + preview JSON ────────────────────────────────────────────
post_ready = any(m["used_for_openai_preview"] for m in post_media_prepared)
hl_ready   = any(m["used_for_openai_preview"] for m in highlight_stories_prepared)

if not post_ready:
    errors.append("No usable post media prepared — check compression/frame extraction")
if not hl_ready:
    errors.append("No usable highlight media prepared — check compression/frame extraction")

preview = {
    "stage": "stage3b1_openai_input_preview",
    "openai_call_allowed": False,
    "account": "vlada_kliuiko",
    "post_sample": {
        "content_id": pid,
        "shortcode": selected_post.get("shortCode") or selected_post.get("shortcode") or pid,
        "url": purl,
        "type": ptype,
        "caption": pcap,
        "timestamp": pts,
        "fields_used": [k for k in ("shortCode","url","type","caption","timestamp","displayUrl","videoUrl") if k in selected_post],
        "selected_media": post_media_prepared,
    },
    "highlight_sample": {
        "highlight_id": HIGHLIGHT_ID,
        "analysis_scope": "sample_only",
        "not_full_highlight_analysis": True,
        "stories_total_in_raw": stories_total,
        "stories_selected_count": len(hl_entries),
        "selected_stories": highlight_stories_prepared,
    },
    "limits_applied": {
        "max_posts": MAX_POSTS,
        "max_highlight_stories": MAX_HIGHLIGHT_STORIES,
        "max_frames_per_video": MAX_FRAMES_PER_VIDEO,
        "max_total_images": MAX_TOTAL_IMAGES,
        "images_sent_count_planned": image_files_total,
    },
    "readiness": {
        "can_run_stage3b2_openai_call": post_ready and hl_ready and not errors,
        "post_ready": post_ready,
        "highlight_ready": hl_ready,
        "errors": errors,
        "warnings": warnings,
    },
}
PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
PREVIEW_PATH.write_text(json.dumps(preview, ensure_ascii=False, indent=2))
print(f"preview JSON saved: {PREVIEW_PATH.relative_to(BASE)}")

# ── H. Markdown report ────────────────────────────────────────────────────────
def yesno(v): return "yes" if v else "no"

post_media_str = ", ".join(
    f"{m['media_type']} ({Path(m['prepared_path']).name if m['prepared_path'] else 'failed'})"
    for m in post_media_prepared
) or "none"
post_frames = sum(1 for m in post_media_prepared if m["media_type"] == "frame")
post_images = sum(1 for m in post_media_prepared if m["media_type"] == "image")

hl_media_str = ", ".join(
    f"story {m['story_number']} {m['media_type']}"
    for m in highlight_stories_prepared
) or "none"
hl_frames = sum(1 for m in highlight_stories_prepared if m["media_type"] == "frame")
hl_images = sum(1 for m in highlight_stories_prepared if m["media_type"] == "image")

blockers_str = "\n".join(f"  - {e}" for e in errors) or "  none"
warnings_str = "\n".join(f"  - {w}" for w in warnings) or "  none"

report_md = f"""# Stage 3B-1 OpenAI Input Preview

## Scope

Stage 3B-1 только готовит input для OpenAI.
OpenAI API на этом этапе НЕ вызывается.

## Post sample

- content id: {pid}
- shortcode: {selected_post.get("shortCode") or selected_post.get("shortcode") or pid}
- url: {purl}
- caption found: {yesno(bool(pcap))}
- media selected: {post_media_str}
- frames extracted: {post_frames}
- prepared files: {len(post_media_prepared)} (images: {post_images}, frames: {post_frames})

## Highlight sample

- highlight id: {HIGHLIGHT_ID}
- stories total in raw: {stories_total}
- stories selected: {len(hl_entries)}
- scope: sample only
- not full highlight analysis: true
- media selected: {hl_media_str}
- frames extracted: {hl_frames}
- prepared files: {len(highlight_stories_prepared)} (images: {hl_images}, frames: {hl_frames})

## Limits

- max posts: {MAX_POSTS}
- max highlight stories: {MAX_HIGHLIGHT_STORIES}
- max frames per video: {MAX_FRAMES_PER_VIDEO}
- max total images: {MAX_TOTAL_IMAGES}
- planned image count: {image_files_total}

## Readiness for Stage 3B-2

- post ready: {yesno(post_ready)}
- highlight ready: {yesno(hl_ready)}
- can run OpenAI call: {yesno(preview["readiness"]["can_run_stage3b2_openai_call"])}
- blockers:
{blockers_str}
- warnings:
{warnings_str}

## Next step

{"Stage 3B-2 can call OpenAI on prepared files only." if preview["readiness"]["can_run_stage3b2_openai_call"] else "Fix blockers above before proceeding to Stage 3B-2."}
"""

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(report_md)
print(f"report saved: {REPORT_PATH.relative_to(BASE)}")
print(f"can_run_stage3b2: {preview['readiness']['can_run_stage3b2_openai_call']}")
