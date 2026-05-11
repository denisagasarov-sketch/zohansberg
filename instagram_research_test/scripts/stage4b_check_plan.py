import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE = Path(__file__).parent.parent

PLAN_PATH        = BASE / "data/normalized/stage4a_openai_plan.json"
CHECK_OUT_PATH   = BASE / "data/normalized/stage4b_plan_check.json"
GITIGNORE_PATH   = BASE / ".gitignore"
ENV_PATH         = BASE / ".env"

MAX_OPENAI_CALLS = 13

load_dotenv(dotenv_path=ENV_PATH, override=True)

errors = []

# ── .env + key ────────────────────────────────────────────────────────────────
env_exists       = ENV_PATH.exists()
openai_key_found = False
openai_key_valid = False

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not env_exists:
    errors.append(".env file not found")
else:
    if OPENAI_API_KEY:
        openai_key_found = True
        if not OPENAI_API_KEY.startswith("sk-"):
            errors.append("OPENAI_API_KEY does not start with 'sk-'")
        elif not OPENAI_API_KEY.isascii():
            errors.append("OPENAI_API_KEY contains non-ASCII characters")
        elif any(c in OPENAI_API_KEY for c in (" ", "\t", "\n")):
            errors.append("OPENAI_API_KEY contains whitespace")
        else:
            openai_key_valid = True
    else:
        errors.append("OPENAI_API_KEY not set in .env")

# ── Plan file ─────────────────────────────────────────────────────────────────
plan_found   = False
plan_status  = None
can_run      = False
plan         = None

posts_requests_count    = 0
highlight_batch_count   = 0
all_files_found         = False
limits_ok               = False
planned_calls           = 0
missing_files           = []
limit_violations        = []

if not PLAN_PATH.exists():
    errors.append("stage4a_openai_plan.json not found")
else:
    plan_found = True
    try:
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"stage4a_openai_plan.json parse error: {e}")
        plan = None

if plan:
    summary = plan.get("summary", {})
    plan_status = summary.get("plan_status")
    can_run     = summary.get("can_run_stage4b", False)

    if plan_status != "OK":
        errors.append(f"plan_status is '{plan_status}', expected 'OK'")
    if not can_run:
        errors.append("can_run_stage4b is false")

    posts_plan    = plan.get("posts_plan", [])
    batches_plan  = plan.get("highlight_batches_plan", [])

    posts_ok    = [p for p in posts_plan    if p.get("status") == "OK"]
    batches_ok  = [b for b in batches_plan  if b.get("status") == "OK"]

    posts_requests_count  = len(posts_plan)
    highlight_batch_count = len(batches_plan)

    if len(posts_ok) != 5:
        errors.append(f"expected 5 OK posts requests, got {len(posts_ok)}")
    if len(batches_ok) != 8:
        errors.append(f"expected 8 OK highlight batch requests, got {len(batches_ok)}")

    # Check per-request limits and file existence
    for req in posts_plan + batches_plan:
        if req.get("images_count", 0) > 10:
            limit_violations.append(
                f"{req['request_id']}: images_count {req['images_count']} > 10"
            )
        if req.get("estimated_payload_size_bytes", 0) > 20 * 1024 * 1024:
            mb = req["estimated_payload_size_bytes"] // 1024 // 1024
            limit_violations.append(
                f"{req['request_id']}: payload {mb} MB > 20 MB"
            )
        for p in req.get("prepared_paths", []):
            fp = BASE / p
            if not fp.exists():
                missing_files.append(p)

    if limit_violations:
        errors.extend(limit_violations)
    if missing_files:
        errors.append(f"{len(missing_files)} prepared file(s) not found locally")

    all_files_found = len(missing_files) == 0
    limits_ok       = len(limit_violations) == 0

    # How many calls to make (skip existing OK outputs without --force)
    force = "--force" in sys.argv
    for req in posts_plan:
        out = BASE / "analysis" / "stage4b" / "posts" / f"{req['request_id']}.json"
        if out.exists() and not force:
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
                if existing.get("status") == "OK":
                    continue
            except Exception:
                pass
        planned_calls += 1

    for req in batches_plan:
        out = BASE / "analysis" / "stage4b" / "highlight_batches" / f"{req['request_id']}.json"
        if out.exists() and not force:
            try:
                existing = json.loads(out.read_text(encoding="utf-8"))
                if existing.get("status") == "OK":
                    continue
            except Exception:
                pass
        planned_calls += 1

    if planned_calls > MAX_OPENAI_CALLS:
        errors.append(
            f"planned_calls_to_make {planned_calls} > max {MAX_OPENAI_CALLS}"
        )

# ── .gitignore ────────────────────────────────────────────────────────────────
gitignore_safe = False
if GITIGNORE_PATH.exists():
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    required = [".env", "data/raw/", "output/", "analysis/openai_responses/"]
    gitignore_safe = all(r in content for r in required)
if not gitignore_safe:
    errors.append(".gitignore missing required safety entries")

# ── Result ────────────────────────────────────────────────────────────────────
can_continue = (
    openai_key_valid
    and plan_found
    and plan_status == "OK"
    and can_run
    and all_files_found
    and limits_ok
    and planned_calls <= MAX_OPENAI_CALLS
    and gitignore_safe
    and len(errors) == 0
)

result = {
    "stage":                    "stage4b_plan_check",
    "openai_key_found":         openai_key_found,
    "openai_key_valid":         openai_key_valid,
    "plan_found":               plan_found,
    "plan_status":              plan_status,
    "can_run_stage4b":          can_run,
    "posts_requests":           posts_requests_count,
    "highlight_batch_requests": highlight_batch_count,
    "all_prepared_files_found": all_files_found,
    "limits_ok":                limits_ok,
    "max_openai_calls_allowed": MAX_OPENAI_CALLS,
    "planned_calls_to_make":    planned_calls,
    "stage4b_can_continue":     can_continue,
    "errors":                   errors,
}

CHECK_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
CHECK_OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

for k, v in result.items():
    if k != "errors":
        print(f"{k}: {v}")
if errors:
    print("errors:")
    for e in errors:
        print(f"  - {e}")
print(f"saved: {CHECK_OUT_PATH.relative_to(BASE)}")

if not can_continue:
    sys.exit(1)
