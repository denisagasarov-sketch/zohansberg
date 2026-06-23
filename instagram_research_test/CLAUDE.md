# Instagram Competitor Research Pipeline

## Репо
/Users/agasarov_da/zohansberg-instagram-test/
Ветка: claude/instagram-competitor-research-test-8mA3d

## Архитектура
- pipeline/core/      — config, paths, apify_client, openai_client, sheets_client
- pipeline/stages/    — один файл = один стейдж
- run.py              — оркестратор
- scripts/            — старый код (только читать, не трогать)

## Правила
- Импорты только из pipeline.core.*
- Пути только через paths.raw() и paths.normalized()
- dry_run поддерживать везде
- Функция называется analyze() или collect() с сигнатурой (username: str, dry_run: bool = False) -> dict

## Стейджи
- 01 collect_profile.py        — готов
- 02 collect_pinned_details.py — готов
- 03 analyze_pinned_posts.py   — готов
- 04 analyze_pinned_visuals.py — готов
- 05 analyze_bio.py            — готов
- 06 classify_profile_link.py  — готов
- 07 analyze_landing.py        — готов
- 08 collect_highlights.py     — готов
- 09 collect_stories.py        — готов
- 10 analyze_highlights.py     — готов
- 11 collect_reels.py          — готов
- 12 analyze_reels.py          — готов
- 13 collect_posts.py          — готов
- 14 analyze_posts.py          — готов
- 15 build_payload.py          — готов
- 16 write_sheets.py           — готов
