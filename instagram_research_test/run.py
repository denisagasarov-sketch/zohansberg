"""Единственная точка входа нового пайплайна.

Использование:
  python3 run.py --account vlada_kliuiko
  python3 run.py --account vlada_kliuiko --stages 01,05,08
  python3 run.py --account vlada_kliuiko --from-stage 11 --dry-run
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from typing import Callable

from pipeline.core.config import get_account
from pipeline.stages.analyze_bio import analyze as analyze_bio
from pipeline.stages.analyze_posts import analyze as analyze_posts
from pipeline.stages.analyze_reels import analyze as analyze_reels
from pipeline.stages.build_payload import build as build_payload
from pipeline.stages.collect_highlights import collect as collect_highlights
from pipeline.stages.collect_posts import collect as collect_posts
from pipeline.stages.collect_profile import collect as collect_profile
from pipeline.stages.collect_reels import collect as collect_reels
from pipeline.stages.collect_stories import collect as collect_stories
from pipeline.stages.collect_pinned_details import collect as collect_pinned_details
from pipeline.stages.analyze_pinned_posts import analyze as analyze_pinned_posts
from pipeline.stages.analyze_pinned_visuals import analyze as analyze_pinned_visuals
from pipeline.stages.classify_profile_link import classify as classify_profile_link
from pipeline.stages.analyze_landing import analyze as analyze_landing
from pipeline.stages.analyze_highlights import analyze as analyze_highlights
from pipeline.stages.prepare_sheets import prepare as prepare_sheets
from pipeline.stages.write_sheets import write as write_sheets
from pipeline.core.meta import update_meta, STAGE_TO_BLOCK

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Stage:
    number: str
    name: str
    runner: Callable[[str, bool], dict]


def _profile(username: str, dry_run: bool) -> dict:
    return collect_profile(username=username, dry_run=dry_run)


def _pinned_details(username: str, dry_run: bool) -> dict:
    return collect_pinned_details(username=username, dry_run=dry_run)


def _analyze_pinned_posts(username: str, dry_run: bool) -> dict:
    return analyze_pinned_posts(username=username, dry_run=dry_run)


def _analyze_pinned_visuals(username: str, dry_run: bool) -> dict:
    return analyze_pinned_visuals(username=username, dry_run=dry_run)


def _classify_link(username: str, dry_run: bool) -> dict:
    return classify_profile_link(username=username, dry_run=dry_run)


def _analyze_landing(username: str, dry_run: bool) -> dict:
    return analyze_landing(username=username, dry_run=dry_run)


def _analyze_highlights(username: str, dry_run: bool) -> dict:
    return analyze_highlights(username=username, dry_run=dry_run)


def _bio(username: str, dry_run: bool) -> dict:
    return analyze_bio(username=username, dry_run=dry_run)


def _highlights(username: str, dry_run: bool) -> dict:
    return collect_highlights(username=username, limit=None, dry_run=dry_run)


def _stories(username: str, dry_run: bool) -> dict:
    return collect_stories(username=username, limit=None, dry_run=dry_run)


def _reels(username: str, dry_run: bool) -> dict:
    return collect_reels(username=username, dry_run=dry_run)


def _analyze_reels(username: str, dry_run: bool) -> dict:
    return analyze_reels(username=username, dry_run=dry_run)


def _env_int(name: str, default: int) -> int:
    """Читает целочисленную env-переменную, при пустом/некорректном значении — default."""
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw.strip() else default
    except (TypeError, ValueError):
        return default


def _posts(username: str, dry_run: bool) -> dict:
    # Настройки из бота (PIPELINE_*); дефолты совпадают с прежним поведением:
    # period / 6 мес / все типы / 30 шт.
    content_mode = os.environ.get("PIPELINE_CONTENT_MODE", "period") or "period"
    months_back = _env_int("PIPELINE_MONTHS_BACK", 6)
    target_count = _env_int("PIPELINE_TARGET_COUNT", 30)
    post_types_raw = os.environ.get("PIPELINE_POST_TYPES", "")
    post_types = [p.strip() for p in post_types_raw.split(",") if p.strip()] or None
    # Необязательный фильтр: shortCode постов, которые не нужно собирать.
    # Сейчас ботом не задействуется (актуализация идёт через upsert-слияние в стейдже 16).
    exclude_raw = os.environ.get("PIPELINE_EXCLUDE_SHORTCODES", "")
    exclude_codes = [c.strip() for c in exclude_raw.split(",") if c.strip()] or None
    return collect_posts(
        username=username,
        limit=200,
        months_back=months_back,
        dry_run=dry_run,
        post_types=post_types,
        content_mode=content_mode,
        target_count=target_count,
        exclude_codes=exclude_codes,
    )


def _analyze_posts(username: str, dry_run: bool) -> dict:
    content_filter = os.environ.get("PIPELINE_CONTENT_FILTER", "all") or "all"
    return analyze_posts(username=username, dry_run=dry_run, content_filter=content_filter)


def _build_payload(username: str, dry_run: bool) -> dict:
    return build_payload(username=username, dry_run=dry_run)


def _prepare_sheets(username: str, dry_run: bool) -> dict:
    return prepare_sheets(username=username, dry_run=dry_run)


def _write_sheets(username: str, dry_run: bool) -> dict:
    return write_sheets(username=username, dry_run=dry_run)


STAGES = (
    Stage("01", "collect_profile", _profile),
    Stage("02", "collect_pinned_details", _pinned_details),
    Stage("03", "analyze_pinned_posts", _analyze_pinned_posts),
    Stage("04", "analyze_pinned_visuals", _analyze_pinned_visuals),
    Stage("05", "analyze_bio", _bio),
    Stage("06", "classify_profile_link", _classify_link),
    Stage("07", "analyze_landing", _analyze_landing),
    Stage("08", "collect_highlights", _highlights),
    Stage("09", "collect_stories", _stories),
    Stage("10", "analyze_highlights", _analyze_highlights),
    Stage("11", "collect_reels", _reels),
    Stage("12", "analyze_reels", _analyze_reels),
    Stage("13", "collect_posts", _posts),
    Stage("14", "analyze_posts", _analyze_posts),
    Stage("15", "build_payload", _build_payload),
    Stage("15b", "prepare_sheets", _prepare_sheets),
    Stage("16", "write_sheets", _write_sheets),
)
STAGES_BY_NUMBER = {stage.number: stage for stage in STAGES}


def _normalize_stage_number(value: str) -> str:
    stripped = value.strip()
    if stripped.isdigit():
        return f"{int(stripped):02d}"
    # Буквенно-цифровые номера вида "15b" — возвращаем как есть
    import re as _re
    if _re.match(r"^\d+[a-z]+$", stripped):
        return stripped
    raise ValueError(f"Некорректный номер стейджа: {value!r}")


def select_stages(stages: str | None, from_stage: str | None) -> list[Stage]:
    if stages:
        requested = [_normalize_stage_number(value) for value in stages.split(",") if value.strip()]
        if not requested:
            raise ValueError("--stages не содержит номеров")
        unavailable = [number for number in requested if number not in STAGES_BY_NUMBER]
        if unavailable:
            available = ", ".join(stage.number for stage in STAGES)
            raise ValueError(
                f"Стейджи ещё не перенесены или неизвестны: {', '.join(unavailable)}. "
                f"Доступны: {available}"
            )
        return [STAGES_BY_NUMBER[number] for number in requested]

    if from_stage:
        start = _normalize_stage_number(from_stage)
        if start not in STAGES_BY_NUMBER:
            available = ", ".join(stage.number for stage in STAGES)
            raise ValueError(f"Стейдж {start} недоступен. Доступны: {available}")
        start_index = next(index for index, stage in enumerate(STAGES) if stage.number == start)
        return list(STAGES[start_index:])

    return list(STAGES)


def run_pipeline(
    username: str,
    selected: list[Stage],
    dry_run: bool = False,
    write_mode: str = "replace",
) -> list[dict]:
    get_account(username)
    results = []

    logger.info(
        "Pipeline | @%s | stages=%s | dry_run=%s | write_mode=%s",
        username,
        ",".join(stage.number for stage in selected),
        dry_run,
        write_mode,
    )
    for index, stage in enumerate(selected, start=1):
        logger.info("[%d/%d] %s %s", index, len(selected), stage.number, stage.name)
        try:
            if stage.number == "16":
                result = write_sheets(username=username, dry_run=dry_run, write_mode=write_mode)
            else:
                result = stage.runner(username, dry_run)
        except Exception as error:
            # Устойчивость: ошибка одного стейджа не роняет весь прогон.
            # У реального конкурента часто пуст какой-то блок (нет закрепов,
            # хайлайтов, ссылки, протухла кука) — продолжаем со следующего.
            logger.exception("Stage %s %s failed: %s", stage.number, stage.name, error)
            results.append({
                "number": stage.number,
                "name": stage.name,
                "status": "failed",
                "error": str(error).splitlines()[0] if str(error).strip() else repr(error),
                "result": None,
            })
            continue
        results.append({
            "number": stage.number,
            "name": stage.name,
            "status": "dry_run" if dry_run else "ok",
            "result": result,
        })
        # update_meta — только для успешно завершённых стейджей
        if not dry_run:
            block = STAGE_TO_BLOCK.get(stage.number)
            if block:
                update_meta(username, block)

    failures = [item for item in results if item["status"] == "failed"]

    print("\n=== Pipeline Summary ===")
    print(f"Аккаунт: @{username}")
    for item in results:
        line = f"{item['number']} {item['name']}: {item['status']}"
        if item["status"] == "failed":
            line += f" — {item.get('error', '')}"
        print(line)
    if failures:
        print(f"\n⚠️ Стейджей с ошибкой: {len(failures)} из {len(results)}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram competitor research pipeline")
    parser.add_argument("--account", required=True, help="Instagram username")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--stages", help="Номера через запятую, например 01,05,08")
    selection.add_argument("--from-stage", help="Запустить с указанного номера")
    parser.add_argument("--dry-run", action="store_true", help="Не вызывать внешние API")
    parser.add_argument(
        "--write-mode", default="replace", choices=["replace", "upsert"],
        help="Режим записи в таблицу: replace (перезаписать строки аккаунта) или "
             "upsert (актуализировать Посты/Reels по ссылке, история копится)",
    )
    args = parser.parse_args()

    try:
        selected = select_stages(args.stages, args.from_stage)
        results = run_pipeline(args.account, selected, args.dry_run, write_mode=args.write_mode)
    except (ValueError, FileNotFoundError, EnvironmentError, RuntimeError) as error:
        parser.error(str(error))
        return

    # Ненулевой код выхода, если хотя бы один стейдж упал —
    # чтобы бот показал предупреждение «завершён с ошибками».
    if any(item["status"] == "failed" for item in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
