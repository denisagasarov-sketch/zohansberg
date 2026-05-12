import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from apify_client import ApifyClient
from dotenv import load_dotenv

BASE = Path(__file__).parent.parent
load_dotenv(BASE / ".env")

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
if not APIFY_TOKEN:
    raise SystemExit("APIFY_TOKEN missing in .env — aborting")

client = ApifyClient(APIFY_TOKEN)

for d in ["data/raw", "data/normalized", "report", "scripts"]:
    (BASE / d).mkdir(parents=True, exist_ok=True)

payloads_path = BASE / "data" / "actor_payloads.json"
payloads = json.loads(payloads_path.read_text())

if not payloads.get("stage_2_allowed"):
    raise SystemExit("stage_2_allowed is not true in actor_payloads.json — aborting")

errors = []

def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean_highlight_id(raw_id):
    if not raw_id:
        return None
    cleaned = re.sub(r"^highlight:", "", str(raw_id))
    return cleaned if re.fullmatch(r"\d{17}", cleaned) else None

def run_actor(actor_id, payload, label):
    safe_payload = {k: v for k, v in payload.items() if k not in ("token",)}
    print(f"\n{'='*60}")
    print(f"actor id: {actor_id}")
    print(f"input payload:\n{json.dumps(safe_payload, indent=2)}")
    print(f"Running this actor once")
    print('='*60)
    try:
        run = client.actor(actor_id).call(run_input=payload)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        return items, None
    except Exception as e:
        err = str(e)
        errors.append({
            "step": label,
            "actor_id": actor_id,
            "error": err,
            "timestamp": now_iso(),
            "input_used_without_secrets": safe_payload,
        })
        print(f"[ERROR] {label}: {err}")
        return None, err


# ── A. Posts dataset test ─────────────────────────────────────────────────────

print("\n>>> A. Posts dataset test")

posts_cfg = payloads["actors"]["posts_reels"]
posts_actor = posts_cfg["actor_id"]
posts_input = posts_cfg["test_input"]

posts_items, posts_err = run_actor(posts_actor, posts_input, "posts")

save_json(BASE / "data/raw/posts_test_raw.json", posts_items if posts_items is not None else [])

sample_post = posts_items[0] if posts_items else None
save_json(BASE / "data/raw/sample_post_item.json", sample_post)

def check_field(item, *keys):
    if not item:
        return False
    return any(k in item for k in keys)

if posts_items is not None and len(posts_items) > 0:
    sample = posts_items[0]
    fields = list(sample.keys())
    has_url = check_field(sample, "url", "shortCode", "shortcode", "link", "postUrl")
    has_cap = check_field(sample, "caption", "text", "description")
    has_vis = check_field(sample, "displayUrl", "imageUrl", "thumbnailUrl", "videoUrl",
                          "media_url", "display_url", "thumbnail")
    has_ts  = check_field(sample, "timestamp", "date", "takenAt", "taken_at", "createdAt",
                          "postedAt", "time")
    has_lk  = check_field(sample, "likesCount", "likes", "like_count", "likeCount")
    has_cm  = check_field(sample, "commentsCount", "comments", "comment_count", "commentCount")
    has_vw  = check_field(sample, "videoViewCount", "views", "view_count", "viewCount",
                          "playCount", "videoPlayCount")
    has_vid = check_field(sample, "videoUrl", "video_url", "videoSrc")
    has_car = check_field(sample, "images", "carouselMedia", "carousel_media", "sidecarChildren",
                          "childPosts")
    has_rl  = check_field(sample, "isReel", "reel", "type") or any(
                  "reel" in str(v).lower() for v in sample.values()
              )

    if has_url and (has_cap or has_vis):
        post_status = "OK"
    elif len(posts_items) > 0:
        post_status = "PARTIAL"
    else:
        post_status = "FAIL"
else:
    fields = []
    has_url = has_cap = has_vis = has_ts = has_lk = has_cm = has_vw = has_vid = has_car = has_rl = False
    post_status = "FAIL"

posts_inventory = {
    "status": post_status,
    "actor_id": posts_actor,
    "items_count": len(posts_items) if posts_items else 0,
    "dataset_type": "array" if isinstance(posts_items, list) else "unknown",
    "sample_item_fields": fields,
    "has_caption": has_cap,
    "has_timestamp_or_date": has_ts,
    "has_url_or_shortcode": has_url,
    "has_likes": has_lk,
    "has_comments": has_cm,
    "has_views": has_vw,
    "has_any_visual_source": has_vis,
    "has_media_url_like_field": has_vis,
    "has_video_url_like_field": has_vid,
    "has_carousel_like_field": has_car,
    "has_reel_like_field": has_rl,
    "raw_path": "data/raw/posts_test_raw.json",
    "sample_path": "data/raw/sample_post_item.json",
    "errors": [posts_err] if posts_err else [],
}
save_json(BASE / "data/normalized/posts_field_inventory.json", posts_inventory)
print(f"Posts status: {post_status} | items: {posts_inventory['items_count']}")


# ── B. Highlights index test ──────────────────────────────────────────────────

print("\n>>> B. Highlights index test")

hl_cfg = payloads["actors"]["highlights_index"]
hl_actor = hl_cfg["actor_id"]
hl_input = hl_cfg["test_input"]

hl_items, hl_err = run_actor(hl_actor, hl_input, "highlights_index")

save_json(BASE / "data/raw/highlights_index_test_raw.json", hl_items if hl_items is not None else [])

# find best sample item (prefer one with an id field)
sample_hl = None
if hl_items:
    for item in hl_items:
        if "id" in item:
            sample_hl = item
            break
    if sample_hl is None:
        sample_hl = hl_items[0]
save_json(BASE / "data/raw/sample_highlight_item.json", sample_hl)

raw_hl_id = None
clean_hl_id = None
clean_valid = False

if sample_hl:
    raw_hl_id = sample_hl.get("id")
    clean_hl_id = clean_highlight_id(raw_hl_id)
    clean_valid = clean_hl_id is not None

if hl_items is not None and len(hl_items) > 0:
    hl_fields = list(hl_items[0].keys())
    hl_has_title   = any("title" in item for item in hl_items)
    hl_has_id      = any("id" in item for item in hl_items)
    hl_has_cover   = any(k in hl_items[0] for k in ("cover_media", "coverMedia", "cover",
                                                      "coverImage", "cover_image"))
    hl_has_uname   = any("username" in item for item in hl_items)
    hl_has_uid     = any(k in hl_items[0] for k in ("user_id", "userId", "ownerId"))

    if len(hl_items) > 0 and hl_has_id and clean_valid:
        hl_status = "OK"
    elif len(hl_items) > 0:
        hl_status = "PARTIAL"
    else:
        hl_status = "FAIL"
else:
    hl_fields = []
    hl_has_title = hl_has_id = hl_has_cover = hl_has_uname = hl_has_uid = False
    hl_status = "FAIL"

hl_summary = {
    "status": hl_status,
    "actor_id": hl_actor,
    "highlights_count": len(hl_items) if hl_items else 0,
    "dataset_type": "array" if isinstance(hl_items, list) else "unknown",
    "sample_item_fields": hl_fields,
    "has_title": hl_has_title,
    "has_highlight_id": hl_has_id,
    "highlight_id_original": raw_hl_id,
    "clean_highlight_id": clean_hl_id,
    "clean_highlight_id_valid": clean_valid,
    "has_cover_media": hl_has_cover,
    "has_username": hl_has_uname,
    "has_user_id": hl_has_uid,
    "raw_path": "data/raw/highlights_index_test_raw.json",
    "sample_path": "data/raw/sample_highlight_item.json",
    "errors": [hl_err] if hl_err else [],
}
save_json(BASE / "data/normalized/highlights_index_summary.json", hl_summary)
print(f"Highlights status: {hl_status} | count: {hl_summary['highlights_count']} | "
      f"clean_id: {clean_hl_id} | valid: {clean_valid}")


# ── C. Highlight stories test ─────────────────────────────────────────────────

print("\n>>> C. Highlight stories test")

stories_cfg = payloads["actors"]["highlight_stories"]
stories_actor = stories_cfg["actor_id"]

if not clean_valid:
    print("Skipping highlight stories — no valid clean_highlight_id")
    stories_summary = {
        "status": "SKIPPED",
        "actor_id": stories_actor,
        "highlight_id_tested": None,
        "stories_count": 0,
        "dataset_type": "empty",
        "sample_item_fields": [],
        "has_storyNumber": False,
        "has_storyId": False,
        "has_storyType": False,
        "has_imageUrl": False,
        "has_videoUrl": False,
        "has_any_media_url": False,
        "has_takenAt": False,
        "has_duration": False,
        "has_rawStoryData": False,
        "raw_path": "data/raw/highlight_stories_test_raw.json",
        "sample_path": "data/raw/sample_story_item.json",
        "skip_reason": "No valid clean_highlight_id from highlights index",
        "errors": [],
    }
    save_json(BASE / "data/raw/highlight_stories_test_raw.json", [])
    save_json(BASE / "data/raw/sample_story_item.json", None)
else:
    stories_input = {"highlightId": clean_hl_id}
    st_items, st_err = run_actor(stories_actor, stories_input, "highlight_stories")

    save_json(BASE / "data/raw/highlight_stories_test_raw.json",
              st_items if st_items is not None else [])

    sample_st = st_items[0] if st_items else None
    save_json(BASE / "data/raw/sample_story_item.json", sample_st)

    if st_items and len(st_items) > 0:
        st_fields = list(st_items[0].keys())
        has_sn  = check_field(st_items[0], "storyNumber")
        has_sid = check_field(st_items[0], "storyId", "story_id", "id")
        has_stp = check_field(st_items[0], "storyType", "story_type", "type", "mediaType")
        has_img = check_field(st_items[0], "imageUrl", "image_url", "displayUrl")
        has_vid = check_field(st_items[0], "videoUrl", "video_url", "videoSrc")
        has_any_media = has_img or has_vid
        has_ta  = check_field(st_items[0], "takenAt", "taken_at", "timestamp", "publishDate")
        has_dur = check_field(st_items[0], "duration")
        has_raw = check_field(st_items[0], "rawStoryData", "raw_story_data")

        if len(st_items) > 0 and has_any_media:
            st_status = "OK"
        elif len(st_items) > 0:
            st_status = "PARTIAL"
        else:
            st_status = "FAIL"
    else:
        st_fields = []
        has_sn = has_sid = has_stp = has_img = has_vid = has_any_media = False
        has_ta = has_dur = has_raw = False
        st_status = "FAIL"

    stories_summary = {
        "status": st_status,
        "actor_id": stories_actor,
        "highlight_id_tested": clean_hl_id,
        "stories_count": len(st_items) if st_items else 0,
        "dataset_type": "array" if isinstance(st_items, list) else "unknown",
        "sample_item_fields": st_fields,
        "has_storyNumber": has_sn,
        "has_storyId": has_sid,
        "has_storyType": has_stp,
        "has_imageUrl": has_img,
        "has_videoUrl": has_vid,
        "has_any_media_url": has_any_media,
        "has_takenAt": has_ta,
        "has_duration": has_dur,
        "has_rawStoryData": has_raw,
        "raw_path": "data/raw/highlight_stories_test_raw.json",
        "sample_path": "data/raw/sample_story_item.json",
        "skip_reason": None,
        "errors": [st_err] if st_err else [],
    }

    print(f"Stories status: {st_status} | count: {stories_summary['stories_count']}")

save_json(BASE / "data/normalized/highlight_stories_summary.json", stories_summary)


# ── D. Error log ──────────────────────────────────────────────────────────────

save_json(BASE / "data/raw/errors_test.json", errors)


# ── E. Report ─────────────────────────────────────────────────────────────────

def yesno(v):
    return "yes" if v else "no"

# final verdict
p_ok  = posts_inventory["status"]
h_ok  = hl_summary["status"]
s_ok  = stories_summary["status"]

if p_ok == "OK" and h_ok == "OK" and s_ok == "OK":
    verdict = "OK — можно переходить к Stage 3: media download + OpenAI-анализ"
elif p_ok in ("OK", "PARTIAL") and (h_ok != "OK" or s_ok not in ("OK", "SKIPPED")):
    verdict = "PARTIAL — часть данных доступна, но есть ограничения"
elif p_ok == "FAIL":
    verdict = "FAIL — нужно менять actor или способ сбора"
else:
    verdict = "PARTIAL — часть данных доступна, но есть ограничения"

posts_errors_str  = ", ".join(posts_inventory["errors"]) or "none"
hl_errors_str     = ", ".join(str(e) for e in hl_summary["errors"]) or "none"
st_errors_str     = ", ".join(str(e) for e in stories_summary["errors"]) or "none"

report = f"""# Instagram scraping test report

## Scope

Stage 2 checks only:
- posts dataset raw output
- highlights index raw output
- highlight stories raw output

Stage 2 does NOT check:
- bio
- profile link
- pinned posts
- website
- bot funnel
- content quality
- marketing strategy
- OpenAI analysis
- media download

## Test account

https://www.instagram.com/vlada_kliuiko/

## Posts dataset actor

- actor id: {posts_actor}
- status: {p_ok}
- items returned: {posts_inventory['items_count']}
- sample item path: {posts_inventory['sample_path']}
- raw path: {posts_inventory['raw_path']}
- field inventory path: data/normalized/posts_field_inventory.json
- key fields available: caption={yesno(has_cap)}, url/shortcode={yesno(has_url)}, timestamp={yesno(has_ts)}, likes={yesno(has_lk)}, comments={yesno(has_cm)}, views={yesno(has_vw)}, visual={yesno(has_vis)}, video_url={yesno(has_vid)}, carousel={yesno(has_car)}, reel={yesno(has_rl)}
- errors: {posts_errors_str}

## Highlights index actor

- actor id: {hl_actor}
- status: {h_ok}
- highlights returned: {hl_summary['highlights_count']}
- clean highlight id available: {yesno(hl_summary['has_highlight_id'])}
- clean highlight id valid: {yesno(hl_summary['clean_highlight_id_valid'])}
- clean highlight id value: {hl_summary['clean_highlight_id'] or 'n/a'}
- sample item path: {hl_summary['sample_path']}
- raw path: {hl_summary['raw_path']}
- summary path: data/normalized/highlights_index_summary.json
- errors: {hl_errors_str}

## Highlight stories actor

- actor id: {stories_actor}
- status: {s_ok}
- highlight id tested: {stories_summary['highlight_id_tested'] or 'n/a'}
- stories returned: {stories_summary['stories_count']}
- imageUrl available: {yesno(stories_summary['has_imageUrl'])}
- videoUrl available: {yesno(stories_summary['has_videoUrl'])}
- any media URL available: {yesno(stories_summary['has_any_media_url'])}
- sample item path: {stories_summary['sample_path']}
- raw path: {stories_summary['raw_path']}
- summary path: data/normalized/highlight_stories_summary.json
- errors: {st_errors_str}

## Final verdict

{verdict}

## Recommendation

"""

# Build recommendation
recs = []
if p_ok == "OK":
    recs.append("- Масштабирование на 20 публикаций: возможно — изменить `resultsLimit` в actor_payloads.json.")
elif p_ok == "PARTIAL":
    recs.append("- Масштабирование на 20 публикаций: осторожно — posts actor вернул PARTIAL, проверь sample_post_item.json.")
else:
    recs.append("- Масштабирование на 20 публикаций: нет — posts actor вернул FAIL, нужно устранить причину.")

if p_ok in ("OK", "PARTIAL"):
    recs.append("- Масштабирование на все аккаунты: возможно — добавить URL в accounts.json, запускать по одному.")
else:
    recs.append("- Масштабирование на все аккаунты: нет — сначала исправить posts actor.")

if h_ok == "OK" and s_ok == "OK":
    recs.append("- Анализ highlights внутри: возможно — highlights index и stories оба вернули OK.")
elif h_ok in ("OK", "PARTIAL") and s_ok in ("OK", "PARTIAL"):
    recs.append("- Анализ highlights внутри: частично — проверь highlights_index_summary.json и highlight_stories_summary.json.")
elif s_ok == "SKIPPED":
    recs.append("- Анализ highlights внутри: не проверялось — clean_highlight_id не был получен.")
else:
    recs.append("- Анализ highlights внутри: нет — нужно исправить highlights actor.")

if p_ok == "OK" and h_ok == "OK" and s_ok == "OK":
    recs.append("- Перед Stage 3: всё готово. Можно добавить media download и подключить OpenAI API.")
else:
    issues = []
    if p_ok != "OK":
        issues.append(f"posts={p_ok}")
    if h_ok != "OK":
        issues.append(f"highlights_index={h_ok}")
    if s_ok not in ("OK", "SKIPPED"):
        issues.append(f"highlight_stories={s_ok}")
    recs.append(f"- Перед Stage 3: исправить — {', '.join(issues)}. Проверь error log: data/raw/errors_test.json.")

report += "\n".join(recs) + "\n"

report_path = BASE / "report/scraping_test_report.md"
report_path.write_text(report)

print(f"\n{'='*60}")
print(f"Report saved: report/scraping_test_report.md")
print(f"Final verdict: {verdict}")
print(f"Posts: {p_ok} | {posts_inventory['items_count']} items")
print(f"Highlights: {h_ok} | {hl_summary['highlights_count']} items | clean_id valid: {clean_valid}")
print(f"Stories: {s_ok} | {stories_summary['stories_count']} items | "
      f"any_media: {yesno(stories_summary['has_any_media_url'])}")
print('='*60)
