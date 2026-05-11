import os
import json
from pathlib import Path

BASE = Path(__file__).parent.parent

def check():
    results = {}

    env_path = BASE / ".env"
    results[".env"] = "found" if env_path.exists() else "missing"

    token_found = False
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("APIFY_TOKEN=") and len(line.split("=", 1)[1].strip()) > 0:
                token_found = True
                break
    results["APIFY_TOKEN"] = "found" if token_found else "missing"

    payloads_path = BASE / "data" / "actor_payloads.json"
    results["actor_payloads.json"] = "found" if payloads_path.exists() else "missing"

    stage_2_allowed = False
    if payloads_path.exists():
        try:
            data = json.loads(payloads_path.read_text())
            stage_2_allowed = bool(data.get("stage_2_allowed", False))
        except Exception:
            pass
    results["stage_2_allowed"] = str(stage_2_allowed).lower()

    for key, val in results.items():
        print(f"{key}: {val}")

    ok = (
        results[".env"] == "found"
        and results["APIFY_TOKEN"] == "found"
        and results["actor_payloads.json"] == "found"
        and results["stage_2_allowed"] == "true"
    )
    if not ok:
        raise SystemExit("check_env failed — fix issues above before running Stage 2")

if __name__ == "__main__":
    check()
