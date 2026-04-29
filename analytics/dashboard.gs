// ============================================================
// EdTech Analytics MVP — Dashboard
// ============================================================
//
// Source: funnel sheet (19 columns)
// Output: dashboard sheet (7 columns), 4 blocks:
//   1. Общая воронка
//   2. Воронка по источникам
//   3. Match quality
//   4. Data quality summary
//
// Depends on: clean_events.gs (_getSheet)

// funnel column indices (0-based)
var FC = {
  PERSON_ID:           0,
  SOURCE:              1,
  UTM_MEDIUM:          2,
  UTM_CAMPAIGN:        3,
  UTM_CONTENT:         4,
  WEBINAR_SITE_VISIT:  5,
  WEBINAR_FORM_SUBMIT: 6,
  BOT_STARTED:         7,
  ZOOM_ATTENDED:       8,
  ZOOM_DURATION_MIN:   9,
  WATCHED_TO_SALE:     10,
  COURSE_SITE_VISIT:   11,
  COURSE_FORM_SUBMIT:  12,
  SALE_STATUS:         13,
  PAID:                14,
  AMOUNT:              15,
  PAYMENT_DATE:        16,
  MATCH_QUALITY:       17,
  DATA_CONFLICTS:      18
};

var SECTION = {
  FUNNEL:  'Общая воронка',
  SOURCES: 'Воронка по источникам',
  MQ:      'Match quality',
  DQ:      'Data quality'
};

// ── helpers ─────────────────────────────────────────────────

function _isTrue(val) {
  return val === true || String(val).toUpperCase() === 'TRUE';
}

// Returns percentage (0–100, 1 decimal) or '' if denominator is 0/empty.
function _pct(numerator, denominator) {
  if (!denominator || denominator === 0) return '';
  return Math.round(numerator / denominator * 1000) / 10;
}

// Builds one dashboard row.
function _drow(section, metric, value, fromPrev, fromStart, source, notes) {
  return [
    section,
    metric,
    value        !== '' ? value        : '',
    fromPrev     !== '' ? fromPrev     : '',
    fromStart    !== '' ? fromStart    : '',
    source !== undefined && source !== null ? String(source) : 'all',
    notes  !== undefined && notes  !== null ? String(notes)  : ''
  ];
}

// ── main ────────────────────────────────────────────────────

function buildDashboard() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var fSheet  = _getSheet(ss, 'funnel');
  var fLastRow = fSheet.getLastRow();
  if (fLastRow < 2) {
    Logger.log('buildDashboard: funnel is empty, run buildFunnel first');
    return;
  }
  var rows = fSheet.getRange(2, 1, fLastRow - 1, 19).getValues();
  var total = rows.length;

  // ── Aggregate ────────────────────────────────────────────

  // Block 1 accumulators
  var b1 = { site: 0, form: 0, bot: 0, zoom: 0, watched: 0,
             csite: 0, cform: 0, payments: 0, revenue: 0 };

  // Block 2: source → accumulators
  var srcMap = {};

  // Block 3: match quality counts
  var mqCounts = { STRONG: 0, MEDIUM: 0, WEAK: 0, CHECK: 0, UNKNOWN: 0 };

  // Block 4: data quality issue counts
  var dq = { missing_source: 0, weak_only: 0, conflict: 0,
             zoom_no_cform: 0, cform_no_zoom: 0, paid_no_src: 0 };

  rows.forEach(function(row) {
    var src      = String(row[FC.SOURCE]).trim();
    var siteV    = _isTrue(row[FC.WEBINAR_SITE_VISIT]);
    var formV    = _isTrue(row[FC.WEBINAR_FORM_SUBMIT]);
    var botV     = _isTrue(row[FC.BOT_STARTED]);
    var zoomV    = _isTrue(row[FC.ZOOM_ATTENDED]);
    var watchedV = _isTrue(row[FC.WATCHED_TO_SALE]);
    var csiteV   = _isTrue(row[FC.COURSE_SITE_VISIT]);
    var cformV   = _isTrue(row[FC.COURSE_FORM_SUBMIT]);
    var paidV    = _isTrue(row[FC.PAID]);
    var amount   = parseFloat(String(row[FC.AMOUNT])) || 0;
    var mq       = String(row[FC.MATCH_QUALITY]).trim().toUpperCase();
    var conflict = _isTrue(row[FC.DATA_CONFLICTS]);

    // Block 1
    if (siteV)    b1.site++;
    if (formV)    b1.form++;
    if (botV)     b1.bot++;
    if (zoomV)    b1.zoom++;
    if (watchedV) b1.watched++;
    if (csiteV)   b1.csite++;
    if (cformV)   b1.cform++;
    if (paidV)  { b1.payments++; b1.revenue += amount; }

    // Block 2
    var label = src || '(unknown)';
    if (!srcMap[label]) {
      srcMap[label] = { total: 0, site: 0, reg: 0, bot: 0, zoom: 0,
                        watched: 0, clead: 0, payments: 0, revenue: 0, strong: 0 };
    }
    var s = srcMap[label];
    s.total++;
    if (siteV)    s.site++;
    if (formV)    s.reg++;
    if (botV)     s.bot++;
    if (zoomV)    s.zoom++;
    if (watchedV) s.watched++;
    if (cformV)   s.clead++;
    if (paidV)  { s.payments++; s.revenue += amount; }
    if (mq === 'STRONG' || mq === 'MEDIUM') s.strong++;

    // Block 3
    if (mqCounts[mq] !== undefined) mqCounts[mq]++;
    else mqCounts.UNKNOWN++;

    // Block 4
    if (!src)              dq.missing_source++;
    if (mq === 'WEAK')     dq.weak_only++;
    if (conflict)          dq.conflict++;
    if (zoomV && !cformV)  dq.zoom_no_cform++;
    if (cformV && !zoomV)  dq.cform_no_zoom++;
    if (paidV && !src)     dq.paid_no_src++;
  });

  // ── Build output ─────────────────────────────────────────

  var out = [];

  // ── Block 1: Общая воронка ────────────────────────────────
  // Funnel sequence for conversion_from_previous calculation
  var steps = [
    { metric: 'webinar_site_visitors', n: b1.site     },
    { metric: 'webinar_form_submits',  n: b1.form     },
    { metric: 'bot_starts',            n: b1.bot      },
    { metric: 'zoom_attended',         n: b1.zoom     },
    { metric: 'watched_to_sale',       n: b1.watched  },
    { metric: 'course_site_visitors',  n: b1.csite    },
    { metric: 'course_form_submits',   n: b1.cform    },
    { metric: 'payments',              n: b1.payments }
  ];

  steps.forEach(function(step, i) {
    var fromPrev  = i === 0 ? '' : _pct(step.n, steps[i - 1].n);
    var fromStart = i === 0 ? '' : _pct(step.n, b1.site);
    out.push(_drow(SECTION.FUNNEL, step.metric, step.n, fromPrev, fromStart, 'all', ''));
  });
  out.push(_drow(SECTION.FUNNEL, 'revenue', b1.revenue, '', '', 'all', ''));

  // ── Block 2: Воронка по источникам ────────────────────────
  Object.keys(srcMap).sort().forEach(function(label) {
    var s = srcMap[label];
    var metrics = [
      ['visitors',              s.site,                  ''],
      ['webinar_registrations', s.reg,                   ''],
      ['bot_starts',            s.bot,                   ''],
      ['zoom_attended',         s.zoom,                  ''],
      ['watched_to_sale',       s.watched,               ''],
      ['course_leads',          s.clead,                 ''],
      ['payments',              s.payments,              ''],
      ['revenue',               s.revenue,               ''],
      ['cr_visit_to_registration', _pct(s.reg,      s.site),  '%'],
      ['cr_registration_to_zoom',  _pct(s.zoom,     s.reg),   '%'],
      ['cr_zoom_to_lead',          _pct(s.clead,    s.zoom),  '%'],
      ['cr_lead_to_payment',       _pct(s.payments, s.clead), '%'],
      ['match_rate',               _pct(s.strong,   s.total), '%']
    ];
    metrics.forEach(function(m) {
      out.push(_drow(SECTION.SOURCES, m[0], m[1], '', '', label, m[2]));
    });
  });

  // ── Block 3: Match quality ─────────────────────────────────
  // value = count, conversion_from_start = share %
  ['STRONG', 'MEDIUM', 'WEAK', 'CHECK', 'UNKNOWN'].forEach(function(seg) {
    var count = mqCounts[seg];
    out.push(_drow(SECTION.MQ, seg, count, '', _pct(count, total), 'all', ''));
  });

  // ── Block 4: Data quality ──────────────────────────────────
  var dqItems = [
    ['missing_source',           dq.missing_source, 'person_id без source'],
    ['weak_only_client_id',      dq.weak_only,      'match_quality = WEAK, только client_id'],
    ['has_conflict',             dq.conflict,       'конфликт идентификаторов при склейке'],
    ['zoom_without_course_form', dq.zoom_no_cform,  'были на зуме, не оставили заявку на курс'],
    ['course_form_without_zoom', dq.cform_no_zoom,  'заявка на курс без зума — возможна потеря данных'],
    ['payments_without_source',  dq.paid_no_src,    'оплата без атрибуции']
  ];
  dqItems.forEach(function(item) {
    out.push(_drow(SECTION.DQ, item[0], item[1], '', '', 'all', item[2]));
  });

  // ── Write ──────────────────────────────────────────────────
  var dSheet  = _getSheet(ss, 'dashboard');
  var dLastRow = dSheet.getLastRow();
  if (dLastRow > 1) dSheet.getRange(2, 1, dLastRow - 1, 7).clearContent();

  if (out.length > 0) {
    dSheet.getRange(2, 1, out.length, 7).setValues(out);
  }

  Logger.log('buildDashboard: wrote ' + out.length + ' rows (' +
    steps.length + 1 + ' funnel, ' +
    Object.keys(srcMap).length + ' sources, 5 mq segments, ' +
    dqItems.length + ' dq issues)');
}
