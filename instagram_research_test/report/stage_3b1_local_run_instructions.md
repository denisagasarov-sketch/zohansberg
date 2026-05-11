# Stage 3B-1 local run instructions

## What this stage does

Prepares images and frames for OpenAI analysis.
**Does NOT call OpenAI API.**

Actions:
- validates local raw files from Stage 2
- selects 1 test post + up to 5 highlight stories
- extracts frames from any video media (max 5 frames per video)
- compresses all selected images to max 1280px / JPEG 85
- saves prepared files to `output/openai_inputs/stage3b1/`
- creates input preview JSON and markdown report

## Prerequisites

Before running, confirm:
- [ ] Stage 2 ran locally — `data/raw/posts_test_raw.json` not empty
- [ ] Stage 2B ran locally — `data/raw/highlight_stories_manual_test_raw.json` not empty
- [ ] Stage 3A ran locally — `data/normalized/stage3a_media_manifest.json` exists with downloaded files
- [ ] Dependencies installed: `pillow`, `opencv-python`

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

source .venv/bin/activate

python scripts/stage3b1_run_local.py

cat report/stage_3b1_openai_input_preview.md
```

## Output files created

```
data/normalized/stage3b1_openai_input_preview.json   ← full input preview
report/stage_3b1_openai_input_preview.md              ← human-readable report
output/openai_inputs/stage3b1/
  frames/   ← extracted video frames
  images/   ← compressed images ready for OpenAI
```

## If pillow or opencv is missing

```bash
pip install pillow opencv-python
```

## If raw files are still empty

Re-run Stage 2 and Stage 3A first:

```bash
python scripts/run_scraping_test.py
python scripts/test_highlight_stories_manual.py
python scripts/stage3a_run_local.py
```

Then re-run Stage 3B-1.

## Next step after this

If report shows `can run OpenAI call: yes` → proceed to Stage 3B-2.
Stage 3B-2 will send prepared files to OpenAI Vision (gpt-4o) and save responses.
