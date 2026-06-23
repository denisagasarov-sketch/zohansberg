# Stage 4B local run instructions

## What this stage does

Runs OpenAI analysis (gpt-4.1-mini) on the approved Stage 4A plan:
- 5 posts — one OpenAI request per post
- 8 highlight batches — one OpenAI request per batch
- 13 total OpenAI calls
- Saves structured JSON per post and per batch
- Creates technical report

Stage 4B does NOT do:
- Highlight synthesis
- Final account report
- Bio or pinned posts analysis
- New scraping or media downloading

## Prerequisites

Before running, confirm:
- [ ] Stage 4A completed with `plan_status: OK` and `can_run_stage4b: true`
- [ ] `data/normalized/stage4a_openai_plan.json` exists
- [ ] `output/openai_inputs/stage4/` contains prepared images/frames
- [ ] `OPENAI_API_KEY` is set in `.env`
- [ ] `.gitignore` contains: `.env`, `data/raw/`, `output/`, `analysis/openai_responses/`

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

source .venv/bin/activate

# Clear shell-injected secrets — .env must be the only source
unset OPENAI_API_KEY
unset APIFY_TOKEN
unset OPENAI_ORG_ID
unset OPENAI_PROJECT
unset OPENAI_BASE_URL

# Safety preview — no OpenAI calls, shows what would run
python scripts/stage4b_run_local.py --dry-run

# Real Stage 4B run
python scripts/stage4b_run_local.py

cat report/stage_4b_openai_analysis_report.md
```

## Output files created

```
analysis/
  stage4b/
    posts/
      post_<content_id>.json         ← validated post analysis JSON
    highlight_batches/
      highlight_batch_<n>.json       ← validated batch analysis JSON
  openai_responses/                  ← gitignored
    stage4b/
      posts/
        <request_id>_response.json
        <request_id>_error_traceback.txt  (if failed)
      highlight_batches/
        <request_id>_response.json
        <request_id>_error_traceback.txt  (if failed)

data/normalized/
  stage4b_plan_check.json
  stage4b_posts_summary.json
  stage4b_highlight_batches_summary.json

report/
  stage_4b_openai_analysis_report.md
```

## Files NOT committed (gitignored)

```
analysis/openai_responses/   ← raw OpenAI responses
output/                      ← all downloaded and prepared media
data/raw/                    ← raw Apify scraper output
.env                         ← API keys
```

## Resume behavior

Stage 4B supports resume without re-running successful requests:
- If `analysis/stage4b/posts/<id>.json` exists with `status: OK` → skipped
- If `status: PARTIAL` or `FAIL` → re-analyzed
- Use `--force` to re-run everything including existing OK outputs

```bash
# Re-run only failed/partial requests (default behavior)
python scripts/stage4b_run_local.py

# Re-run everything, including existing OK outputs
python scripts/stage4b_run_local.py --force
```

## If plan check fails

- `stage4b_can_continue: false` → fix errors listed in `stage4b_plan_check.json`
- Missing prepared files → re-run Stage 4A (`stage4a_run_local.py`)
- Invalid API key → check `.env`, confirm key starts with `sk-`

## If some posts or batches fail

- Check `analysis/openai_responses/stage4b/` for error tracebacks
- Re-run without `--force` to retry only failed items
- Common causes: OpenAI rate limit, timeout, malformed response JSON
- If a single request keeps failing, check its `prepared_paths` exist on disk

## Model

```
MODEL = "gpt-4.1-mini"
```

Do not change the model name without confirming with the project owner.

## Next step

After Stage 4B completes with verdict `OK` or `PARTIAL`:

Stage 4C will perform:
- Highlight synthesis across all 8 batch outputs
- Final one-account report for `vlada_kliuiko`
