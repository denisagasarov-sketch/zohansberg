# Stage 3B-2 local run instructions

## What this stage does

Calls OpenAI API (gpt-4.1-mini) with prepared images from Stage 3B-1.
Makes exactly 2 API requests:
1. Post analysis — 1 image + caption
2. Highlight sample analysis — up to 6 images/frames

Returns structured JSON analysis. Validates schema. Saves report.

## Prerequisites

Before running, confirm:
- [ ] Stage 3B-1 ran locally — `data/normalized/stage3b1_openai_input_preview.json` exists
- [ ] `readiness.can_run_stage3b2_openai_call = true` in that file
- [ ] `output/openai_inputs/stage3b1/images/` contains prepared images
- [ ] `OPENAI_API_KEY` is set in `.env`
- [ ] `.gitignore` contains: `.env`, `data/raw/`, `output/`, `analysis/openai_responses/`

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

source .venv/bin/activate

python scripts/stage3b2_run_local.py

cat report/stage_3b2_openai_analysis_test_report.md
```

## Output files created

```
analysis/
  content_analysis_test.json              ← validated post analysis JSON
  highlights_analysis_test.json           ← validated highlight analysis JSON
  openai_responses/
    post_analysis_response.json           ← raw OpenAI response (post)
    highlight_analysis_response.json      ← raw OpenAI response (highlight)
report/
  stage_3b2_openai_analysis_test_report.md
```

## Files NOT committed (gitignored)

```
analysis/openai_responses/   ← in .gitignore
output/                      ← in .gitignore
data/raw/                    ← in .gitignore
.env                         ← in .gitignore
```

## If model is unavailable

The script uses `MODEL = "gpt-4.1-mini"`.
If the model is not available on your OpenAI plan, the script will stop with a clear error.
Do not change the model name yourself — confirm with the project owner first.

## If preflight fails

The script checks all conditions before calling OpenAI.
If any check fails, no API call is made and the error is written to the report.
Fix the indicated issue and re-run.
