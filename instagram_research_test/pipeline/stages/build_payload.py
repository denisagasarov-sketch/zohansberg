"""Stage 15: собирает все normalized/*.json предыдущих стейджей в единый payload.json."""

import argparse
import json
import logging
from datetime import datetime, timezone

from pipeline.core.config import get_account
from pipeline.core.paths import normalized

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _load_sources(username: str) -> dict:
    norm_dir = normalized(username, "placeholder").parent
    sources = {}
    if not norm_dir.exists():
        return sources
    for path in sorted(norm_dir.glob("*.json")):
        if path.stem == "payload":
            continue
        try:
            sources[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Не удалось прочитать %s: %s", path.name, e)
            sources[path.stem] = None
    return sources


def build(username: str, dry_run: bool = False) -> dict:
    """Загружает все normalized/*.json и сохраняет normalized/payload.json."""
    get_account(username)

    logger.info("[15] build_payload | @%s | dry_run=%s", username, dry_run)

    if dry_run:
        logger.info("[DRY RUN] Файлы не записываются")
        return {"dry_run": True, "payload": {}}

    sources = _load_sources(username)
    loaded = [k for k, v in sources.items() if v is not None]
    failed = [k for k, v in sources.items() if v is None]

    if failed:
        logger.warning("Не загружены файлы: %s", failed)

    payload = {
        "account": username,
        "stage": "stage15",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources_loaded": loaded,
        "sources_failed": failed,
        "data": sources,
    }

    output_path = normalized(username, "payload.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Stage 15: Build Payload | @{username} ===")
    print(f"Загружено источников: {len(loaded)} | ошибок: {len(failed)}")
    print(f"Сохранено: {output_path}")

    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 15: build payload")
    parser.add_argument("--account", required=True, help="Instagram username")
    parser.add_argument("--dry-run", action="store_true", help="Не записывать файлы")
    args = parser.parse_args()
    build(args.account, args.dry_run)
