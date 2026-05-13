"""Aggregate real OpenAI token costs from pipeline normalized outputs."""

import argparse
import json
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


def _cost(tokens: int, model: str) -> float:
    rate = RATES.get(model, 0)
    return round(tokens * rate / 1000, 4)


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

    return {
        "account":      account,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "stages":       stages,
        "totals": {
            "total_tokens":  total_tokens,
            "total_cost_usd": total_cost,
            "note": "Apify затраты не включены — берите из Apify Console",
        },
    }


def print_report(result: dict, summary_only: bool = False):
    account     = result["account"]
    stages      = result["stages"]
    totals      = result["totals"]
    total_tokens = totals["total_tokens"]
    total_cost   = totals["total_cost_usd"]

    if summary_only:
        print(f"  Итого OpenAI: ${total_cost:.4f} | Apify: см. console.apify.com")
        return

    print(f"\n=== Затраты OpenAI для @{account} ===")
    for stage, v in stages.items():
        label = f"  {stage} ({v['model']}):"
        print(f"{label:<28} {v['tokens']:>6} токенов  ${v['cost_usd']:.4f}")
    print(f"  {'─' * 37}")
    print(f"  {'Итого OpenAI:':<26} {total_tokens:>6} токенов  ${total_cost:.4f}")
    print(f"  Apify: см. console.apify.com")


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
