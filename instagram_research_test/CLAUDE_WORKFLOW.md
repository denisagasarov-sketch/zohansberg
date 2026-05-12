# Claude Workflow Rules

## Рабочая ветка

Всегда работать только в ветке:

claude/instagram-competitor-research-test-8mA3d

Не создавать новые ветки.
Не пушить в другие ветки.
Не использовать ветки:
- claude/html-evidence-report-PH4Qd
- любые новые claude/* ветки

Если текущая ветка другая — остановись и напиши пользователю:
"Я не в рабочей ветке. Нужно переключиться на claude/instagram-competitor-research-test-8mA3d."

## Перед любыми изменениями

Сначала проверить:

git branch --show-current

Ожидаемый результат:

claude/instagram-competitor-research-test-8mA3d

Если результат другой — не писать файлы, не коммитить, не пушить.

## Куда пушить

Все изменения пушить только в:

origin claude/instagram-competitor-research-test-8mA3d

Команда:

git push origin claude/instagram-competitor-research-test-8mA3d

## Commit / push

По умолчанию НЕ делать commit и push.

Commit/push можно делать только если пользователь прямо написал:
"можно коммитить и пушить"

или:
"закоммить и запушь"

Если пользователь написал "не коммить", "не пушь", "не делай git add / commit / push" — запрещено выполнять любые git add, git commit, git push.

## Что можно коммитить

Коммитить можно только явно созданные/измененные code/report/prompt файлы, которые относятся к задаче.

Никогда не коммитить:

.env
analysis/
output/
data/raw/
analysis/openai_responses/
любые файлы с API keys
любые большие media files
любые base64 dumps

## Перед push

Перед push обязательно показать:

git status
git diff --name-only --cached

И убедиться, что в staged нет:

.env
analysis/
output/
data/raw/
analysis/openai_responses/

## Если нужна новая задача

Не создавать новую ветку.
Работать в текущей рабочей ветке:
claude/instagram-competitor-research-test-8mA3d

## Если файл был случайно создан в другой ветке

Не продолжать работу в другой ветке.

Нужно перенести только нужные файлы в рабочую ветку:

git checkout claude/instagram-competitor-research-test-8mA3d
git checkout origin/<wrong-branch> -- path/to/file

Потом работать только в рабочей ветке.

## OpenAI / Apify / media

Не запускать OpenAI, Apify, scraping или media download без явного разрешения пользователя.

## Обязательный ответ после изменений

После правки всегда писать:

- текущая ветка
- какие файлы изменены
- был ли commit/push
- commit hash, если commit/push был
- что НЕ трогалось: .env, data/raw, analysis, output
