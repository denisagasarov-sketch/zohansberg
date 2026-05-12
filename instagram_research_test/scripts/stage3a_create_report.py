import json
from pathlib import Path

BASE = Path(__file__).parent.parent

CHECK_PATH    = BASE / "data/normalized/stage3a_raw_inputs_check.json"
MANIFEST_PATH = BASE / "data/normalized/stage3a_media_manifest.json"
REPORT_PATH   = BASE / "report/stage_3a_media_download_test_report.md"

def load(path, label):
    if not path.exists():
        raise SystemExit(f"{label} not found at {path} — run previous steps first")
    return json.loads(path.read_text())

check    = load(CHECK_PATH, "stage3a_raw_inputs_check.json")
manifest = load(MANIFEST_PATH, "stage3a_media_manifest.json")

pr = check["posts_raw"]
sr = check["highlight_stories_raw"]
sm = manifest["summary"]

def yesno(v):
    return "yes" if v else "no"

errors_list = check.get("errors", [])
dl_errors = [i["error"] for i in manifest["post_media"] + manifest["highlight_media"] if i.get("error")]
all_errors = errors_list + dl_errors
errors_str = "\n".join(f"  - {e}" for e in all_errors) if all_errors else "  none"

# ── Verdict ───────────────────────────────────────────────────────────────────
raw_ok  = pr["status"] in ("OK", "PARTIAL") and pr["not_empty"]
raw_ok &= sr["status"] in ("OK", "PARTIAL") and sr["not_empty"]
dl_ok   = sm["status"] in ("OK", "PARTIAL")
any_post_dl = sm["post_image_downloaded"] or sm["post_video_downloaded"]
any_hl_dl   = sm["highlight_image_downloaded"] or sm["highlight_video_downloaded"]

if raw_ok and any_post_dl and any_hl_dl:
    verdict = "OK — можно переходить к Stage 3B: OpenAI analysis test"
elif raw_ok and (any_post_dl or any_hl_dl):
    verdict = "PARTIAL — часть media скачивается, но есть ограничения"
else:
    verdict = "FAIL — нельзя переходить к OpenAI, сначала исправить raw/media download"

# ── Recommendation ────────────────────────────────────────────────────────────
recs = []
if verdict.startswith("OK"):
    recs.append("- Можно переходить к Stage 3B.")
    what = []
    if sm["post_image_downloaded"]:
        what.append("post images")
    if sm["post_video_downloaded"]:
        what.append("post videos")
    if sm["highlight_image_downloaded"]:
        what.append("highlight story images")
    if sm["highlight_video_downloaded"]:
        what.append("highlight story videos")
    recs.append(f"- Через OpenAI можно анализировать: {', '.join(what)}.")
    recs.append("- Перед масштабированием: убедиться, что CDN URLs не истекают; для видео использовать кадры вместо полного файла.")
elif verdict.startswith("PARTIAL"):
    recs.append("- Stage 3B возможен частично — только для успешно скачанных media.")
    recs.append("- Проверить ошибки скачивания в stage3a_media_download_errors.json.")
    recs.append("- Возможно, часть URLs истекла — попробовать пересобрать raw data.")
else:
    recs.append("- Stage 3B запускать нельзя.")
    if not raw_ok:
        recs.append("- Сначала запустить локально run_scraping_test.py и test_highlight_stories_manual.py для пересбора raw данных.")
    else:
        recs.append("- Raw данные есть, но media URLs не скачиваются. Проверить errors_test.json.")

report = f"""# Stage 3A Media Download Test Report

## Scope

Stage 3A проверяет только:
- существуют ли локальные raw-файлы;
- не пустые ли они;
- есть ли media URLs;
- скачивается ли минимальный sample media.

Stage 3A НЕ проверяет:
- OpenAI analysis;
- content quality;
- marketing strategy;
- full media download;
- keyframes;
- all posts;
- all highlights.

## Raw inputs

- posts raw found: {yesno(pr['exists'])}
- posts count: {pr['items_count']}
- posts status: {pr['status']}
- highlight stories raw found: {yesno(sr['exists'])}
- stories count: {sr['items_count']}
- highlight stories status: {sr['status']}

## Media sample download

- post image downloaded: {yesno(sm['post_image_downloaded'])}
- post video downloaded: {yesno(sm['post_video_downloaded'])}
- highlight image downloaded: {yesno(sm['highlight_image_downloaded'])}
- highlight video downloaded: {yesno(sm['highlight_video_downloaded'])}
- total files downloaded: {sm['total_files_downloaded']}
- errors:
{errors_str}

## Final verdict

{verdict}

## Recommendation

{chr(10).join(recs)}
"""

REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
REPORT_PATH.write_text(report)
print(f"report saved: {REPORT_PATH.relative_to(BASE)}")
print(f"verdict: {verdict}")
