// ============================================================
// EdTech Analytics MVP — Build clean_events
// ============================================================
//
// Column indices below match header order defined in setup.gs SHEETS.
// clean_events output: 19 columns in this order:
//   event_id, timestamp, source_table, event_type,
//   client_id, telegram_id, telegram_norm, phone_norm, email_norm, name_norm,
//   utm_source, utm_medium, utm_campaign, utm_content,
//   webinar_id, duration_min, status, amount, raw_row_id

// ── helpers ────────────────────────────────────────────────

function _getSheet(ss, name) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) throw new Error('Sheet not found: ' + name);
  return sheet;
}

function _readData(ss, name) {
  var sheet = _getSheet(ss, name);
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  return sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
}

function _toNum(value) {
  var n = parseFloat(String(value).replace(/[^0-9.\-]/g, ''));
  return isNaN(n) ? 0 : n;
}

// ── mappers ─────────────────────────────────────────────────
// Each mapper returns an array matching the 19 clean_events columns.
// raw_row_id = data row index (first data row = 2).

function _mapSiteWebinarRaw(row, rawRowId) {
  // timestamp(0), event(1), client_id(2), page_url(3),
  // utm_source(4), utm_medium(5), utm_campaign(6), utm_content(7), utm_term(8), referrer(9)
  var eventType = String(row[1]).trim().toLowerCase() === 'pageview'
    ? 'site_webinar_pageview'
    : 'site_webinar_event';
  return [
    'site_webinar_raw_' + rawRowId,  // event_id
    row[0],                           // timestamp
    'site_webinar_raw',               // source_table
    eventType,                        // event_type
    String(row[2]),                   // client_id
    '',                               // telegram_id
    '',                               // telegram_norm
    '',                               // phone_norm
    '',                               // email_norm
    '',                               // name_norm
    normalizeUtm(row[4]),             // utm_source
    normalizeUtm(row[5]),             // utm_medium
    normalizeUtm(row[6]),             // utm_campaign
    normalizeUtm(row[7]),             // utm_content
    '',                               // webinar_id
    '',                               // duration_min
    '',                               // status
    '',                               // amount
    rawRowId                          // raw_row_id
  ];
}

function _mapFormWebinarRaw(row, rawRowId) {
  // timestamp(0), client_id(1), name(2), telegram(3), phone(4), email(5),
  // utm_source(6), utm_medium(7), utm_campaign(8), utm_content(9), utm_term(10),
  // form_id(11), source_page(12)
  return [
    'form_webinar_raw_' + rawRowId,
    row[0],
    'form_webinar_raw',
    'webinar_form_submit',
    String(row[1]),
    '',
    normalizeTelegram(row[3]),
    normalizePhone(row[4]),
    normalizeEmail(row[5]),
    normalizeName(row[2]),
    normalizeUtm(row[6]),
    normalizeUtm(row[7]),
    normalizeUtm(row[8]),
    normalizeUtm(row[9]),
    '',
    '',
    '',
    '',
    rawRowId
  ];
}

function _mapBotRaw(row, rawRowId) {
  // timestamp(0), telegram_id(1), telegram_username(2), event(3), step(4),
  // bot_name(5), payload(6), utm_source(7), utm_medium(8), utm_campaign(9), utm_content(10)
  var eventType = String(row[3]).trim().toLowerCase() === 'start'
    ? 'bot_start'
    : 'bot_event';
  return [
    'bot_raw_' + rawRowId,
    row[0],
    'bot_raw',
    eventType,
    '',
    String(row[1]),
    normalizeTelegram(row[2]),
    '',
    '',
    '',
    normalizeUtm(row[7]),
    normalizeUtm(row[8]),
    normalizeUtm(row[9]),
    normalizeUtm(row[10]),
    '',
    '',
    '',
    '',
    rawRowId
  ];
}

function _mapZoomRaw(row, rawRowId) {
  // webinar_id(0), webinar_name(1), name(2), telegram(3), phone(4), email(5),
  // join_time(6), leave_time(7), duration_min(8), watched_to_sale(9),
  // attended(10), source_file(11)
  var duration = isEmpty(row[8]) ? '' : _toNum(row[8]);
  return [
    'zoom_raw_' + rawRowId,
    row[6],                          // join_time used as timestamp
    'zoom_raw',
    'zoom_attended',
    '',
    '',
    normalizeTelegram(row[3]),
    normalizePhone(row[4]),
    normalizeEmail(row[5]),
    normalizeName(row[2]),
    '',
    '',
    '',
    '',
    String(row[0]),                  // webinar_id
    duration,
    '',
    '',
    rawRowId
  ];
}

function _mapCourseSiteRaw(row, rawRowId) {
  // timestamp(0), event(1), client_id(2), page_url(3),
  // utm_source(4), utm_medium(5), utm_campaign(6), utm_content(7), utm_term(8), referrer(9)
  var eventType = String(row[1]).trim().toLowerCase() === 'pageview'
    ? 'course_site_pageview'
    : 'course_site_event';
  return [
    'course_site_raw_' + rawRowId,
    row[0],
    'course_site_raw',
    eventType,
    String(row[2]),
    '',
    '',
    '',
    '',
    '',
    normalizeUtm(row[4]),
    normalizeUtm(row[5]),
    normalizeUtm(row[6]),
    normalizeUtm(row[7]),
    '',
    '',
    '',
    '',
    rawRowId
  ];
}

function _mapCourseFormRaw(row, rawRowId) {
  // timestamp(0), client_id(1), name(2), telegram(3), phone(4), email(5),
  // utm_source(6), utm_medium(7), utm_campaign(8), utm_content(9), utm_term(10),
  // form_id(11), source_page(12)
  return [
    'course_form_raw_' + rawRowId,
    row[0],
    'course_form_raw',
    'course_form_submit',
    String(row[1]),
    '',
    normalizeTelegram(row[3]),
    normalizePhone(row[4]),
    normalizeEmail(row[5]),
    normalizeName(row[2]),
    normalizeUtm(row[6]),
    normalizeUtm(row[7]),
    normalizeUtm(row[8]),
    normalizeUtm(row[9]),
    '',
    '',
    '',
    '',
    rawRowId
  ];
}

function _mapSalesRaw(row, rawRowId) {
  // timestamp(0), name(1), telegram(2), phone(3), email(4),
  // status(5), amount(6), payment_date(7), payment_method(8),
  // reason_lost(9), comment(10), manager(11)
  var status = String(row[5]).trim().toLowerCase();
  var amount = isEmpty(row[6]) ? 0 : _toNum(row[6]);
  var eventType = (status === 'paid' || amount > 0) ? 'payment' : 'sale_status';
  return [
    'sales_raw_' + rawRowId,
    row[0],
    'sales_raw',
    eventType,
    '',
    '',
    normalizeTelegram(row[2]),
    normalizePhone(row[3]),
    normalizeEmail(row[4]),
    normalizeName(row[1]),
    '',
    '',
    '',
    '',
    '',
    '',
    status,
    amount || '',
    rawRowId
  ];
}

// ── main ────────────────────────────────────────────────────

function buildCleanEvents() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var cleanSheet = _getSheet(ss, 'clean_events');

  // Clear old data, keep header row
  var lastRow = cleanSheet.getLastRow();
  if (lastRow > 1) {
    cleanSheet.getRange(2, 1, lastRow - 1, 19).clearContent();
  }

  var sources = [
    { name: 'site_webinar_raw',  mapper: _mapSiteWebinarRaw  },
    { name: 'form_webinar_raw',  mapper: _mapFormWebinarRaw  },
    { name: 'bot_raw',           mapper: _mapBotRaw           },
    { name: 'zoom_raw',          mapper: _mapZoomRaw          },
    { name: 'course_site_raw',   mapper: _mapCourseSiteRaw   },
    { name: 'course_form_raw',   mapper: _mapCourseFormRaw   },
    { name: 'sales_raw',         mapper: _mapSalesRaw         }
  ];

  var allRows = [];

  sources.forEach(function(source) {
    var data = _readData(ss, source.name);
    data.forEach(function(row, idx) {
      var rawRowId = idx + 2; // row 1 = header, data starts at row 2
      allRows.push(source.mapper(row, rawRowId));
    });
  });

  if (allRows.length > 0) {
    cleanSheet.getRange(2, 1, allRows.length, 19).setValues(allRows);
  }

  Logger.log('buildCleanEvents: wrote ' + allRows.length + ' rows to clean_events');
}
