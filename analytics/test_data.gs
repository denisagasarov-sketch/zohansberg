// ============================================================
// EdTech Analytics MVP — Test Data
// ============================================================
//
// 4 тестовые персоны:
//   A. Иван Петров    — полная воронка, оплатил
//   B. Мария Сидорова — вебинар + зум, не купила
//   C. Алексей Козлов — только бот
//   D. Наталья Волкова — форма + сделка без оплаты
//
// Персона A намеренно появляется под разными идентификаторами
// в разных источниках — для проверки склейки.

function loadTestData() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  _writeTestSheet(ss, 'site_webinar_raw', [
    // timestamp, event, client_id, page_url, utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer
    ['2024-03-01 10:00:00', 'pageview', 'cid_abc111', 'https://webinar.site/landing', 'facebook', 'cpc',     'webinar_march', 'ad1', '',       'https://facebook.com'],
    ['2024-03-01 10:01:30', 'pageview', 'cid_abc111', 'https://webinar.site/landing', 'facebook', 'cpc',     'webinar_march', 'ad1', '',       'https://facebook.com'],
    ['2024-03-01 11:15:00', 'pageview', 'cid_bbb222', 'https://webinar.site/landing', 'vk',       'cpc',     'webinar_march', 'ad2', '',       'https://vk.com'],
    ['2024-03-01 14:20:00', 'pageview', 'cid_ccc333', 'https://webinar.site/landing', 'organic',  'organic', '',              '',    'курсы',  'https://google.com'],
    ['2024-03-01 14:21:00', 'scroll',   'cid_ccc333', 'https://webinar.site/landing', 'organic',  'organic', '',              '',    'курсы',  'https://google.com'],
  ]);

  _writeTestSheet(ss, 'form_webinar_raw', [
    // timestamp, client_id, name, telegram, phone, email, utm_source, utm_medium, utm_campaign, utm_content, utm_term, form_id, source_page
    ['2024-03-01 10:15:00', 'cid_abc111', 'Иван Петров',    '@Ivan_Petrov',   '+7 (916) 123-45-67', 'ivan@test.ru',    'facebook', 'cpc',     'webinar_march', 'ad1', '', 'form_webinar', 'https://webinar.site/landing'],
    ['2024-03-01 11:30:00', 'cid_bbb222', 'Мария Сидорова', '@maria_s',       '8 926 234-56-78',    'maria@test.ru',   'vk',       'cpc',     'webinar_march', 'ad2', '', 'form_webinar', 'https://webinar.site/landing'],
    ['2024-03-02 09:05:00', '',           'Наталья Волкова','',               '+79031112233',       'natalia@test.ru', 'email',    'email',   'followup',      '',    '', 'form_webinar', 'https://webinar.site/replay'],
  ]);

  _writeTestSheet(ss, 'bot_raw', [
    // timestamp, telegram_id, telegram_username, event, step, bot_name, payload, utm_source, utm_medium, utm_campaign, utm_content
    ['2024-03-01 10:16:00', '123456789', 'Ivan_Petrov',  'start',    'welcome',   'analytics_bot', '',            'facebook', 'cpc',   'webinar_march', 'ad1'],
    ['2024-03-01 10:17:00', '123456789', 'Ivan_Petrov',  'button',   'materials', 'analytics_bot', 'get_pdf',     '',         '',      '',              ''   ],
    ['2024-03-01 12:00:00', '555000111', 'alexei_k',     'start',    'welcome',   'analytics_bot', '',            'vk',       'cpc',   'webinar_march', 'ad3'],
    ['2024-03-01 12:05:00', '555000111', 'alexei_k',     'button',   'schedule',  'analytics_bot', 'get_time',    '',         '',      '',              ''   ],
    ['2024-03-01 11:31:00', '777333999', 'maria_s',      'start',    'welcome',   'analytics_bot', '',            'vk',       'cpc',   'webinar_march', 'ad2'],
  ]);

  _writeTestSheet(ss, 'zoom_raw', [
    // webinar_id, webinar_name, name, telegram, phone, email, join_time, leave_time, duration_min, watched_to_sale, attended, source_file
    ['webinar_2024_03_05', 'Вебинар март 2024', 'Иван Петров',    'Ivan_Petrov', '+79161234567', 'ivan@test.ru',    '2024-03-05 19:00', '2024-03-05 21:10', '130', 'TRUE',  'TRUE', 'zoom_export_march.csv'],
    ['webinar_2024_03_05', 'Вебинар март 2024', 'Мария Сидорова', 'maria_s',     '79262345678',  'maria@test.ru',   '2024-03-05 19:02', '2024-03-05 20:15', '73',  'FALSE', 'TRUE', 'zoom_export_march.csv'],
    ['webinar_2024_03_05', 'Вебинар март 2024', 'Петр Новиков',   '',            '',             'novikov@mail.ru', '2024-03-05 19:10', '2024-03-05 19:40', '30',  'FALSE', 'TRUE', 'zoom_export_march.csv'],
  ]);

  _writeTestSheet(ss, 'course_site_raw', [
    // timestamp, event, client_id, page_url, utm_source, utm_medium, utm_campaign, utm_content, utm_term, referrer
    ['2024-03-06 10:00:00', 'pageview', 'cid_abc111', 'https://course.site/program', 'email',    'email',   'after_webinar', '',    '', ''],
    ['2024-03-06 10:02:00', 'pageview', 'cid_abc111', 'https://course.site/price',   'email',    'email',   'after_webinar', '',    '', ''],
    ['2024-03-06 10:03:00', 'scroll',   'cid_abc111', 'https://course.site/price',   'email',    'email',   'after_webinar', '',    '', ''],
    ['2024-03-06 11:00:00', 'pageview', 'cid_bbb222', 'https://course.site/program', 'direct',   'direct',  '',              '',    '', ''],
  ]);

  _writeTestSheet(ss, 'course_form_raw', [
    // timestamp, client_id, name, telegram, phone, email, utm_source, utm_medium, utm_campaign, utm_content, utm_term, form_id, source_page
    ['2024-03-06 10:10:00', 'cid_abc111', 'Иван Петров', '@Ivan_Petrov', '+79161234567', 'ivan@test.ru',  'email', 'email', 'after_webinar', '', '', 'form_course', 'https://course.site/price'],
  ]);

  _writeTestSheet(ss, 'sales_raw', [
    // timestamp, name, telegram, phone, email, status, amount, payment_date, payment_method, reason_lost, comment, manager
    ['2024-03-07 14:00:00', 'Иван Петров',    '@Ivan_Petrov',   '+79161234567', 'ivan@test.ru',    'paid',    49000, '2024-03-07', 'card',   '',              '',                  'Анна'],
    ['2024-03-08 10:00:00', 'Наталья Волкова','',               '+79031112233', 'natalia@test.ru', 'no_sale', '',    '',           '',       'дорого',        'перезвонить через месяц', 'Анна'],
    ['2024-03-09 12:00:00', 'Мария Сидорова', '@maria_s',       '79262345678',  'maria@test.ru',   'think',   '',    '',           '',       '',              '',                  'Анна'],
  ]);

  Logger.log('loadTestData: test data written to all RAW sheets');
  SpreadsheetApp.getUi().alert(
    'Test data loaded',
    'Тестовые данные добавлены во все RAW-листы.\nЗапусти ▶ Run full pipeline.',
    SpreadsheetApp.getUi().ButtonSet.OK
  );
}

function _writeTestSheet(ss, sheetName, rows) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) { Logger.log('Sheet not found: ' + sheetName); return; }

  var lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).clearContent();

  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
  }
}
