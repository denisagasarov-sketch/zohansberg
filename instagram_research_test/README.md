# Instagram Competitor Research — Test Run

Proof of concept pipeline: Claude Code + Apify + OpenAI API.

## Цель

Проверить техническую возможность автоматического исследования публичных Instagram-аккаунтов конкурентов.

## Что делает этот тест

1. Берём 1 публичный Instagram-аккаунт из `data/accounts.json`
2. Собираем 5 последних posts/reels через Apify
3. Отдельно собираем индекс highlights аккаунта
4. Отдельно собираем stories внутри 1-2 highlights
5. Скачиваем media локально в `output/`
6. Анализируем 1 post/reel и 1 highlight через OpenAI API
7. Сохраняем ответы в `analysis/openai_responses/`

## Что НЕ делаем на этом этапе

- Не запускаем полный анализ всех аккаунтов
- Не берём больше 5 публикаций
- Не анализируем все highlights

## Стек

- **Сбор данных**: [Apify](https://apify.com) — Instagram Scraper
- **Анализ**: OpenAI API (GPT-4o) — текст, изображения, скриншоты, кадры из видео
- **Оркестрация**: Claude Code (без Anthropic API)

## Настройка

```bash
cp .env.example .env
# Вставить ключи в .env:
# OPENAI_API_KEY=sk-...
# APIFY_TOKEN=apify_api_...

pip install -r requirements.txt
```

## Структура

```
instagram_research_test/
  data/
    accounts.json        # список аккаунтов и параметры
    raw/                 # сырые данные от Apify (в .gitignore)
    normalized/          # нормализованные данные
  output/
    media/
      posts/             # скачанные фото/видео постов
      reels/             # скачанные reels
      highlights/        # скачанные highlights
    frames/              # кадры из видео
    screenshots/         # скриншоты для анализа
  analysis/
    openai_responses/    # ответы OpenAI API (в .gitignore)
  report/                # итоговые отчёты
  scripts/               # скрипты сбора и анализа
```

## Статус

- [x] Структура проекта создана
- [ ] Ключи вставлены в .env
- [ ] Тестовый аккаунт выбран в accounts.json
- [ ] Сбор данных через Apify
- [ ] Скачивание media
- [ ] Анализ через OpenAI API
- [ ] Итоговый отчёт
