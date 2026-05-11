# Stage 4C local run instructions

## What this stage does

Local synthesis of Stage 4B outputs into a final one-account report.
**No OpenAI calls. No media downloads. No image processing.**

Steps run in order:
1. **stage4c_check_inputs** — validates all 5 post JSON and 8 batch JSON exist and are status OK
2. **stage4c_synthesize_highlight** — aggregates 8 highlight batch outputs into a single highlight summary (roles, patterns, evidence, score)
3. **stage4c_synthesize_account** — combines 5 posts + highlight summary into an account-level synthesis (offer, funnel roles, trust mechanics, weak spots, ideas to adapt)
4. **stage4c_create_final_report** — writes the final markdown report for vlada_kliuiko

## Prerequisites

Before running, confirm:
- [ ] Stage 4B completed with verdict `OK`
- [ ] `analysis/stage4b/posts/` contains 5 JSON files, all with `status: OK`
- [ ] `analysis/stage4b/highlight_batches/` contains 8 JSON files, all with `status: OK`
- [ ] `data/normalized/stage4b_posts_summary.json` exists with `status: OK`
- [ ] `data/normalized/stage4b_highlight_batches_summary.json` exists with `status: OK`

## Commands

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test

source .venv/bin/activate

python scripts/stage4c_run_local.py

cat report/final_one_account_analysis_vlada_kliuiko.md
cat analysis/stage4c/highlight_summary.json
cat analysis/stage4c/account_summary.json
```

## Output files created

```
data/normalized/
  stage4c_inputs_check.json          ← inputs validation result

analysis/stage4c/
  highlight_summary.json             ← aggregated highlight synthesis
  account_summary.json               ← full account synthesis with source_refs

report/
  final_one_account_analysis_vlada_kliuiko.md   ← final readable report
```

## Files NOT committed (gitignored)

```
analysis/         ← all analysis outputs
output/           ← all downloaded and prepared media
data/raw/         ← raw Apify scraper output
.env              ← API keys
```

## Traceability

Every conclusion in both JSON and markdown outputs has `source_refs`:
- `post_<content_id>` — references a specific post analysis
- `highlight_batch_<n>` — references a specific batch analysis
- `highlight_summary` — references the aggregated highlight
- `limitation` — marks a gap that comes from scope constraints, not from data

Conclusions without source_refs are excluded from the final report.

## If inputs check fails

- `stage4c_can_continue: false` → check `stage4c_inputs_check.json` for details
- A post or batch with `status: PARTIAL` → re-run Stage 4B with `--force` for that request
- Missing files → re-run Stage 4B (`stage4b_run_local.py`)

## If highlight synthesis status = PARTIAL

- `key_evidence < 5` → some batches returned low evidence; check batch JSON files
- Account synthesis still runs but may inherit PARTIAL status

## If highlight synthesis status = FAIL

- `batches_analyzed < 8` → one or more batch files missing or unreadable
- Account synthesis is aborted; re-run Stage 4B first

## Status rules

| Component | FAIL condition | PARTIAL condition |
|-----------|----------------|-------------------|
| highlight_summary | batches_analyzed < 8 | key_evidence < 5 |
| account_summary | highlight FAIL or most source_refs empty | primary_offer missing, trust_mechanics < 3, or social_proof_patterns < 3 |

## What Stage 4C does NOT do

- No OpenAI calls
- No Apify calls
- No media downloading or image processing
- No bio analysis
- No pinned posts analysis
- No website/bot funnel analysis
- No new scraping
