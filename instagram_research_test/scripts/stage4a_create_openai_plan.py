import json
from pathlib import Path

BASE = Path(__file__).parent.parent

MANIFEST_PATH = BASE / "data/normalized/stage4a_media_manifest.json"
PLAN_PATH     = BASE / "data/normalized/stage4a_openai_plan.json"

BATCH_SIZE           = 8
MAX_TOTAL_REQUESTS   = 15
MAX_IMAGES_PER_REQ   = 10
MAX_PAYLOAD_MB       = 20
MAX_TOTAL_INPUTS     = 120

if not MANIFEST_PATH.exists():
    raise SystemExit("stage4a_media_manifest.json not found — run stage4a_prepare_media.py first")

manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
plan_errors = []

def est_bytes(paths):
    total = 0
    for p in paths:
        fp = BASE / p
        if fp.exists():
            total += fp.stat().st_size
    return total

# ── A. Posts plan ─────────────────────────────────────────────────────────────
posts_plan = []
for post in manifest.get("posts", []):
    prepared_paths = [
        inp["prepared_path"] for inp in post.get("prepared_inputs", [])
        if inp.get("used_for_openai_plan") and inp.get("prepared_path")
    ]
    img_count = len(prepared_paths)
    payload_bytes = est_bytes(prepared_paths)
    req_errors = []

    if img_count > MAX_IMAGES_PER_REQ:
        req_errors.append(f"images_count {img_count} exceeds max {MAX_IMAGES_PER_REQ}")
    if payload_bytes > MAX_PAYLOAD_MB * 1024 * 1024:
        req_errors.append(f"payload {payload_bytes // 1024 // 1024} MB exceeds {MAX_PAYLOAD_MB} MB")

    posts_plan.append({
        "request_id": f"post_{post['content_id']}",
        "content_id": post["content_id"],
        "url": post.get("url", ""),
        "type": post.get("type", "unknown"),
        "caption_found": bool(post.get("caption")),
        "prepared_paths": prepared_paths,
        "images_count": img_count,
        "estimated_payload_size_bytes": payload_bytes,
        "status": "FAIL" if req_errors else "OK",
        "errors": req_errors,
    })

# ── B. Highlight batch plan ───────────────────────────────────────────────────
stories = manifest.get("highlight", {}).get("stories", [])
# only stories with prepared inputs
ready_stories = [s for s in stories if any(
    inp.get("used_for_openai_plan") and inp.get("prepared_path")
    for inp in s.get("prepared_inputs", [])
)]

batches_plan = []
for batch_i, start in enumerate(range(0, len(ready_stories), BATCH_SIZE)):
    batch = ready_stories[start: start + BATCH_SIZE]
    prepared_paths = [
        inp["prepared_path"]
        for s in batch
        for inp in s.get("prepared_inputs", [])
        if inp.get("used_for_openai_plan") and inp.get("prepared_path")
    ]
    img_count    = len(prepared_paths)
    payload_bytes = est_bytes(prepared_paths)
    req_errors    = []

    if img_count > MAX_IMAGES_PER_REQ:
        req_errors.append(f"images_count {img_count} exceeds max {MAX_IMAGES_PER_REQ}")
    if payload_bytes > MAX_PAYLOAD_MB * 1024 * 1024:
        req_errors.append(f"payload {payload_bytes // 1024 // 1024} MB exceeds {MAX_PAYLOAD_MB} MB")

    batches_plan.append({
        "request_id": f"highlight_batch_{batch_i + 1}",
        "batch_index": batch_i + 1,
        "story_ids": [s["story_id"] for s in batch],
        "story_numbers": [s["story_number"] for s in batch],
        "prepared_paths": prepared_paths,
        "images_count": img_count,
        "estimated_payload_size_bytes": payload_bytes,
        "status": "FAIL" if req_errors else "OK",
        "errors": req_errors,
    })

# ── C. Synthesis plan ─────────────────────────────────────────────────────────
synthesis_plan = {
    "request_id": "highlight_synthesis",
    "uses_images": False,
    "uses_batch_outputs_only": True,
    "status": "OK",
}

# ── Safety guards ─────────────────────────────────────────────────────────────
total_requests = len(posts_plan) + len(batches_plan) + 1  # +1 synthesis
total_images   = sum(p["images_count"] for p in posts_plan + batches_plan)
max_imgs_req   = max((p["images_count"] for p in posts_plan + batches_plan), default=0)
max_payload_b  = max((p["estimated_payload_size_bytes"] for p in posts_plan + batches_plan), default=0)
max_payload_mb = round(max_payload_b / 1024 / 1024, 2)

all_prepared_paths = [
    p for pl in posts_plan + batches_plan for p in pl["prepared_paths"]
]
total_inputs = len(all_prepared_paths)

if total_requests > MAX_TOTAL_REQUESTS:
    plan_errors.append(f"estimated_openai_requests {total_requests} > max {MAX_TOTAL_REQUESTS}")
if max_imgs_req > MAX_IMAGES_PER_REQ:
    plan_errors.append(f"max images in one request {max_imgs_req} > max {MAX_IMAGES_PER_REQ}")
if max_payload_b > MAX_PAYLOAD_MB * 1024 * 1024:
    plan_errors.append(f"max payload {max_payload_mb} MB > max {MAX_PAYLOAD_MB} MB")
if total_inputs > MAX_TOTAL_INPUTS:
    plan_errors.append(f"total_prepared_inputs {total_inputs} > max {MAX_TOTAL_INPUTS}")

any_req_fail = any(p["status"] == "FAIL" for p in posts_plan + batches_plan)
if any_req_fail:
    plan_errors.append("one or more individual requests exceed limits")

if plan_errors:
    plan_status = "FAIL"
elif any(p["status"] == "FAIL" for p in posts_plan):
    plan_status = "PARTIAL"
else:
    plan_status = "OK"

can_run_stage4b = plan_status in ("OK", "PARTIAL")

plan = {
    "account": "vlada_kliuiko",
    "stage": "stage4a_openai_plan",
    "openai_call_allowed": False,
    "posts_plan": posts_plan,
    "highlight_batches_plan": batches_plan,
    "synthesis_plan": synthesis_plan,
    "summary": {
        "posts_requests": len(posts_plan),
        "highlight_batch_requests": len(batches_plan),
        "synthesis_requests": 1,
        "estimated_openai_requests": total_requests,
        "total_images_planned": total_images,
        "max_images_in_one_request": max_imgs_req,
        "max_payload_size_mb": max_payload_mb,
        "plan_status": plan_status,
        "can_run_stage4b": can_run_stage4b,
        "errors": plan_errors,
    },
}

PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"posts requests:            {len(posts_plan)}")
print(f"highlight batch requests:  {len(batches_plan)}")
print(f"synthesis requests:        1")
print(f"estimated total requests:  {total_requests} (max {MAX_TOTAL_REQUESTS})")
print(f"total images planned:      {total_images}")
print(f"max images in one request: {max_imgs_req} (max {MAX_IMAGES_PER_REQ})")
print(f"max payload size:          {max_payload_mb} MB (max {MAX_PAYLOAD_MB} MB)")
print(f"total prepared inputs:     {total_inputs} (max {MAX_TOTAL_INPUTS})")
print(f"plan_status:               {plan_status}")
print(f"can_run_stage4b:           {can_run_stage4b}")
if plan_errors:
    print("plan errors:")
    for e in plan_errors:
        print(f"  - {e}")
print(f"saved: {PLAN_PATH.relative_to(BASE)}")
