"""Слияние строк аккаунта по ссылке (upsert) для листов «Посты» / «Reels».

Режим «Актуализировать»: свежесобранные последние N постов сливаются с уже
записанными строками аккаунта так, что:
  - пост, который есть и в таблице, и в новом сборе → обновляется (берём свежую строку);
  - пост из нового сбора, которого не было в таблице → добавляется;
  - старый пост в таблице, которого нет в последних N → сохраняется (история копится).

Ключ матчинга — shortcode из ссылки на пост (устойчив к хвостовым слешам,
query-параметрам и редактированию URL). Совпадает с _ig_shortcode в prepare_sheets.
"""

import re

# /p/<code>/, /reel/<code>/, /tv/<code>/ — shortcode это первый сегмент после типа.
_SHORTCODE_RE = re.compile(r"/(?:p|reel|tv)/([^/?#]+)")


def shortcode(url) -> str:
    """Достаёт shortcode из ссылки на пост/reels. Пустая строка, если не найден."""
    if not isinstance(url, str):
        url = str(url or "")
    m = _SHORTCODE_RE.search(url)
    return m.group(1) if m else ""


def merge_rows(existing_rows, new_rows, headers, link_header) -> list:
    """Сливает строки аккаунта по ссылке (upsert).

    Параметры:
      existing_rows — строки аккаунта из таблицы (как есть, могут быть любой ширины);
      new_rows      — свежесобранные строки (payload, ширина == len(headers));
      headers       — заголовки листа (канонічная payload-схема);
      link_header   — имя колонки-ссылки («Ссылка на пост» / «Ссылка»).

    Возврат — объединённый набор строк аккаунта: сначала свежие (new_rows,
    в порядке сбора), затем старые строки, которых нет в свежем наборе (история).

    Если link_header нет в headers — матчить не по чему, возвращаем new_rows
    (поведение replace: безопасно, без дублей).
    """
    if link_header not in headers:
        return list(new_rows)

    idx   = headers.index(link_header)
    width = len(headers)

    def _code(row) -> str:
        return shortcode(row[idx]) if idx < len(row) else ""

    # Свежий набор: дедуп по shortcode (на случай повторов), сохраняем порядок.
    new_codes: set[str] = set()
    merged: list = []
    for row in new_rows:
        code = _code(row)
        if code and code in new_codes:
            continue  # дубль внутри свежего набора — пропускаем
        if code:
            new_codes.add(code)
        merged.append(list(row))

    # Старые строки: добавляем те, чей shortcode не входит в свежий набор.
    # Строки без распознанного shortcode сохраняем (не теряем историю).
    for row in existing_rows:
        code = _code(row)
        if code and code in new_codes:
            continue  # этот пост обновлён свежей строкой
        # Приводим ширину старой строки к payload-схеме.
        norm = [str(v) if v is not None else "" for v in row[:width]]
        norm += [""] * (width - len(norm))
        merged.append(norm)

    return merged
