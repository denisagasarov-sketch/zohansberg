// ============================================================
// EdTech Analytics MVP — Sheet Structure Setup
// ============================================================

var SHEETS = {
  // RAW
  site_webinar_raw: [
    'timestamp', 'event', 'client_id', 'page_url',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'referrer'
  ],
  form_webinar_raw: [
    'timestamp', 'client_id', 'name', 'telegram', 'phone', 'email',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'form_id', 'source_page'
  ],
  bot_raw: [
    'timestamp', 'telegram_id', 'telegram_username', 'event', 'step',
    'bot_name', 'payload',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content'
  ],
  zoom_raw: [
    'webinar_id', 'webinar_name', 'name', 'telegram', 'phone', 'email',
    'join_time', 'leave_time', 'duration_min', 'watched_to_sale',
    'attended', 'source_file'
  ],
  course_site_raw: [
    'timestamp', 'event', 'client_id', 'page_url',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'referrer'
  ],
  course_form_raw: [
    'timestamp', 'client_id', 'name', 'telegram', 'phone', 'email',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
    'form_id', 'source_page'
  ],
  sales_raw: [
    'timestamp', 'name', 'telegram', 'phone', 'email',
    'status', 'amount', 'payment_date', 'payment_method',
    'reason_lost', 'comment', 'manager'
  ],

  // CALCULATED
  clean_events: [
    'event_id', 'timestamp', 'source_table', 'event_type',
    'client_id', 'telegram_id', 'telegram_norm', 'phone_norm', 'email_norm', 'name_norm',
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_content',
    'webinar_id', 'duration_min', 'status', 'amount', 'raw_row_id'
  ],
  identity_map: [
    'identifier_type', 'identifier_value', 'person_id',
    'match_strength', 'first_seen_at', 'last_seen_at',
    'source_tables', 'conflict_flag'
  ],
  people: [
    'person_id', 'first_seen_at', 'last_seen_at',
    'first_source', 'first_utm_medium', 'first_utm_campaign', 'first_utm_content',
    'telegram_id', 'telegram_norm', 'phone_norm', 'email_norm', 'client_ids',
    'match_quality',
    'has_webinar_form', 'has_bot', 'has_zoom', 'has_course_form', 'has_sale', 'has_payment',
    'total_amount', 'notes'
  ],
  funnel: [
    'person_id', 'source', 'utm_medium', 'utm_campaign', 'utm_content',
    'webinar_site_visit', 'webinar_form_submit', 'bot_started',
    'zoom_attended', 'zoom_duration_min', 'watched_to_sale',
    'course_site_visit', 'course_form_submit',
    'sale_status', 'paid', 'amount', 'payment_date',
    'match_quality', 'data_conflicts'
  ],
  dashboard: [
    'section', 'metric', 'value',
    'conversion_from_previous', 'conversion_from_start',
    'source', 'notes'
  ],
  data_quality: [
    'issue_type', 'severity', 'source_table',
    'raw_row_id', 'person_id', 'description', 'suggested_fix'
  ],
  settings: [
    'key', 'value', 'description'
  ]
};

// Tab colors: RAW = light red, CALCULATED = light blue
var TAB_COLORS = {
  site_webinar_raw:  '#fce8e6',
  form_webinar_raw:  '#fce8e6',
  bot_raw:           '#fce8e6',
  zoom_raw:          '#fce8e6',
  course_site_raw:   '#fce8e6',
  course_form_raw:   '#fce8e6',
  sales_raw:         '#fce8e6',
  clean_events:      '#e8f0fe',
  identity_map:      '#e8f0fe',
  people:            '#e8f0fe',
  funnel:            '#e8f0fe',
  dashboard:         '#e8f0fe',
  data_quality:      '#e8f0fe',
  settings:          '#e8f0fe'
};

// ============================================================

function createSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  Object.keys(SHEETS).forEach(function(sheetName) {
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) {
      sheet = ss.insertSheet(sheetName);
    }
    if (TAB_COLORS[sheetName]) {
      sheet.setTabColor(TAB_COLORS[sheetName]);
    }
  });

  // Remove default "Sheet1" if it still exists and is empty
  var defaultSheet = ss.getSheetByName('Sheet1');
  if (defaultSheet && ss.getSheets().length > 1) {
    ss.deleteSheet(defaultSheet);
  }
}

function setupHeaders() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  Object.keys(SHEETS).forEach(function(sheetName) {
    var sheet = ss.getSheetByName(sheetName);
    if (!sheet) return;

    var headers = SHEETS[sheetName];

    // Write headers to row 1
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);

    // Style header row: bold, gray background, freeze
    var headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange
      .setFontWeight('bold')
      .setBackground('#f3f3f3')
      .setWrap(false);

    sheet.setFrozenRows(1);

    // Auto-resize columns for readability
    sheet.autoResizeColumns(1, headers.length);
  });
}

function runSetup() {
  createSheets();
  setupHeaders();
  SpreadsheetApp.getUi().alert(
    'Analytics MVP',
    'Setup complete.\n\n' +
    'RAW sheets: site_webinar_raw, form_webinar_raw, bot_raw, zoom_raw, ' +
    'course_site_raw, course_form_raw, sales_raw\n\n' +
    'Calculated sheets: clean_events, identity_map, people, funnel, ' +
    'dashboard, data_quality, settings',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function runPipeline() {
  buildCleanEvents();
  buildIdentityAndPeople();
  buildFunnel();
  buildDashboard();
  SpreadsheetApp.getUi().alert(
    'Analytics MVP',
    'Pipeline complete: clean_events → identity_map → people → funnel → dashboard',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Analytics MVP')
    .addItem('Run setup', 'runSetup')
    .addSeparator()
    .addItem('▶ Run full pipeline', 'runPipeline')
    .addSeparator()
    .addItem('Build clean_events', 'buildCleanEvents')
    .addItem('Build identity + people', 'buildIdentityAndPeople')
    .addItem('Build funnel', 'buildFunnel')
    .addItem('Build dashboard', 'buildDashboard')
    .addSeparator()
    .addItem('[DEV] Load test data', 'loadTestData')
    .addToUi();
}
