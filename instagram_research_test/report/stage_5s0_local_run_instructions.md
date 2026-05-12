# Stage 5S-0 — Singhera Capability Check

## Что делает

Проверяет, может ли `singhera07/instagram-scraper` заменить или дополнить
текущие actors в Instagram competitor research pipeline.

Тестирует 4 capability-блока:

| Блок | Цель | Текущий actor |
|---|---|---|
| profile | Профиль (bio, url, counts) | apify/instagram-scraper (details) |
| posts_pinned | Посты + isPinned | apify/instagram-scraper (posts) |
| highlights_index | Список highlights | scrapio/instagram-highlights-scraper (заблокирован) |
| highlight_stories | Stories внутри highlight | igview-owner/instagram-highlights-stories-viewer |

## Что НЕ делает

- не анализирует контент
- не скачивает media
- не запускает OpenAI
- не заполняет XLSX
- не меняет Stage 4 / Stage 5A / Stage 5B

## Текущий статус payload schemas

**Строгое правило:** actor вызывается только если для его action найден
точный payload в project files. Угаданные payloads запрещены.

Результат поиска по проекту (scripts, data, report):

| Action | Статус | Причина |
|---|---|---|
| profile | SKIPPED | payload не найден в project files |
| posts_pinned | SKIPPED | payload не найден в project files |
| highlights_index | SKIPPED | action=highlights подтверждён пользователем (32 highlights), но параметр url/username не найден в project files |
| highlight_stories | SKIPPED | payload не найден в project files |

**Для включения action:** найти точный payload и заполнить `CONFIRMED_PAYLOADS`
в скрипте `scripts/stage5s0_check_singhera_capabilities.py`.

## Требования

- Python 3.11+
- `pip install apify-client python-dotenv`
- Заполненный `.env` с `APIFY_TOKEN=apify_api_...`

## Команды

```bash
cd /Users/agasarov_da/zohansberg-instagram-test/instagram_research_test
source .venv/bin/activate

# safety preview, без Apify calls
python scripts/stage5s0_check_singhera_capabilities.py --dry-run

# real capability check (только подтверждённые actions)
python scripts/stage5s0_check_singhera_capabilities.py

cat data/normalized/stage5s0_singhera_capability_summary.json
```

## Как включить проверку конкретного action

Открыть `scripts/stage5s0_check_singhera_capabilities.py`.
Найти `CONFIRMED_PAYLOADS`. Заполнить нужный блок:

```python
CONFIRMED_PAYLOADS = {
    "profile": None,           # → заменить None на точный payload dict
    "posts_pinned": None,
    "highlights_index": None,  # например: {"action": "highlights", "url": "..."}
    "highlight_stories": None,
}
```

Пример для highlights_index (после подтверждения формата):

```python
"highlights_index": {
    "action": "highlights",
    "url": "https://www.instagram.com/vlada_kliuiko/"
    # или "username": "vlada_kliuiko" — точный ключ должен быть подтверждён
}
```

## Выходные файлы

```
data/raw/stage5s0_singhera_profile_raw.json           ← не коммитить
data/raw/stage5s0_singhera_posts_raw.json             ← не коммитить
data/raw/stage5s0_singhera_highlights_raw.json        ← не коммитить
data/raw/stage5s0_singhera_highlight_stories_raw.json ← не коммитить
data/normalized/stage5s0_singhera_capability_summary.json  ← коммитить
```

Raw создаются только для SKIPPED=false actions.

## Как интерпретировать результат

**`replace_decision` по каждому action:**

| Decision | Значение |
|---|---|
| `replace current actor` | singhera07 вернул все обязательные поля |
| `use as fallback` | singhera07 вернул часть обязательных полей |
| `keep current actor` | singhera07 не вернул обязательные поля |
| `not enough evidence` | actor вернул 0 items |
| `skipped` | action не запускался (payload не подтверждён) |

**`recommended_architecture`:**
- Финальная рекомендация по составу actor pair
- Если highlight_stories не работает — singhera07 primary для index, igview-owner для stories
- Если оба работают — singhera07 может заменить оба

**`can_replace`:**
- `true` = singhera07 вернул все обязательные поля для замены
- `false` = не вернул или action SKIPPED

## Следующий шаг

После Stage 5S-0:
- `compatible` / `replace` → переключить pipeline на singhera07 для подтверждённых actions
- `skipped` → предоставить точные payloads для включения action checks
- `not_compatible` → оставить текущие actors, singhera07 не заменяет
