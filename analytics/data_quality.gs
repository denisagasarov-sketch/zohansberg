// ============================================================
// EdTech Analytics MVP — Data Quality Layer
// ============================================================
//
// Checks 10 issue types across RAW sheets, identity_map, people, funnel.
// Depends on: _getSheet/_readData (clean_events.gs),
//             normalizeTelegram/Phone/Email/isEmpty (normalize.gs),
//             P_COL/IM_COL/Z_COL (funnel.gs), FC (dashboard.gs)

// RAW sheet column indices used only in this file
var DQ_FORM = { CLIENT_ID: 1, TELEGRAM: 3, PHONE: 4, EMAIL: 5 };
var DQ_SALES = { TELEGRAM: 2, PHONE: 3, EMAIL: 4 };

// severity order for sorting output
var SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };

// ── helpers ─────────────────────────────────────────────────

// Builds identity lookup { "type:value" → person_id } from identity_map rows.
function _buildDqIdLookup(imRows) {
  var lookup = {};
  imRows.forEach(function(row) {
    lookup[String(row[IM_COL.ID_TYPE]) + ':' + String(row[IM_COL.ID_VALUE])] =
      String(row[IM_COL.PERSON_ID]);
  });
  return lookup;
}

// Tries to resolve person_id for a RAW row using normalized identifiers.
function _lookupPid(idLookup, telegram, phone, email, clientId) {
  var tg = normalizeTelegram(telegram);
  var ph = normalizePhone(phone);
  var em = normalizeEmail(email);
  var ci = clientId ? String(clientId).trim() : '';

  if (tg && idLookup['telegram:'   + tg]) return idLookup['telegram:'   + tg];
  if (ph && idLookup['phone:'      + ph]) return idLookup['phone:'      + ph];
  if (em && idLookup['email:'      + em]) return idLookup['email:'      + em];
  if (ci && idLookup['client_id:'  + ci]) return idLookup['client_id:'  + ci];
  return '';
}

// Builds one data_quality row.
function _issue(type, severity, srcTable, rawRowId, personId, description, fix) {
  return [
    type,
    severity,
    srcTable,
    rawRowId  || '',
    personId  || '',
    description,
    fix
  ];
}

// ── main ────────────────────────────────────────────────────

function buildDataQuality() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // Load identity_map for lookup + conflict detection
  var imSheet  = _getSheet(ss, 'identity_map');
  var imLastRow = imSheet.getLastRow();
  var imRows    = imLastRow >= 2
    ? imSheet.getRange(2, 1, imLastRow - 1, 8).getValues()
    : [];
  var idLookup  = _buildDqIdLookup(imRows);

  var issues = [];

  // ── 1. missing_telegram_in_webinar_form (high) ────────────
  _readData(ss, 'form_webinar_raw').forEach(function(row, idx) {
    if (isEmpty(row[DQ_FORM.TELEGRAM])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, '', row[DQ_FORM.PHONE], row[DQ_FORM.EMAIL], row[DQ_FORM.CLIENT_ID]);
      issues.push(_issue(
        'missing_telegram_in_webinar_form', 'high',
        'form_webinar_raw', rawRow, pid,
        'Строка ' + rawRow + ': telegram отсутствует. Невозможно склеить с ботом и telegram-продажей.',
        'Добавить поле telegram в форму регистрации на вебинар'
      ));
    }
  });

  // ── 2. missing_phone_in_webinar_form (high) ───────────────
  _readData(ss, 'form_webinar_raw').forEach(function(row, idx) {
    if (isEmpty(row[DQ_FORM.PHONE])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, row[DQ_FORM.TELEGRAM], '', row[DQ_FORM.EMAIL], row[DQ_FORM.CLIENT_ID]);
      issues.push(_issue(
        'missing_phone_in_webinar_form', 'high',
        'form_webinar_raw', rawRow, pid,
        'Строка ' + rawRow + ': телефон отсутствует. Снижает качество склейки.',
        'Добавить обязательное поле телефон в форму регистрации на вебинар'
      ));
    }
  });

  // ── 3. missing_telegram_in_course_form (critical) ─────────
  _readData(ss, 'course_form_raw').forEach(function(row, idx) {
    if (isEmpty(row[DQ_FORM.TELEGRAM])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, '', row[DQ_FORM.PHONE], row[DQ_FORM.EMAIL], row[DQ_FORM.CLIENT_ID]);
      issues.push(_issue(
        'missing_telegram_in_course_form', 'critical',
        'course_form_raw', rawRow, pid,
        'Строка ' + rawRow + ': telegram отсутствует. Невозможно связать заявку с продажей в telegram.',
        'Сделать поле telegram обязательным в форме заявки на курс'
      ));
    }
  });

  // ── 4. zoom_without_telegram (medium) ─────────────────────
  _readData(ss, 'zoom_raw').forEach(function(row, idx) {
    if (isEmpty(row[Z_COL.TELEGRAM])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, '', row[Z_COL.PHONE], row[Z_COL.EMAIL], '');
      issues.push(_issue(
        'zoom_without_telegram', 'medium',
        'zoom_raw', rawRow, pid,
        'Строка ' + rawRow + ': telegram отсутствует в данных Zoom. Сложнее склеить с ботом.',
        'Запросить telegram при регистрации на вебинар или в анкете Zoom'
      ));
    }
  });

  // ── 5. zoom_without_phone (high) ──────────────────────────
  _readData(ss, 'zoom_raw').forEach(function(row, idx) {
    if (isEmpty(row[Z_COL.PHONE])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, row[Z_COL.TELEGRAM], '', row[Z_COL.EMAIL], '');
      issues.push(_issue(
        'zoom_without_phone', 'high',
        'zoom_raw', rawRow, pid,
        'Строка ' + rawRow + ': телефон отсутствует в данных Zoom.',
        'Добавить сбор телефона при регистрации в Zoom или сопоставить с webinar_form'
      ));
    }
  });

  // ── 6. sales_without_telegram (critical) ──────────────────
  _readData(ss, 'sales_raw').forEach(function(row, idx) {
    if (isEmpty(row[DQ_SALES.TELEGRAM])) {
      var rawRow = idx + 2;
      var pid    = _lookupPid(idLookup, '', row[DQ_SALES.PHONE], row[DQ_SALES.EMAIL], '');
      issues.push(_issue(
        'sales_without_telegram', 'critical',
        'sales_raw', rawRow, pid,
        'Строка ' + rawRow + ': telegram отсутствует в записи о продаже. Невозможно замкнуть воронку.',
        'Менеджер обязан вносить telegram клиента при создании сделки'
      ));
    }
  });

  // ── 7. conflicting_identifiers (critical) ─────────────────
  imRows.forEach(function(row, idx) {
    if (String(row[IM_COL.CONFLICT_FLAG]).toUpperCase() !== 'TRUE') return;
    var idType  = String(row[IM_COL.ID_TYPE]);
    var idValue = String(row[IM_COL.ID_VALUE]);
    var pid     = String(row[IM_COL.PERSON_ID]);
    var sources = String(row[6]); // source_tables
    issues.push(_issue(
      'conflicting_identifiers', 'critical',
      sources, idx + 2, pid,
      'Идентификатор ' + idType + ' = "' + idValue + '" связан с несколькими person_id. Источники: ' + sources + '.',
      'Ручная проверка: возможно дублирование записей или ошибка в данных'
    ));
  });

  // ── 8. unknown_source (medium) ────────────────────────────
  var pSheet  = _getSheet(ss, 'people');
  var pLastRow = pSheet.getLastRow();
  if (pLastRow >= 2) {
    pSheet.getRange(2, 1, pLastRow - 1, 21).getValues().forEach(function(row) {
      var pid    = String(row[P_COL.PERSON_ID]).trim();
      var source = String(row[P_COL.FIRST_SOURCE]).trim();
      if (!source) {
        issues.push(_issue(
          'unknown_source', 'medium',
          'people', '', pid,
          'person_id ' + pid + ': first_source отсутствует. Непонятно откуда пришёл человек.',
          'Проверить источник вручную; добавить utm-метки на все точки входа'
        ));
      }
    });
  }

  // ── 9. only_client_id_people (low) ───────────────────────
  if (pLastRow >= 2) {
    pSheet.getRange(2, 1, pLastRow - 1, 21).getValues().forEach(function(row) {
      var pid = String(row[P_COL.PERSON_ID]).trim();
      var mq  = String(row[P_COL.MATCH_QUALITY]).trim().toUpperCase();
      if (mq === 'WEAK') {
        issues.push(_issue(
          'only_client_id_people', 'low',
          'people', '', pid,
          'person_id ' + pid + ': match_quality = WEAK, только client_id. Нет telegram, phone, email.',
          'Добавить форму с контактами на страницу или dogнать ретаргетингом с лид-формой'
        ));
      }
    });
  }

  // ── 10. payment_without_source (critical) ─────────────────
  var fSheet  = _getSheet(ss, 'funnel');
  var fLastRow = fSheet.getLastRow();
  if (fLastRow >= 2) {
    fSheet.getRange(2, 1, fLastRow - 1, 19).getValues().forEach(function(row) {
      var pid    = String(row[FC.PERSON_ID]).trim();
      var source = String(row[FC.SOURCE]).trim();
      var paid   = _isTrue(row[FC.PAID]);
      var amount = parseFloat(String(row[FC.AMOUNT])) || 0;
      if (paid && !source) {
        issues.push(_issue(
          'payment_without_source', 'critical',
          'funnel', '', pid,
          'person_id ' + pid + ' оплатил' + (amount ? ' ' + amount + ' ₽' : '') + ', но source неизвестен. Потеря атрибуции.',
          'Найти точку входа вручную; убедиться что все каналы передают utm-метки'
        ));
      }
    });
  }

  // ── Sort by severity, then issue_type ─────────────────────
  issues.sort(function(a, b) {
    var sa = SEVERITY_ORDER[a[1]] !== undefined ? SEVERITY_ORDER[a[1]] : 99;
    var sb = SEVERITY_ORDER[b[1]] !== undefined ? SEVERITY_ORDER[b[1]] : 99;
    if (sa !== sb) return sa - sb;
    return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
  });

  // ── Write data_quality sheet ───────────────────────────────
  var dqSheet  = _getSheet(ss, 'data_quality');
  var dqLastRow = dqSheet.getLastRow();
  if (dqLastRow > 1) dqSheet.getRange(2, 1, dqLastRow - 1, 7).clearContent();

  if (issues.length > 0) {
    dqSheet.getRange(2, 1, issues.length, 7).setValues(issues);
  }

  Logger.log('buildDataQuality: found ' + issues.length + ' issues');
}
