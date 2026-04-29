// ============================================================
// EdTech Analytics MVP — Normalization Functions
// ============================================================

function isEmpty(value) {
  return value === null || value === undefined || String(value).trim() === '';
}

function normalizeTelegram(value) {
  if (isEmpty(value)) return '';
  var result = String(value).trim().toLowerCase().replace(/@/g, '').replace(/\s+/g, '');
  return result === '' ? '' : result;
}

function normalizePhone(value) {
  if (isEmpty(value)) return '';
  var digits = String(value).replace(/\D/g, '');
  if (digits.length === 11 && digits.charAt(0) === '8') {
    digits = '7' + digits.slice(1);
  }
  if (digits.length < 7) return '';
  return digits;
}

function normalizeEmail(value) {
  if (isEmpty(value)) return '';
  return String(value).trim().toLowerCase();
}

function normalizeUtm(value) {
  if (isEmpty(value)) return '';
  return String(value).trim().toLowerCase();
}

function normalizeName(value) {
  if (isEmpty(value)) return '';
  return String(value).trim().replace(/\s+/g, ' ').toLowerCase();
}

function isValidPhone(value) {
  var normalized = normalizePhone(value);
  return normalized !== '';
}

// ============================================================
// Manual test — run from Apps Script editor, check Execution Log
// ============================================================

function testNormalization() {
  var tests = [
    // normalizeTelegram
    { fn: 'normalizeTelegram', input: ' @Denis_Test ',       expected: 'denis_test' },
    { fn: 'normalizeTelegram', input: '@UPPER',              expected: 'upper' },
    { fn: 'normalizeTelegram', input: '   ',                 expected: '' },
    { fn: 'normalizeTelegram', input: '',                    expected: '' },
    { fn: 'normalizeTelegram', input: null,                  expected: '' },

    // normalizePhone
    { fn: 'normalizePhone',    input: '+7 (999) 123-45-67',  expected: '79991234567' },
    { fn: 'normalizePhone',    input: '89991234567',         expected: '79991234567' },
    { fn: 'normalizePhone',    input: '79991234567',         expected: '79991234567' },
    { fn: 'normalizePhone',    input: '123',                 expected: '' },
    { fn: 'normalizePhone',    input: '',                    expected: '' },
    { fn: 'normalizePhone',    input: null,                  expected: '' },

    // normalizeEmail
    { fn: 'normalizeEmail',    input: '  User@Example.COM ', expected: 'user@example.com' },
    { fn: 'normalizeEmail',    input: '',                    expected: '' },
    { fn: 'normalizeEmail',    input: null,                  expected: '' },

    // normalizeUtm
    { fn: 'normalizeUtm',      input: '  Facebook_ADS ',    expected: 'facebook_ads' },
    { fn: 'normalizeUtm',      input: '',                    expected: '' },

    // normalizeName
    { fn: 'normalizeName',     input: '  Ivan   Ivanov ',   expected: 'ivan ivanov' },
    { fn: 'normalizeName',     input: '',                    expected: '' },
    { fn: 'normalizeName',     input: null,                  expected: '' },

    // isValidPhone
    { fn: 'isValidPhone',      input: '+7 (999) 123-45-67', expected: true },
    { fn: 'isValidPhone',      input: '123',                expected: false },
    { fn: 'isValidPhone',      input: '',                   expected: false },

    // isEmpty
    { fn: 'isEmpty',           input: '',                   expected: true },
    { fn: 'isEmpty',           input: '  ',                 expected: true },
    { fn: 'isEmpty',           input: null,                 expected: true },
    { fn: 'isEmpty',           input: 'hello',              expected: false }
  ];

  var fns = {
    normalizeTelegram: normalizeTelegram,
    normalizePhone:    normalizePhone,
    normalizeEmail:    normalizeEmail,
    normalizeUtm:      normalizeUtm,
    normalizeName:     normalizeName,
    isValidPhone:      isValidPhone,
    isEmpty:           isEmpty
  };

  var passed = 0;
  var failed = 0;

  tests.forEach(function(t) {
    var result = fns[t.fn](t.input);
    var ok = result === t.expected;
    if (ok) {
      passed++;
      Logger.log('PASS  ' + t.fn + '(' + JSON.stringify(t.input) + ') → ' + JSON.stringify(result));
    } else {
      failed++;
      Logger.log('FAIL  ' + t.fn + '(' + JSON.stringify(t.input) + ') → got ' + JSON.stringify(result) + ', expected ' + JSON.stringify(t.expected));
    }
  });

  Logger.log('---');
  Logger.log('Results: ' + passed + ' passed, ' + failed + ' failed');
}
