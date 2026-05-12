# Claude Master Rules — Instagram Competitor Research Pipeline

## 1. Working branch

Always work only in:

claude/instagram-competitor-research-test-8mA3d

Before any work, run:

git branch --show-current

If the current branch is different:
- stop;
- do not edit files;
- do not commit;
- do not push;
- tell the user that the current branch is wrong.

Never create new branches unless the user explicitly asks.

## 2. Read project rules first

Before any task, read:

- instagram_research_test/CLAUDE_WORKFLOW.md
- instagram_research_test/CLAUDE_MASTER_RULES.md

If a task has extra rules, follow both.
If rules conflict, follow the stricter rule.

## 3. Default execution mode

For simple explanation tasks:
- do not edit files;
- answer in chat.

For implementation tasks:
- create or edit only the files required by the task;
- do not run expensive or external operations unless explicitly allowed.

For research/planning tasks:
- prefer answering in chat;
- create a file only if the user asks or if the task explicitly says to create one.

For checker scripts:
- create dry-run mode;
- do not run real Apify/OpenAI after creating the script unless the user explicitly asks.

## 4. Commit policy

Safe project files may be committed if the task is completed and the changed files are only safe files.

Safe files:

- scripts/*.py
- prompts/*.md
- report/*_local_run_instructions.md
- report/*_audit*.md
- report/*_registry*.md
- report/*_plan*.md
- report/*_needed*.md
- config/*.json
- config/*.md
- docs/*.md
- README.md
- CLAUDE_WORKFLOW.md
- CLAUDE_MASTER_RULES.md
- .gitignore, only if needed to protect runtime outputs

Also commit safe project knowledge when it appears:

- actor payload examples without tokens;
- actor capability notes;
- input schema notes;
- field mapping notes;
- acceptance criteria;
- registry files;
- local run instructions.

Preferred files for safe project knowledge:

- config/actors_registry.json
- report/actor_capabilities_registry.md

Never commit unsafe/runtime files:

- .env
- API keys / tokens / secrets
- data/raw/
- data/normalized/
- analysis/
- analysis/openai_responses/
- output/
- downloaded media
- base64 dumps
- generated HTML reports, unless explicitly requested
- generated XLSX/ODS reports, unless explicitly requested
- large raw JSON outputs

## 5. Git commands

Never use:

git add .
git add -A

Always stage files explicitly:

git add path/to/file1 path/to/file2

Before commit, run and show:

git status --short
git diff --name-only
git diff --cached --name-only

If a forbidden file is staged:
- stop;
- unstage it;
- do not commit until staged files are safe.

Push only to:

origin claude/instagram-competitor-research-test-8mA3d

## 6. Runtime outputs

Runtime outputs are useful locally, but must not be committed.

Runtime outputs include:

- data/raw/
- data/normalized/
- analysis/
- output/
- generated reports
- downloaded media

If a real run creates runtime outputs, mention them in the final response:

- what was created;
- where it is;
- that it was not committed.

## 7. External services

Do not run these unless the task explicitly allows it:

- OpenAI
- Apify
- scraping
- media download
- website crawling
- Telegram/bot interaction

For every checker script, implement --dry-run first.

Dry-run must:
- validate tokens without printing them;
- show planned payloads;
- show planned external calls;
- not call external services;
- not create raw outputs.

## 8. Secrets

Never print:

- APIFY_TOKEN
- OPENAI_API_KEY
- any API key
- any secret from .env

Allowed token output:

- "found"
- "format OK"
- "missing"
- "invalid"

Never output the actual token.

## 9. Actor registry policy

If an actor payload, input schema, or capability is discovered, save it as safe project knowledge.

Use:

config/actors_registry.json

or:

report/actor_capabilities_registry.md

Do not rely only on chat memory.

Actor registry entries should include:

- actor name
- purpose
- tested account
- tested action/mode
- safe input payload example without tokens
- confirmed output fields
- limitations
- recommended use
- fallback actor, if any
- date or run context if useful

Never include:
- tokens;
- raw media URLs if too long;
- full raw outputs;
- private secrets.

## 10. If payload schema is unknown

Do not create a useless checker where all actions are SKIPPED.

If payload schema is unknown:

1. Search project files first.
2. Search actor registry files.
3. Search reports and notes.
4. If still unknown, stop.
5. Tell the user exactly what to copy from Apify UI:
   - actor name;
   - latest run;
   - Input JSON;
   - API / JSON input example;
   - action/mode examples.

Do not guess payloads.
Do not make blind Apify calls.

## 11. Stage design rules

Do not build large stages blindly.

Use small gates:

- schema check first;
- compatibility check second;
- collector third;
- analyzer fourth;
- table writer last.

Every stage should have:

- clear inputs;
- clear outputs;
- dry-run if external calls are involved;
- normalized JSON;
- source_refs;
- confidence/status fields;
- local run instructions.

## 12. Field status format

For data that may later go into XLSX, use this wrapper:

{
  "value": "...",
  "data_status": "ok|partial|missing|manual_needed",
  "source_ref": "...",
  "confidence": "high|medium|low|null",
  "notes": "..."
}

Rules:

- direct actor field: ok / high
- manual direct copy: ok / high
- rule-based inference: partial / medium or low
- needs manual input: manual_needed
- unavailable and no clear source: missing

Do not present inferred fields as facts.

## 13. Language policy

Human-readable analytical fields should be in Russian.

Technical enum values may remain in English if the schema requires it.

Do not translate:

- IDs
- URLs
- file paths
- source_refs
- enum values required by code

## 14. Final response format

At the end of every task, report:

- current branch;
- files created/changed;
- commands run;
- whether OpenAI was run;
- whether Apify was run;
- whether .env was touched;
- runtime outputs created, if any;
- whether commit/push was done;
- commit hash, if any.

If nothing was committed, say so.
