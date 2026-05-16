"""
One-off test: compare 3 Apify actors for Instagram Reel transcript extraction.
Run: python scripts/_test_transcript_actors.py
"""

import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env", override=True)
except ImportError:
    pass

try:
    from apify_client import ApifyClient
except ImportError:
    raise SystemExit("apify-client not installed — run: pip install apify-client")

TOKEN = os.environ.get("APIFY_TOKEN", "")
if not TOKEN:
    raise SystemExit("[ERROR] APIFY_TOKEN not set")

client = ApifyClient(TOKEN)

REEL_URL = "https://www.instagram.com/p/DXxLzsNug-u/"

ACTORS = [
    {
        "id":    "apify/instagram-reel-scraper",
        "label": "1. apify/instagram-reel-scraper (includeTranscript: true)",
        "input": {
            "username":          ["vlada_kliuiko"],
            "resultsLimit":      1,
            "includeTranscript": True,
        },
    },
    {
        "id":    "crawlerbros/instagram-transcript-scraper",
        "label": "2. crawlerbros/instagram-transcript-scraper",
        "input": {
            "urls": [REEL_URL],
        },
    },
    {
        "id":    "bulletproof/instagram-transcript",
        "label": "3. bulletproof/instagram-transcript",
        "input": {
            "urls": [REEL_URL],
        },
    },
]

# Fields we care about in the normalized summary
SUMMARY_FIELDS = [
    "transcript", "caption", "viewCount", "videoPlayCount",
    "videoViewCount", "displayUrl", "thumbnailUrl", "videoUrl",
    "likesCount", "commentsCount",
]


def truncate(v, n=120):
    s = str(v)
    return s[:n] + "…" if len(s) > n else s


def run_actor(spec: dict) -> dict:
    label = spec["label"]
    actor_id = spec["id"]
    run_input = spec["input"]

    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"Input: {json.dumps(run_input, ensure_ascii=False)}")
    print("Starting run...")

    t0 = time.time()
    try:
        run = client.actor(actor_id).call(run_input=run_input, timeout_secs=120)
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        print(f"[FAIL] Actor call exception after {elapsed}s: {e}")
        return {"actor": actor_id, "error": str(e), "elapsed_s": elapsed}

    elapsed = round(time.time() - t0, 1)
    run_id     = run.get("id", "?")
    dataset_id = run.get("defaultDatasetId", "?")
    status     = run.get("status", "?")
    stats      = run.get("stats", {})
    cost_usd   = stats.get("computeUnits", 0) * 0.004  # rough Apify compute unit cost

    print(f"Run ID:     {run_id}")
    print(f"Dataset ID: {dataset_id}")
    print(f"Status:     {status}")
    print(f"Elapsed:    {elapsed}s")

    if status != "SUCCEEDED":
        print(f"[FAIL] Run did not succeed")
        return {"actor": actor_id, "status": status, "elapsed_s": elapsed,
                "run_id": run_id, "error": f"status={status}"}

    try:
        items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        print(f"[FAIL] Could not fetch dataset: {e}")
        return {"actor": actor_id, "status": status, "elapsed_s": elapsed,
                "run_id": run_id, "error": str(e)}

    print(f"Items returned: {len(items)}")

    result = {
        "actor":      actor_id,
        "status":     status,
        "elapsed_s":  elapsed,
        "run_id":     run_id,
        "dataset_id": dataset_id,
        "item_count": len(items),
    }

    if not items:
        result["error"] = "empty dataset"
        return result

    item = items[0]
    all_keys = sorted(item.keys())
    result["all_keys"] = all_keys

    # Transcript
    transcript = item.get("transcript")
    result["has_transcript"] = transcript not in (None, "", [], {})
    result["transcript"]     = transcript

    # Summary fields
    summary = {}
    for f in SUMMARY_FIELDS:
        v = item.get(f)
        if v is not None:
            summary[f] = v
    result["summary_fields"] = summary

    return result


def print_result(r: dict):
    label = r["actor"]
    print(f"\n{'─'*60}")
    print(f"RESULT: {label}")
    print(f"  Status:    {r.get('status', 'N/A')}")
    print(f"  Elapsed:   {r.get('elapsed_s', '?')}s")
    print(f"  Run ID:    {r.get('run_id', 'N/A')}")
    if r.get("error"):
        print(f"  ERROR:     {r['error']}")
        return
    print(f"  Items:     {r.get('item_count', 0)}")
    print(f"  All keys:  {', '.join(r.get('all_keys', []))}")
    print()
    has_t = r.get("has_transcript", False)
    t_val = r.get("transcript")
    print(f"  transcript present: {'YES ✅' if has_t else 'NO ❌'}")
    if has_t:
        print(f"  transcript value:   {truncate(t_val, 300)}")
    print()
    for f, v in (r.get("summary_fields") or {}).items():
        print(f"  {f}: {truncate(v, 100)}")


def main():
    print(f"Reel under test: {REEL_URL}")
    print(f"Testing {len(ACTORS)} actors...\n")

    results = []
    for spec in ACTORS:
        r = run_actor(spec)
        results.append(r)
        print_result(r)

    # Save raw results for reference
    out_path = BASE / "data" / "vlada_kliuiko" / "raw" / "_transcript_actor_test.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n[OK] Raw results saved to {out_path.relative_to(BASE)}")

    # Final comparison table
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")
    print(f"{'Actor':<45} {'Status':<10} {'Transcript':<12} {'Time'}")
    print(f"{'─'*45} {'─'*10} {'─'*12} {'─'*8}")
    for r in results:
        name     = r["actor"].split("/")[-1][:44]
        status   = r.get("status", "ERROR")[:9]
        has_t    = "YES ✅" if r.get("has_transcript") else "NO ❌"
        elapsed  = f"{r.get('elapsed_s','?')}s"
        print(f"{name:<45} {status:<10} {has_t:<12} {elapsed}")


if __name__ == "__main__":
    main()
