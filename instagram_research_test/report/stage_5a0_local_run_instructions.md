# Stage 5A-0 — Actor Profile Schema Check

## Что делает

Проверяет, какие профильные и pinned-поля реально возвращает `apify/instagram-scraper`
для аккаунта `vlada_kliuiko`. Тестирует три режима: `details`, `profiles`, `posts_fallback`.

После запуска будет ясно:
- можно ли автоматически собирать bio;
- можно ли собирать ссылку из bio и имя профиля;
- можно ли собирать followers/following/posts count;
- можно ли автоматически определять закреплённые посты;
- какие данные придётся вводить вручную.

## Что НЕ делает

- Не анализирует конкурента.
- Не заполняет таблицу.
- Не вызывает OpenAI.
- Не скачивает media.
- Не анализирует highlights.

## Требования

- Python 3.11+
- Установленные зависимости: `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# Safety preview — Apify НЕ вызывается
python scripts/stage5a0_actor_profile_schema_check.py --dry-run

# Реальный запуск — 3 actor calls
python scripts/stage5a0_actor_profile_schema_check.py

# Посмотреть итоговый summary
cat data/normalized/stage5a0_actor_schema_check.json
```

## Выходные файлы

После реального запуска:

```
data/raw/stage5a0_profile_details_raw.json          ← raw output mode details
data/raw/stage5a0_profile_profiles_raw.json         ← raw output mode profiles
data/raw/stage5a0_profile_posts_fallback_raw.json   ← raw output mode posts
data/normalized/stage5a0_actor_schema_check.json    ← итоговый summary
```

Файлы в `data/raw/` — в `.gitignore`, не коммитятся.
`data/normalized/stage5a0_actor_schema_check.json` — коммитится.

## Как интерпретировать результат

**`can_use_actor_for_profile: true`**
Актор возвращает достаточно профильных полей. Stage 5A-1 можно строить на actor output.

**`can_use_actor_for_profile: false`**
Актор не даёт нужных полей. Нужен ручной ввод через `data/input/profile_manual.json`.

**`manual_needed`**
Список логических полей, которые актор не вернул. Каждое нужно будет ввести вручную.
Возможные значения: `bio_text`, `full_name`, `username`, `external_url`,
`followers_count`, `following_count`, `posts_count`, `pinned_posts`.

**`pinned_detection.available: true`**
Закреплённые посты можно определять автоматически.
Поле и режим указаны в `pinned_detection.source` и `pinned_detection.field`.

**`pinned_detection.available: false`**
Закреплённые посты нужно вводить вручную через `data/input/pinned_posts_manual.json`.

**Статусы по каждому mode:**
- `OK` — актор вернул ≥1 item
- `FAIL` — актор вернул 0 items или бросил ошибку
- `SKIPPED` — APIFY_TOKEN невалиден, запуск не выполнялся
- `DRY_RUN` — вызов не производился (режим --dry-run)

## Следующий шаг

Если `can_use_actor_for_profile: true`:
→ Создать Stage 5A-1 на основе лучшего mode из `modes_tested`.

Если `can_use_actor_for_profile: false`:
→ Заполнить `data/input/profile_manual.json` вручную, затем Stage 5A-1.

Если `pinned_detection.available: false`:
→ Заполнить `data/input/pinned_posts_manual.json` вручную.
