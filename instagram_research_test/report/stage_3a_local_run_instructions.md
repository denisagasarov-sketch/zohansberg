# Stage 3A local run instructions

## Prerequisites

Before running, confirm:
- [ ] Stage 2 ran locally and produced real data in `data/raw/`
- [ ] `data/raw/posts_test_raw.json` is not empty (more than `[]`)
- [ ] `data/raw/highlight_stories_manual_test_raw.json` is not empty
- [ ] Python virtual environment exists and dependencies are installed

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

source .venv/bin/activate

python scripts/stage3a_run_local.py

cat report/stage_3a_media_download_test_report.md
```

## What each script does

| Script | Action |
|---|---|
| `stage3a_check_raw_inputs.py` | Checks raw files exist, not empty, have media fields. Saves `data/normalized/stage3a_raw_inputs_check.json` |
| `stage3a_download_media_sample.py` | Downloads 1 post image, 1 post video (if exists), 1 story image, 1 story video (if exists). Saves to `output/media/stage3a/`. Saves manifest + error log. |
| `stage3a_create_report.py` | Reads check + manifest, writes `report/stage_3a_media_download_test_report.md` |
| `stage3a_run_local.py` | Runs all three steps in order. Stops on first failure. |

## Output files created

```
data/normalized/stage3a_raw_inputs_check.json
data/normalized/stage3a_media_manifest.json
data/normalized/stage3a_media_download_errors.json
output/media/stage3a/posts/       ← post image + video sample
output/media/stage3a/highlights/  ← story image + video sample
report/stage_3a_media_download_test_report.md
```

## If venv doesn't exist yet

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## If raw files are empty

Raw files are gitignored. If they show `[]`, re-run Stage 2 scraping first:

```bash
python scripts/run_scraping_test.py
python scripts/test_highlight_stories_manual.py
```

Then re-run Stage 3A.
