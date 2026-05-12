# Analysis Language Policy — Russian

## Goal

All human-readable analytical fields must be written in Russian from the first OpenAI analysis step.

The pipeline must not rely on final-stage translation. Stage 4B should produce Russian analytical JSON. Stage 4C should synthesize Russian JSON. Stage 4D should only render Russian data into HTML.

## Write in Russian

All human-readable fields must be written in Russian:

- topic
- format
- hook
- main_message
- audience_pain
- audience_desire
- barrier_or_objection
- cta
- offer
- social_proof
- observed_facts.caption_facts
- observed_facts.visual_facts
- observed_facts.visible_text
- inferred_meanings.summary
- inferred_meanings.trust_mechanics
- evidence
- limitations
- visual_summary
- key_evidence
- cta_patterns
- offer_patterns
- social_proof_patterns
- trust_mechanics
- weak_spots
- ideas_to_adapt
- report labels
- section summaries

## Do not translate technical fields

Do not translate or rewrite:

- status
- confidence
- funnel_role
- main_roles
- account
- content_id
- request_id
- story_id
- story_numbers
- highlight_id
- url
- file paths
- source_refs
- post IDs
- batch IDs
- enum values

## Enum values must stay exactly as schema requires

status:
- OK
- PARTIAL
- FAIL

confidence:
- high
- medium
- low

funnel_role:
- reach
- trust
- warmup
- sales
- engagement
- leadgen
- expertise
- unknown

main_roles:
- social_proof
- student_results
- course_trust
- community
- education
- reviews
- cases
- faq
- product
- pricing
- about
- process
- backstage
- lead_magnet
- unknown

## Fixed Russian values

Use these fixed Russian values in human-readable fields:

- not found → Не найдено
- not enough evidence → Недостаточно данных
- no explicit CTA found → Прямой призыв к действию не найден
- no explicit offer found → Явный оффер не найден
- no social proof found → Социальное доказательство не найдено

## Evidence rules

Do not invent.

Separate:
- observed facts: what is directly visible in caption, text, images or frames
- inferred meanings: analytical interpretation based on observed facts

Every analytical conclusion must be supported by evidence.

If evidence is weak, write:
Недостаточно данных

If CTA, offer or social proof is absent, write:
Не найдено

## Style

Write in Russian.

Use a dry, practical, analytical tone.

No marketing fluff.

No overclaiming.

No emotional praise.

No unsupported claims.

No rewriting source_refs.

No translating IDs, URLs or file paths.

## Output rule

Return only valid JSON when the script asks for JSON.

No markdown.

No prose outside JSON.
