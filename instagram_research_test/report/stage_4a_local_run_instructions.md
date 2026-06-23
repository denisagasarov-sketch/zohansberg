# Stage 4A local run instructions

## What this stage does

Prepares all media (5 posts + 57 highlight stories) for full OpenAI analysis.

Steps run in order:
1. **stage4a_check_inputs** — validates raw data files and prior stage outputs
2. **stage4a_prepare_media** — downloads, compresses images, extracts video frames for all posts and stories
3. **stage4a_create_openai_plan** — batches prepared inputs into OpenAI requests; validates against limits
4. **stage4a_create_report** — writes `report/stage_4a_media_and_openai_plan.md`

No OpenAI API calls are made in Stage 4A.

## Prerequisites

Before running, confirm:
- [ ] `data/raw/posts_test_raw.json` exists and has 5 items
- [ ] `data/raw/highlight_stories_manual_test_raw.json` exists and has 57 items
- [ ] `data/normalized/stage3a_media_manifest.json` exists
- [ ] `data/normalized/stage3b1_openai_input_preview.json` exists
- [ ] `.gitignore` contains: `.env`, `data/raw/`, `output/`, `analysis/openai_responses/`

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

# Clear any shell-injected secrets to ensure .env is the source of truth
unset OPENAI_API_KEY
unset APIFY_TOKEN

source .venv/bin/activate

python scripts/stage4a_run_local.py

cat report/stage_4a_media_and_openai_plan.md
```

## Output files created

```
data/normalized/
  stage4a_inputs_check.json        ← inputs validation result
  stage4a_media_manifest.json      ← per-post and per-story prepared inputs
  stage4a_media_errors.json        ← download/processing errors (if any)
  stage4a_openai_plan.json         ← batched OpenAI request plan

report/
  stage_4a_media_and_openai_plan.md

output/media/stage4/               ← downloaded media files (gitignored)
output/openai_inputs/stage4/       ← compressed/resized images for OpenAI (gitignored)
```

## Files NOT committed (gitignored)

```
output/                            ← all downloaded and prepared media
data/raw/                          ← raw Apify scraper output
.env                               ← API keys
analysis/openai_responses/         ← OpenAI raw responses
```

## Plan limits

| Limit | Value |
|-------|-------|
| Max total OpenAI requests | 15 |
| Max images per request | 10 |
| Max payload per request | 20 MB |
| Max total prepared inputs | 120 |

Expected totals: 5 post requests + 8 highlight batches (57 ÷ 8) + 1 synthesis = **14 requests**.

## If inputs check fails

- `stage4a_can_continue: false` → fix the listed errors, re-run prior stages, then retry
- Missing manifest → re-run Stage 3A locally first

## If media preparation has errors

- Check `data/normalized/stage4a_media_errors.json` for details
- Individual story failures are recorded but do not stop the stage
- If too many posts fail, re-run Stage 3A to re-download media

## If plan status is FAIL

- Review `summary.errors` in `stage4a_openai_plan.json`
- Common causes: too many images per batch, payload too large, total requests exceed 15
- Do NOT proceed to Stage 4B until `can_run_stage4b: true`

## Next step

After Stage 4A completes with `can_run_stage4b: true`:

```bash
python scripts/stage4b_run_local.py
```

Stage 4B will make real OpenAI API calls. Confirm with the project owner before running.
