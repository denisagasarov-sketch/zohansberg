// ============================================================
// EdTech Analytics MVP — Funnel Layer
// ============================================================
//
// Sources: clean_events + identity_map + people
// (zoom_raw read directly for watched_to_sale — field not in clean_events)
// Depends on: CE_COL (identity.gs), _getSheet/_readData (clean_events.gs),
//             normalizeTelegram/Phone/Email (normalize.gs)
//
// funnel output: 19 columns
//   person_id, source, utm_medium, utm_campaign, utm_content,
//   webinar_site_visit, webinar_form_submit, bot_started,
//   zoom_attended, zoom_duration_min, watched_to_sale,
//   course_site_visit, course_form_submit,
//   sale_status, paid, amount, payment_date,
//   match_quality, data_conflicts

// people column indices (0-based)
var P_COL = {
  PERSON_ID:          0,
  FIRST_SEEN_AT:      1,
  FIRST_SOURCE:       3,
  FIRST_UTM_MEDIUM:   4,
  FIRST_UTM_CAMPAIGN: 5,
  FIRST_UTM_CONTENT:  6,
  MATCH_QUALITY:      12
};

// identity_map column indices (0-based)
var IM_COL = {
  ID_TYPE:      0,
  ID_VALUE:     1,
  PERSON_ID:    2,
  CONFLICT_FLAG:7
};

// zoom_raw column indices (0-based)
var Z_COL = {
  TELEGRAM:       3,
  PHONE:          4,
  EMAIL:          5,
  WATCHED_TO_SALE:9
};

// ── helpers ─────────────────────────────────────────────────

// Builds "type:value" → person_id lookup from identity_map rows.
function _buildIdLookup(imRows) {
  var lookup = {};
  imRows.forEach(function(row) {
    var key = String(row[IM_COL.ID_TYPE]) + ':' + String(row[IM_COL.ID_VALUE]);
    lookup[key] = String(row[IM_COL.PERSON_ID]);
  });
  return lookup;
}

// Returns person_id for a clean_events row using priority-ordered identifier lookup.
function _findPidForEvent(row, idLookup) {
  var candidates = [
    { type: 'telegram_id', val: String(row[CE_COL.TELEGRAM_ID]).trim()   },
    { type: 'telegram',    val: String(row[CE_COL.TELEGRAM_NORM]).trim()  },
    { type: 'phone',       val: String(row[CE_COL.PHONE_NORM]).trim()     },
    { type: 'email',       val: String(row[CE_COL.EMAIL_NORM]).trim()     },
    { type: 'client_id',   val: String(row[CE_COL.CLIENT_ID]).trim()      }
  ];
  for (var i = 0; i < candidates.length; i++) {
    var c = candidates[i];
    if (c.val !== '') {
      var pid = idLookup[c.type + ':' + c.val];
      if (pid) return pid;
    }
  }
  return null;
}

// Returns person_id for a zoom_raw row via normalized identifiers.
function _findPidForZoom(row, idLookup) {
  var tg    = normalizeTelegram(row[Z_COL.TELEGRAM]);
  var phone = normalizePhone(row[Z_COL.PHONE]);
  var email = normalizeEmail(row[Z_COL.EMAIL]);

  if (tg    && idLookup['telegram:' + tg])    return idLookup['telegram:' + tg];
  if (phone && idLookup['phone:' + phone])     return idLookup['phone:' + phone];
  if (email && idLookup['email:' + email])     return idLookup['email:' + email];
  return null;
}

function _newFunnelRecord(pid, peopleRow) {
  return {
    person_id:           pid,
    source:              String(peopleRow[P_COL.FIRST_SOURCE]),
    utm_medium:          String(peopleRow[P_COL.FIRST_UTM_MEDIUM]),
    utm_campaign:        String(peopleRow[P_COL.FIRST_UTM_CAMPAIGN]),
    utm_content:         String(peopleRow[P_COL.FIRST_UTM_CONTENT]),
    webinar_site_visit:  false,
    webinar_form_submit: false,
    bot_started:         false,
    zoom_attended:       false,
    zoom_duration_min:   0,
    watched_to_sale:     false,
    course_site_visit:   false,
    course_form_submit:  false,
    sale_status:         '',
    sale_status_ts:      '',   // internal, not written to sheet
    paid:                false,
    amount:              0,
    payment_date:        '',
    match_quality:       String(peopleRow[P_COL.MATCH_QUALITY]),
    data_conflicts:      false
  };
}

// ── main ────────────────────────────────────────────────────

function buildFunnel() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. People → base records
  var pSheet  = _getSheet(ss, 'people');
  var pLastRow = pSheet.getLastRow();
  if (pLastRow < 2) {
    Logger.log('buildFunnel: people is empty, run buildIdentityAndPeople first');
    return;
  }
  var peopleRows = pSheet.getRange(2, 1, pLastRow - 1, 21).getValues();

  var funnelMap = {};
  peopleRows.forEach(function(row) {
    var pid = String(row[P_COL.PERSON_ID]).trim();
    if (!pid) return;
    funnelMap[pid] = _newFunnelRecord(pid, row);
  });

  // 2. Identity map → id lookup + conflict flags
  var imSheet  = _getSheet(ss, 'identity_map');
  var imLastRow = imSheet.getLastRow();
  var idLookup = {};

  if (imLastRow >= 2) {
    var imRows = imSheet.getRange(2, 1, imLastRow - 1, 8).getValues();
    idLookup = _buildIdLookup(imRows);

    imRows.forEach(function(row) {
      var pid      = String(row[IM_COL.PERSON_ID]);
      var conflict = String(row[IM_COL.CONFLICT_FLAG]).toUpperCase() === 'TRUE';
      if (conflict && funnelMap[pid]) funnelMap[pid].data_conflicts = true;
    });
  }

  // 3. Clean events → funnel flags
  var cleanSheet  = _getSheet(ss, 'clean_events');
  var cleanLastRow = cleanSheet.getLastRow();

  if (cleanLastRow >= 2) {
    var cleanRows = cleanSheet.getRange(2, 1, cleanLastRow - 1, 19).getValues();

    cleanRows.forEach(function(row) {
      var pid = _findPidForEvent(row, idLookup);
      if (!pid || !funnelMap[pid]) return;

      var f         = funnelMap[pid];
      var eventType = String(row[CE_COL.EVENT_TYPE]);
      var ts        = row[CE_COL.TIMESTAMP];
      var source    = String(row[CE_COL.SOURCE_TABLE]);
      var duration  = parseFloat(String(row[CE_COL.DURATION_MIN])) || 0;
      var status    = String(row[CE_COL.STATUS]).trim().toLowerCase();
      var amount    = parseFloat(String(row[CE_COL.AMOUNT])) || 0;

      switch (eventType) {
        case 'site_webinar_pageview':  f.webinar_site_visit  = true; break;
        case 'webinar_form_submit':    f.webinar_form_submit = true; break;
        case 'bot_start':              f.bot_started         = true; break;
        case 'zoom_attended':
          f.zoom_attended = true;
          if (duration > f.zoom_duration_min) f.zoom_duration_min = duration;
          break;
        case 'course_site_pageview':   f.course_site_visit  = true; break;
        case 'course_form_submit':     f.course_form_submit = true; break;
        case 'payment':
          f.paid    = true;
          f.amount += amount;
          if (!f.payment_date || ts > f.payment_date) f.payment_date = ts;
          break;
      }

      // sale_status: last status from any sales_raw event
      if (source === 'sales_raw' && status) {
        if (!f.sale_status_ts || ts > f.sale_status_ts) {
          f.sale_status    = status;
          f.sale_status_ts = ts;
        }
      }
    });
  }

  // 4. Zoom raw → watched_to_sale (field absent in clean_events)
  var zoomRows = _readData(ss, 'zoom_raw');
  zoomRows.forEach(function(row) {
    var raw     = String(row[Z_COL.WATCHED_TO_SALE]).trim().toLowerCase();
    var watched = (raw === 'true' || raw === 'yes' || raw === '1');
    if (!watched) return;

    var pid = _findPidForZoom(row, idLookup);
    if (pid && funnelMap[pid]) funnelMap[pid].watched_to_sale = true;
  });

  // 5. Write funnel sheet
  var fSheet  = _getSheet(ss, 'funnel');
  var fLastRow = fSheet.getLastRow();
  if (fLastRow > 1) fSheet.getRange(2, 1, fLastRow - 1, 19).clearContent();

  var fRows = Object.keys(funnelMap).map(function(pid) {
    var f = funnelMap[pid];
    return [
      f.person_id,
      f.source,
      f.utm_medium,
      f.utm_campaign,
      f.utm_content,
      f.webinar_site_visit  ? 'TRUE' : 'FALSE',
      f.webinar_form_submit ? 'TRUE' : 'FALSE',
      f.bot_started         ? 'TRUE' : 'FALSE',
      f.zoom_attended       ? 'TRUE' : 'FALSE',
      f.zoom_duration_min > 0 ? f.zoom_duration_min : '',
      f.watched_to_sale     ? 'TRUE' : 'FALSE',
      f.course_site_visit   ? 'TRUE' : 'FALSE',
      f.course_form_submit  ? 'TRUE' : 'FALSE',
      f.sale_status,
      f.paid                ? 'TRUE' : 'FALSE',
      f.amount > 0          ? f.amount : '',
      f.payment_date,
      f.match_quality,
      f.data_conflicts      ? 'TRUE' : 'FALSE'
    ];
  });

  if (fRows.length > 0) {
    fSheet.getRange(2, 1, fRows.length, 19).setValues(fRows);
  }

  Logger.log('buildFunnel: wrote ' + fRows.length + ' rows to funnel');
}
