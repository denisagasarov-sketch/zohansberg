# Stage 4D: запуск HTML-отчета локально

## Что делает Stage 4D

Создает один HTML-файл для просмотра в браузере:

```
report/final_one_account_analysis_vlada_kliuiko.html
```

HTML содержит все доказательства: картинки, кадры видео, цитаты, evidence,
связку «что увидели → какой вывод сделали».

## Предусловия

Стадии 4A, 4B, 4C должны быть выполнены. Нужны файлы:

```
data/normalized/stage4a_openai_plan.json        ← от Stage 4A
data/normalized/stage4a_media_manifest.json     ← от Stage 4A
analysis/stage4b/posts/*.json                   ← от Stage 4B
analysis/stage4b/highlight_batches/*.json       ← от Stage 4B
analysis/stage4c/highlight_summary.json         ← от Stage 4C
analysis/stage4c/account_summary.json           ← от Stage 4C
output/openai_inputs/stage4/                    ← от Stage 4A (медиафайлы)
```

Скрипт работает и при частично отсутствующих файлах —
выводит предупреждения и продолжает.

## Зависимости

Только стандартная библиотека Python. Дополнительных пакетов не нужно.

## Запуск

Выполнять из папки `instagram_research_test/`:

```bash
python scripts/stage4d_create_html_evidence_report.py
```

Ожидаемый вывод:

```
Stage 4D: создание HTML evidence report...
  posts загружено:   N
  батчей загружено:  8
  HTML размер:       XXX KB
  сохранено:         report/final_one_account_analysis_vlada_kliuiko.html

Открыть в браузере:
  open report/final_one_account_analysis_vlada_kliuiko.html
```

## Открыть отчет

```bash
open report/final_one_account_analysis_vlada_kliuiko.html
```

Или двойной клик на файл в Finder / проводнике.

## Как устроен отчет

| Раздел | Содержимое |
|---|---|
| 1. Резюме | Оффер, роли постов, роль хайлайта, механики доверия, слабые места |
| 2. Посты | Карточка на каждый пост: картинки + разбор (тема, формат, хук, CTA, оффер, evidence) |
| 3. Хайлайт | Каждый batch: роли, CTA, оффер, механики доверия, visible text, story grid с кадрами |
| 4. Цитаты | Все видимые тексты из stories, дедуплицированные, с привязкой к batch |
| 5. Доверие | Все механики доверия из account_summary + highlight_summary |
| 6. Идеи | ideas_to_adapt из account_summary |
| 7. Ограничения | Что не анализировали и почему |

## Изображения

HTML использует относительные пути к `../output/openai_inputs/...`.
Файлы не встраиваются base64 — нужно, чтобы папка `output/` лежала рядом с `report/`.

Если открывать HTML из другой директории или через HTTP-сервер —
обновите пути вручную или запустите:

```bash
python -m http.server 8000
# затем открыть http://localhost:8000/report/final_one_account_analysis_vlada_kliuiko.html
```

## Повторный запуск

Скрипт перезаписывает HTML каждый раз. Идемпотентен.
Данные не изменяет.

## Ограничения HTML-отчета

- Картинки не откроются, если папка `output/` недоступна.
- Story-to-image mapping использует данные из `stage4a_media_manifest.json`;
  если manifest недоступен — кадры распределяются по stories приблизительно.
- Цитаты привязаны к batch, не к конкретной story (ограничение Stage 4B).
