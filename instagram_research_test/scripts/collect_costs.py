"""Aggregate real OpenAI token costs from pipeline normalized outputs.

Also collects Apify costs per stage via the Apify API using run IDs stored
in the normalized summary files (profile_summary → 5A-1, stage5b1 → 5B-1,
stage5b2 → 5B-2).
"""

import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent

RATES = {
    "gpt-4o-mini": 0.000375,
    "gpt-4o":      0.005,
}

SOURCES = [
    {
        "stage": "5A-2C",
        "file":  "stage5a2c_pinned_posts_semantic.json",
        "model_default": "gpt-4o-mini",
        "get_tokens": lambda d: d.get("total_tokens_used") or 0,
        "get_model":  lambda d: d.get("model") or "gpt-4o-mini",
    },
    {
        "stage": "5A-2D",
        "file":  "stage5a2d_pinned_hooks.json",
        "model_default": "gpt-4o",
        "get_tokens": lambda d: sum(p.get("tokens_used") or 0 for p in (d.get("posts") or [])),
        "get_model":  lambda d: "gpt-4o",
    },
    {
        "stage": "5A-2E",
        "file":  "stage5a2e_bio_semantic.json",
        "model_default": "gpt-4o-mini",
        "get_tokens": lambda d: d.get("tokens_used") or 0,
        "get_model":  lambda d: "gpt-4o-mini",
    },
    {
        "stage": "5A-2F",
        "file":  "stage5a2f_link_destination.json",
        "model_default": "gpt-4o-mini",
        "get_tokens": lambda d: d.get("tokens_used") or 0,
        "get_model":  lambda d: "gpt-4o-mini",
    },
    {
        "stage": "5A-2G",
        "file":  "stage5a2g_landing_analysis.json",
        "model_default": "gpt-4o",
        "get_tokens": lambda d: d.get("tokens_used") or 0,
        "get_model":  lambda d: "gpt-4o",
    },
    {
        "stage": "5B-2V",
        "file":  "stage5b2v_highlights_visual.json",
        "model_default": "gpt-4o",
        "get_tokens": lambda d: sum(h.get("tokens_used") or 0 for h in (d.get("analyzed_highlights") or [])),
        "get_model":  lambda d: "gpt-4o",
    },
]

# Normalized files that contain apify_run_ids, keyed by pipeline stage label
APIFY_SOURCES = [
    {"stage": "Сбор профиля",   "file": "profile_summary.json"},
    {"stage": "Сбор хайлайтов", "file": "stage5b1_highlights_index_summary.json"},
    {"stage": "Сбор сторис",    "file": "stage5b2_highlights_stories_summary.json"},
]


FORECAST_RATES = {
    "apify_profile":             0.08,
    "apify_highlights":          0.15,
    "apify_stories_per_highlight": 0.14,
    "openai_pinned_per_post":    0.002,
    "openai_vision_per_highlight": 0.005,
}


def _cost(tokens: int, model: str) -> float:
    rate = RATES.get(model, 0)
    return round(tokens * rate / 1000, 4)


def _apify_run_cost(run_id: str, token: str) -> float | None:
    """Query Apify API for a single run's usageTotalUsd. Returns None on failure."""
    url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("data", {}).get("usageTotalUsd")
    except Exception:
        return None


def collect_apify_costs(account: str) -> dict:
    """Return {stage: {"run_ids": [...], "cost_usd": float}} for Apify stages.

    Returns empty dict if APIFY_TOKEN is not set or no run IDs found.
    """
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token:
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=BASE / ".env", override=False)
            token = os.environ.get("APIFY_TOKEN", "").strip()
        except ImportError:
            pass
    if not token:
        return {}

    norm_dir = BASE / "data" / account / "normalized"
    result = {}

    for src in APIFY_SOURCES:
        path = norm_dir / src["file"]
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        run_ids = data.get("apify_run_ids") or []
        if not run_ids:
            continue

        total = 0.0
        for rid in run_ids:
            cost = _apify_run_cost(rid, token)
            if cost is not None:
                total += cost

        entry: dict = {
            "run_ids":  run_ids,
            "cost_usd": round(total, 4),
        }

        # Extra detail for Сбор сторис
        if src["stage"] == "Сбор сторис":
            hl = data.get("highlights_ok") or data.get("highlights_processed") or 0
            stories = data.get("total_stories_count") or 0
            if hl or stories:
                entry["detail"] = f"{hl} хайлайтов, {stories} сторис"

        result[src["stage"]] = entry

    return result


def estimate_next_run(account: str) -> dict:
    """Build cost forecast for the next pipeline run from normalized data."""
    norm_dir = BASE / "data" / account / "normalized"

    # Pinned post count — prefer stage5a2b (actual scraped posts)
    pinned_count = 0
    for fname, key in [
        ("stage5a2b_pinned_posts_details.json", "posts"),
        ("pinned_posts_index.json", "pinned_posts"),
    ]:
        path = norm_dir / fname
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                pinned_count = data.get("total_pinned_posts") or len(data.get(key) or [])
                if pinned_count:
                    break
            except Exception:
                pass

    # Highlight count
    highlight_count = 0
    hl_path = norm_dir / "highlights_index.json"
    if hl_path.exists():
        try:
            data = json.loads(hl_path.read_text(encoding="utf-8"))
            highlight_count = (
                data.get("unique_highlights_count")
                or len(data.get("highlights") or [])
            )
        except Exception:
            pass

    # Stories count (informational only)
    stories_count = 0
    stories_path = norm_dir / "stage5b2_highlights_stories_summary.json"
    if stories_path.exists():
        try:
            data = json.loads(stories_path.read_text(encoding="utf-8"))
            stories_count = data.get("total_stories_count") or 0
        except Exception:
            pass

    r = FORECAST_RATES
    apify_profile    = r["apify_profile"]
    apify_highlights = r["apify_highlights"]
    apify_stories    = round(r["apify_stories_per_highlight"] * highlight_count, 4)
    openai_pinned    = round(r["openai_pinned_per_post"] * pinned_count, 4)
    openai_vision    = round(r["openai_vision_per_highlight"] * highlight_count, 4)

    total_apify  = round(apify_profile + apify_highlights + apify_stories, 4)
    total_openai = round(openai_pinned + openai_vision, 4)
    total        = round(total_apify + total_openai, 4)

    return {
        "inputs": {
            "pinned_count":    pinned_count,
            "highlight_count": highlight_count,
            "stories_count":   stories_count,
        },
        "apify": {
            "profile_usd":    apify_profile,
            "highlights_usd": apify_highlights,
            "stories_usd":    apify_stories,
            "total_usd":      total_apify,
        },
        "openai": {
            "pinned_posts_usd":       openai_pinned,
            "vision_highlights_usd":  openai_vision,
            "total_usd":              total_openai,
        },
        "total_usd": total,
    }


def collect(account: str) -> dict:
    norm_dir = BASE / "data" / account / "normalized"
    stages = {}

    for src in SOURCES:
        path = norm_dir / src["file"]
        if not path.exists():
            print(f"  [SKIP] {src['stage']}: {path.relative_to(BASE)} not found")
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [SKIP] {src['stage']}: cannot read file — {e}")
            continue

        tokens = src["get_tokens"](data)
        model  = src["get_model"](data)
        cost   = _cost(tokens, model)

        stages[src["stage"]] = {
            "tokens":   tokens,
            "model":    model,
            "cost_usd": cost,
        }

    total_tokens = sum(v["tokens"] for v in stages.values())
    total_cost   = round(sum(v["cost_usd"] for v in stages.values()), 4)

    apify_stages = collect_apify_costs(account)
    apify_total  = round(sum(v["cost_usd"] for v in apify_stages.values()), 4) if apify_stages else None

    next_run = estimate_next_run(account)

    return {
        "account":      account,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "stages":       stages,
        "apify_stages": apify_stages,
        "totals": {
            "total_tokens":    total_tokens,
            "total_cost_usd":  total_cost,
            "apify_total_usd": apify_total,
        },
        "next_run_estimate": next_run,
    }


def print_report(result: dict, summary_only: bool = False):
    account      = result["account"]
    stages       = result["stages"]
    totals       = result["totals"]
    apify_stages = result.get("apify_stages") or {}
    total_tokens = totals["total_tokens"]
    total_cost   = totals["total_cost_usd"]
    apify_total  = totals.get("apify_total_usd")
    next_run     = result.get("next_run_estimate") or {}

    if summary_only:
        apify_str = f"${apify_total:.4f}" if apify_total is not None else "см. console.apify.com"
        print(f"  Итого OpenAI: ${total_cost:.4f} | Apify: {apify_str}")
        if next_run:
            print(f"  Прогноз след. запуска: ${next_run.get('total_usd', 0):.4f}")
        return

    print(f"\n=== Затраты OpenAI для @{account} ===")
    for stage, v in stages.items():
        label = f"  {stage} ({v['model']}):"
        print(f"{label:<28} {v['tokens']:>6} токенов  ${v['cost_usd']:.4f}")
    print(f"  {'─' * 37}")
    print(f"  {'Итого OpenAI:':<26} {total_tokens:>6} токенов  ${total_cost:.4f}")

    if apify_stages:
        print(f"\n=== Затраты Apify для @{account} ===")
        for stage, v in apify_stages.items():
            label = f"  {stage}:"
            print(f"{label:<28} {len(v['run_ids'])} run(s)     ${v['cost_usd']:.4f}")
        print(f"  {'─' * 37}")
        apify_str = f"${apify_total:.4f}" if apify_total is not None else "—"
        print(f"  {'Итого Apify:':<26}            {apify_str}")
    else:
        print(f"  Apify: см. console.apify.com")

    if next_run:
        inp = next_run.get("inputs", {})
        a   = next_run.get("apify", {})
        o   = next_run.get("openai", {})
        print(f"\n=== Прогноз следующего запуска @{account} ===")
        print(f"  Входные данные: {inp.get('pinned_count')} закрепов, "
              f"{inp.get('highlight_count')} хайлайтов, "
              f"{inp.get('stories_count')} сторис")
        print(f"  Apify: профиль ${a.get('profile_usd'):.2f} + "
              f"хайлайты ${a.get('highlights_usd'):.2f} + "
              f"сторис ${a.get('stories_usd'):.4f} = ${a.get('total_usd'):.4f}")
        print(f"  OpenAI: закрепы ${o.get('pinned_posts_usd'):.4f} + "
              f"Vision ${o.get('vision_highlights_usd'):.4f} = ${o.get('total_usd'):.4f}")
        print(f"  {'─' * 37}")
        print(f"  {'Итого прогноз:':<26}            ${next_run.get('total_usd', 0):.4f}")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate real OpenAI token costs from pipeline outputs"
    )
    parser.add_argument("--account",  required=True, help="Instagram account to process")
    parser.add_argument("--summary",  action="store_true", help="Print only the total line")
    args = parser.parse_args()

    result = collect(args.account)

    print_report(result, summary_only=args.summary)

    out_path = BASE / "output" / args.account / "costs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Записано: {out_path.relative_to(BASE)}")


if __name__ == "__main__":
    main()
