import json
from pathlib import Path

BASE = Path(__file__).parent.parent

MANIFEST_PATH = BASE / "data/normalized/stage4a_media_manifest.json"
PLAN_PATH     = BASE / "data/normalized/stage4a_openai_plan.json"

MAX_STORIES_PER_BATCH  = 8
MAX_TOTAL_REQUESTS     = 15
MAX_IMAGES_PER_REQUEST = 10
MAX_PAYLOAD_MB         = 20
MAX_TOTAL_INPUTS       = 120
MAX_FRAMES_PER_STORY   = 2   # representative sampling cap for video stories

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


def select_representative(prepared_inputs):
    """
    Pick representative paths for a single story:
    - Video frames present → up to MAX_FRAMES_PER_STORY frames
    - No frames → 1 image
    - Hard cap at MAX_IMAGES_PER_REQUEST with warning
    Returns (selected_paths, warnings)
    """
    used = [inp for inp in prepared_inputs
            if inp.get("used_for_openai_plan") and inp.get("prepared_path")]

    frames = [inp["prepared_path"] for inp in used if inp.get("input_type") == "frame"]
    images = [inp["prepared_path"] for inp in used if inp.get("input_type") == "image"]

    selected = frames[:MAX_FRAMES_PER_STORY] if frames else images[:1]

    warnings = []
    if len(selected) > MAX_IMAGES_PER_REQUEST:
        warnings.append(
            f"story contributed {len(selected)} inputs; truncated to {MAX_IMAGES_PER_REQUEST}"
        )
        selected = selected[:MAX_IMAGES_PER_REQUEST]

    return selected, warnings


# ── A. Posts plan ─────────────────────────────────────────────────────────────
posts_plan = []
for post in manifest.get("posts", []):
    prepared_paths = [
        inp["prepared_path"] for inp in post.get("prepared_inputs", [])
        if inp.get("used_for_openai_plan") and inp.get("prepared_path")
    ]
    img_count     = len(prepared_paths)
    payload_bytes = est_bytes(prepared_paths)
    req_errors    = []

    if img_count > MAX_IMAGES_PER_REQUEST:
        req_errors.append(f"images_count {img_count} exceeds max {MAX_IMAGES_PER_REQUEST}")
    if payload_bytes > MAX_PAYLOAD_MB * 1024 * 1024:
        req_errors.append(f"payload {payload_bytes // 1024 // 1024} MB exceeds {MAX_PAYLOAD_MB} MB")

    posts_plan.append({
        "request_id":                   f"post_{post['content_id']}",
        "content_id":                   post["content_id"],
        "url":                          post.get("url", ""),
        "type":                         post.get("type", "unknown"),
        "caption_found":                bool(post.get("caption")),
        "prepared_paths":               prepared_paths,
        "images_count":                 img_count,
        "estimated_payload_size_bytes": payload_bytes,
        "status":                       "FAIL" if req_errors else "OK",
        "errors":                       req_errors,
    })

# ── B. Highlight batch plan — image-count-aware ───────────────────────────────
stories = manifest.get("highlight", {}).get("stories", [])

# Precompute representative inputs per ready story
ready_stories = []
for s in stories:
    selected, warns = select_representative(s.get("prepared_inputs", []))
    if selected:
        ready_stories.append({
            "story_id":     s["story_id"],
            "story_number": s["story_number"],
            "selected":     selected,
            "warnings":     warns,
        })

# Build batches: close when adding next story would exceed MAX_IMAGES_PER_REQUEST
# or when story count reaches MAX_STORIES_PER_BATCH
batches_plan = []
current_stories:  list = []
current_paths:    list = []
current_warnings: list = []


def flush_batch(stories_list, paths_list, warnings_list, batch_idx):
    img_count     = len(paths_list)
    payload_bytes = est_bytes(paths_list)
    req_errors    = []
    if img_count > MAX_IMAGES_PER_REQUEST:
        req_errors.append(f"images_count {img_count} exceeds max {MAX_IMAGES_PER_REQUEST}")
    if payload_bytes > MAX_PAYLOAD_MB * 1024 * 1024:
        req_errors.append(f"payload {payload_bytes // 1024 // 1024} MB exceeds {MAX_PAYLOAD_MB} MB")
    batches_plan.append({
        "request_id":                   f"highlight_batch_{batch_idx}",
        "batch_index":                  batch_idx,
        "story_ids":                    [s["story_id"]     for s in stories_list],
        "story_numbers":                [s["story_number"] for s in stories_list],
        "prepared_paths":               list(paths_list),
        "images_count":                 img_count,
        "estimated_payload_size_bytes": payload_bytes,
        "status":                       "FAIL" if req_errors else "OK",
        "errors":                       req_errors + warnings_list,
    })


batch_idx = 1
for rs in ready_stories:
    would_exceed_images  = (len(current_paths) + len(rs["selected"])) > MAX_IMAGES_PER_REQUEST
    would_exceed_stories = len(current_stories) >= MAX_STORIES_PER_BATCH

    if current_stories and (would_exceed_images or would_exceed_stories):
        flush_batch(current_stories, current_paths, current_warnings, batch_idx)
        batch_idx += 1
        current_stories  = []
        current_paths    = []
        current_warnings = []

    current_stories.append(rs)
    current_paths.extend(rs["selected"])
    current_warnings.extend(rs["warnings"])

if current_stories:
    flush_batch(current_stories, current_paths, current_warnings, batch_idx)

# ── C. Synthesis plan ─────────────────────────────────────────────────────────
synthesis_plan = {
    "request_id":              "highlight_synthesis",
    "uses_images":             False,
    "uses_batch_outputs_only": True,
    "status":                  "OK",
}

# ── Safety guards ─────────────────────────────────────────────────────────────
total_requests = len(posts_plan) + len(batches_plan) + 1   # +1 synthesis
total_images   = sum(p["images_count"] for p in posts_plan + batches_plan)
max_imgs_req   = max((p["images_count"] for p in posts_plan + batches_plan), default=0)
max_payload_b  = max((p["estimated_payload_size_bytes"] for p in posts_plan + batches_plan), default=0)
max_payload_mb = round(max_payload_b / 1024 / 1024, 2)

# selected inputs = only those going into the plan
all_selected_paths = [p for pl in posts_plan + batches_plan for p in pl["prepared_paths"]]
total_selected     = len(all_selected_paths)

# total prepared inputs in manifest (for reporting context only)
all_prepared_paths = [
    inp["prepared_path"]
    for group in [manifest.get("posts", [])] + [manifest.get("highlight", {}).get("stories", [])]
    for item in group
    for inp in item.get("prepared_inputs", [])
    if inp.get("prepared_path")
]
total_prepared = len(all_prepared_paths)
inputs_dropped = total_prepared - total_selected

if total_requests > MAX_TOTAL_REQUESTS:
    plan_errors.append(f"estimated_openai_requests {total_requests} > max {MAX_TOTAL_REQUESTS}")
if max_imgs_req > MAX_IMAGES_PER_REQUEST:
    plan_errors.append(f"max images in one request {max_imgs_req} > max {MAX_IMAGES_PER_REQUEST}")
if max_payload_b > MAX_PAYLOAD_MB * 1024 * 1024:
    plan_errors.append(f"max payload {max_payload_mb} MB > max {MAX_PAYLOAD_MB} MB")
if total_selected > MAX_TOTAL_INPUTS:
    plan_errors.append(f"total_selected_inputs {total_selected} > max {MAX_TOTAL_INPUTS}")

any_req_fail = any(p["status"] == "FAIL" for p in posts_plan + batches_plan)
if any_req_fail:
    plan_errors.append("one or more individual requests exceed limits")

has_ok_post  = any(p["status"] == "OK" for p in posts_plan)
has_ok_batch = any(b["status"] == "OK" for b in batches_plan)

if plan_errors:
    plan_status = "FAIL"
elif not has_ok_post or not has_ok_batch:
    plan_status = "PARTIAL"
else:
    plan_status = "OK"

can_run_stage4b = plan_status == "OK"

plan = {
    "account":                "vlada_kliuiko",
    "stage":                  "stage4a_openai_plan",
    "openai_call_allowed":    False,
    "posts_plan":             posts_plan,
    "highlight_batches_plan": batches_plan,
    "synthesis_plan":         synthesis_plan,
    "summary": {
        "posts_requests":             len(posts_plan),
        "highlight_batch_requests":   len(batches_plan),
        "synthesis_requests":         1,
        "estimated_openai_requests":  total_requests,
        "total_prepared_inputs":      total_prepared,
        "total_selected_inputs":      total_selected,
        "inputs_dropped_by_sampling": inputs_dropped,
        "total_images_planned":       total_images,
        "max_images_in_one_request":  max_imgs_req,
        "max_payload_size_mb":        max_payload_mb,
        "plan_status":                plan_status,
        "can_run_stage4b":            can_run_stage4b,
        "errors":                     plan_errors,
    },
}

PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
PLAN_PATH.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"posts requests:              {len(posts_plan)}")
print(f"highlight batch requests:    {len(batches_plan)}")
print(f"synthesis requests:          1")
print(f"estimated total requests:    {total_requests} (max {MAX_TOTAL_REQUESTS})")
print(f"total prepared inputs:       {total_prepared}")
print(f"total selected inputs:       {total_selected} (max {MAX_TOTAL_INPUTS})")
print(f"inputs dropped by sampling:  {inputs_dropped}")
print(f"total images planned:        {total_images}")
print(f"max images in one request:   {max_imgs_req} (max {MAX_IMAGES_PER_REQUEST})")
print(f"max payload size:            {max_payload_mb} MB (max {MAX_PAYLOAD_MB} MB)")
print(f"plan_status:                 {plan_status}")
print(f"can_run_stage4b:             {can_run_stage4b}")
if plan_errors:
    print("plan errors:")
    for e in plan_errors:
        print(f"  - {e}")
print(f"saved: {PLAN_PATH.relative_to(BASE)}")
