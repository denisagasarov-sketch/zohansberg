"""Core: обёртка над Apify API."""

import time
import requests
from pipeline.core.config import get_apify_token

APIFY_BASE = "https://api.apify.com/v2"


def run_actor(actor_id: str, input_data: dict, timeout_secs: int = 300) -> list:
    """
    Запускает Apify actor синхронно, возвращает список items из датасета.
    actor_id: например 'apify/instagram-scraper'
    """
    token = get_apify_token()
    actor_slug = actor_id.replace("/", "~")

    resp = requests.post(
        f"{APIFY_BASE}/acts/{actor_slug}/runs",
        params={"token": token},
        json=input_data,
        timeout=30,
    )
    resp.raise_for_status()
    run_id = resp.json()["data"]["id"]

    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        status_resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": token},
            timeout=15,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} завершился со статусом: {status}")
        time.sleep(5)
    else:
        raise TimeoutError(f"Apify run {run_id} не завершился за {timeout_secs}s")

    dataset_id = status_resp.json()["data"]["defaultDatasetId"]
    items_resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": token, "format": "json", "clean": "true"},
        timeout=60,
    )
    items_resp.raise_for_status()
    return items_resp.json()
