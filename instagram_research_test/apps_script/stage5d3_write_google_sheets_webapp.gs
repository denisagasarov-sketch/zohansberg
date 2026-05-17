/**
 * Stage 5D-3: Google Sheets Write Web App
 *
 * Exposes doPost(e) only.
 * Supported modes: "validate", "write"
 * Rejected modes:  "append", "clear", "sync", and any unknown mode.
 *
 * Required Script Property (Project Settings → Script Properties):
 *   SYNC_SECRET — long random secret string; never hardcoded here.
 *
 * Write behaviour:
 *   - Row 1 (headers) and row 2 (comments/hints) are NEVER touched.
 *   - Data is written starting at row 3.
 *   - Old content from row 3 downward is removed with clearContent()
 *     before writing. Formatting, notes, and validations are preserved.
 *   - Sheets with rows=[] are skipped unless allow_empty_clear=true.
 *   - Atomic: all target sheets are validated before any write begins.
 *   - LockService prevents concurrent writes.
 *
 * Allowed write methods: setValues(), clearContent()
 * Forbidden:            clear(), appendRow(), deleteRow(), insertRow(),
 *                       deleteSheet(), insertSheet(), copyTo(), moveActiveSheet()
 */

var EXPECTED_SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ";
var REQUIRED_START_ROW      = 3;
var REJECTED_MODES          = ["append", "clear", "sync"];


// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function doPost(e) {
  var response = {
    ok: false,
    mode: null,
    spreadsheet_id: null,
    spreadsheet_name: null,
    spreadsheet_url: null,
    start_row: REQUIRED_START_ROW,
    write_id: null,
    validated: false,
    written: false,
    only_sheet: null,
    allow_empty_clear: false,
    sheets: {},
    errors: [],
    warnings: []
  };

  try {
    // Parse JSON body
    var body;
    try {
      body = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      response.errors.push("Invalid JSON body: " + parseErr.message);
      return _jsonResponse(response);
    }

    // Validate secret
    var secretError = _validateSecret(body.secret);
    if (secretError) {
      response.errors.push(secretError);
      return _jsonResponse(response);
    }

    // Validate mode
    var mode = body.mode;
    response.mode = mode;
    if (!mode) {
      response.errors.push("'mode' field is required.");
      return _jsonResponse(response);
    }
    if (REJECTED_MODES.indexOf(mode) !== -1) {
      response.errors.push(
        "Mode '" + mode + "' is rejected. Supported modes: validate, write."
      );
      return _jsonResponse(response);
    }
    if (mode !== "validate" && mode !== "write") {
      response.errors.push(
        "Unknown mode: '" + mode + "'. Supported modes: validate, write."
      );
      return _jsonResponse(response);
    }

    // Validate spreadsheet_id
    var spreadsheetId = body.spreadsheet_id;
    response.spreadsheet_id = spreadsheetId;
    if (!spreadsheetId) {
      response.errors.push("'spreadsheet_id' field is required.");
      return _jsonResponse(response);
    }
    if (spreadsheetId !== EXPECTED_SPREADSHEET_ID) {
      response.errors.push(
        "spreadsheet_id mismatch: got '" + spreadsheetId +
        "', expected '" + EXPECTED_SPREADSHEET_ID + "'."
      );
      return _jsonResponse(response);
    }

    // Validate start_row
    var startRow = body.start_row;
    if (startRow !== REQUIRED_START_ROW) {
      response.errors.push(
        "start_row must be " + REQUIRED_START_ROW + ", got: " + startRow
      );
      return _jsonResponse(response);
    }

    // Parse options
    var writeId        = body.write_id        || null;
    var allowEmptyClear = body.allow_empty_clear === true ? true : false;
    var onlySheet      = body.only_sheet       || null;
    var renameHeaders  = body.rename_headers   === true ? true : false;
    response.write_id        = writeId;
    response.allow_empty_clear = allowEmptyClear;
    response.only_sheet      = onlySheet;
    response.rename_headers  = renameHeaders;

    // Validate sheets payload
    var sheetsPayload = body.sheets;
    if (!sheetsPayload || typeof sheetsPayload !== "object") {
      response.errors.push("'sheets' field is required and must be an object.");
      return _jsonResponse(response);
    }

    // Validate only_sheet exists in payload
    if (onlySheet && !(onlySheet in sheetsPayload)) {
      response.errors.push(
        "only_sheet '" + onlySheet + "' is not present in payload sheets. " +
        "Available: " + Object.keys(sheetsPayload).join(", ")
      );
      return _jsonResponse(response);
    }

    // Determine target sheets
    var targetSheetNames = onlySheet ? [onlySheet] : Object.keys(sheetsPayload);

    // Validate every row length in payload before opening spreadsheet
    for (var si = 0; si < targetSheetNames.length; si++) {
      var tsName = targetSheetNames[si];
      var tsData = sheetsPayload[tsName];
      var tsHeaders = tsData.headers || [];
      var tsRows    = tsData.rows    || [];
      for (var ri = 0; ri < tsRows.length; ri++) {
        if (tsRows[ri].length !== tsHeaders.length) {
          response.errors.push(
            "Sheet '" + tsName + "', row " + ri + ": length " +
            tsRows[ri].length + " != headers length " + tsHeaders.length
          );
        }
      }
    }
    if (response.errors.length > 0) {
      return _jsonResponse(response);
    }

    // Open spreadsheet
    var ss;
    try {
      ss = SpreadsheetApp.openById(spreadsheetId);
    } catch (openErr) {
      response.errors.push("Cannot open spreadsheet: " + openErr.message);
      return _jsonResponse(response);
    }

    response.spreadsheet_name = ss.getName();
    response.spreadsheet_url  = ss.getUrl();

    // Collect all sheet names for similarity lookup
    var allSheetNames = ss.getSheets().map(function(s) { return s.getName(); });

    // Extra sheets warning (validate mode checks all sheets in payload)
    var payloadSheetNames = Object.keys(sheetsPayload);
    allSheetNames.forEach(function(ssName) {
      if (payloadSheetNames.indexOf(ssName) === -1) {
        response.warnings.push(
          "Sheet '" + ssName + "' exists in spreadsheet but not in payload. It will not be touched."
        );
      }
    });

    // -----------------------------------------------------------------------
    // Validate mode
    // -----------------------------------------------------------------------
    if (mode === "validate") {
      targetSheetNames.forEach(function(sheetName) {
        var sheetResult = _validateSheet(ss, sheetName, sheetsPayload[sheetName], allSheetNames);
        response.sheets[sheetName] = sheetResult;
        if (!sheetResult.ok) {
          response.errors.push("Validation failed for sheet: '" + sheetName + "'.");
        }
      });
      response.validated = (response.errors.length === 0);
      response.ok        = response.validated;
      response.written   = false;
      return _jsonResponse(response);
    }

    // -----------------------------------------------------------------------
    // Write mode — optionally rename headers before validation
    // -----------------------------------------------------------------------
    if (renameHeaders) {
      for (var ri = 0; ri < targetSheetNames.length; ri++) {
        var rSheetName = targetSheetNames[ri];
        var rPayload   = sheetsPayload[rSheetName];
        var rHeaders   = (rPayload && rPayload.headers) ? rPayload.headers : [];
        if (rHeaders.length === 0) continue;
        var rSheet = ss.getSheetByName(rSheetName);
        if (!rSheet) continue;
        try {
          rSheet.getRange(1, 1, 1, rHeaders.length).setValues([rHeaders]);
          response.warnings.push("rename_headers: updated row 1 headers in '" + rSheetName + "'.");
        } catch (renameErr) {
          response.errors.push("rename_headers: failed to update '" + rSheetName + "': " + renameErr.message);
        }
      }
      if (response.errors.length > 0) {
        return _jsonResponse(response);
      }
    }

    // -----------------------------------------------------------------------
    // Write mode — validate all target sheets first (atomic)
    // -----------------------------------------------------------------------
    var validationResults = {};
    var validationPassed  = true;

    targetSheetNames.forEach(function(sheetName) {
      var sheetResult = _validateSheet(ss, sheetName, sheetsPayload[sheetName], allSheetNames);
      validationResults[sheetName] = sheetResult;
      response.sheets[sheetName] = sheetResult;
      if (!sheetResult.ok) {
        validationPassed = false;
        response.errors.push("Validation failed for sheet: '" + sheetName + "'. Aborting write.");
      }
    });

    response.validated = validationPassed;

    if (!validationPassed) {
      response.written = false;
      return _jsonResponse(response);
    }

    // -----------------------------------------------------------------------
    // Acquire lock and write
    // -----------------------------------------------------------------------
    var lock = LockService.getScriptLock();
    try {
      lock.waitLock(30000);

      var allWriteOk = true;
      for (var wi = 0; wi < targetSheetNames.length; wi++) {
        var sheetName = targetSheetNames[wi];
        var sheetData = sheetsPayload[sheetName];
        var writeResult = _writeSheet(ss, sheetName, sheetData, allowEmptyClear, body.account_label || "");
        // Merge write result into existing validation result
        var existing = response.sheets[sheetName];
        existing.existing_last_row_before_write    = writeResult.existing_last_row_before_write;
        existing.existing_last_column_before_write = writeResult.existing_last_column_before_write;
        existing.cleared_range   = writeResult.cleared_range;
        existing.cleared_rows    = writeResult.cleared_rows;
        existing.written_range   = writeResult.written_range;
        existing.written_rows    = writeResult.written_rows;
        existing.skipped         = writeResult.skipped;
        existing.skipped_reason  = writeResult.skipped_reason;
        if (writeResult.errors && writeResult.errors.length > 0) {
          existing.errors = (existing.errors || []).concat(writeResult.errors);
          existing.ok = false;
          allWriteOk  = false;
        }
        if (writeResult.warnings && writeResult.warnings.length > 0) {
          existing.warnings = (existing.warnings || []).concat(writeResult.warnings);
        }
      }

      response.written = allWriteOk;
      response.ok      = allWriteOk;

    } catch (lockErr) {
      response.errors.push("Could not acquire write lock: " + lockErr.message);
      response.written = false;
    } finally {
      lock.releaseLock();
    }

  } catch (topErr) {
    response.errors.push("Unexpected error: " + topErr.message);
  }

  return _jsonResponse(response);
}


// ---------------------------------------------------------------------------
// Secret validation
// ---------------------------------------------------------------------------

function _validateSecret(providedSecret) {
  var props          = PropertiesService.getScriptProperties();
  var expectedSecret = props.getProperty("SYNC_SECRET");
  if (!expectedSecret) {
    return "SYNC_SECRET is not set in Script Properties. Configure it before using this Web App.";
  }
  if (!providedSecret) {
    return "Request is missing 'secret' field.";
  }
  if (!_safeEquals(providedSecret, expectedSecret)) {
    return "Invalid secret.";
  }
  return null;
}

function _safeEquals(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  if (a.length !== b.length) return false;
  var result = 0;
  for (var i = 0; i < a.length; i++) {
    result |= (a.charCodeAt(i) ^ b.charCodeAt(i));
  }
  return result === 0;
}


// ---------------------------------------------------------------------------
// Sheet validator
// ---------------------------------------------------------------------------

function _validateSheet(ss, sheetName, sheetPayload, allSheetNames) {
  var result = {
    ok: false,
    exists: false,
    payload_headers_count: 0,
    payload_rows_count: 0,
    row2_present: false,
    mismatches: [],
    errors: [],
    warnings: [],
    similar_sheet_names: [],
    // write fields initialised to null
    existing_last_row_before_write: null,
    existing_last_column_before_write: null,
    cleared_range: null,
    cleared_rows: null,
    written_range: null,
    written_rows: null,
    skipped: false,
    skipped_reason: null
  };

  var payloadHeaders = sheetPayload.headers || [];
  var payloadRows    = sheetPayload.rows    || [];
  result.payload_headers_count = payloadHeaders.length;
  result.payload_rows_count    = payloadRows.length;

  var sheet;
  try {
    sheet = ss.getSheetByName(sheetName);
  } catch (e) {
    result.errors.push("Error looking up sheet: " + e.message);
    return result;
  }

  if (!sheet) {
    result.exists = false;
    result.errors.push("Sheet '" + sheetName + "' not found in spreadsheet.");
    result.similar_sheet_names = _similarNames(sheetName, allSheetNames);
    if (result.similar_sheet_names.length > 0) {
      result.warnings.push(
        "Similar sheet names found (possible typo/spacing): " +
        result.similar_sheet_names.join(", ")
      );
    }
    return result;
  }
  result.exists = true;

  if (payloadHeaders.length === 0) {
    result.warnings.push("No headers in payload for this sheet; skipping header validation.");
    result.ok = true;
    return result;
  }

  // Read row 1
  var lastCol    = sheet.getLastColumn();
  var readWidth  = Math.max(payloadHeaders.length + 5, lastCol > 0 ? Math.min(lastCol, payloadHeaders.length + 5) : payloadHeaders.length + 5);
  var row1Values = [];
  try {
    if (lastCol >= 1) {
      var readCols = Math.min(readWidth, lastCol);
      row1Values   = sheet.getRange(1, 1, 1, readCols).getValues()[0];
    }
  } catch (e) {
    result.errors.push("Cannot read row 1: " + e.message);
    return result;
  }

  // Compare headers
  for (var i = 0; i < payloadHeaders.length; i++) {
    var expected = payloadHeaders[i];
    var actual   = (row1Values[i] !== undefined && row1Values[i] !== null)
                   ? String(row1Values[i]) : "";
    if (actual !== expected) {
      var msg = actual === ""
        ? "Column " + (i + 1) + ": expected '" + expected + "', but cell is empty."
        : "Column " + (i + 1) + ": expected '" + expected + "', got '" + actual + "'.";
      result.errors.push(msg);
      result.mismatches.push({ col: i + 1, expected: expected, actual: actual });
    }
  }

  // Extra non-empty headers beyond payload width
  for (var j = payloadHeaders.length; j < row1Values.length; j++) {
    var extra = (row1Values[j] !== null && row1Values[j] !== undefined)
                ? String(row1Values[j]).trim() : "";
    if (extra !== "") {
      result.errors.push(
        "Extra non-empty header at column " + (j + 1) + ": '" + extra +
        "' (beyond payload width " + payloadHeaders.length + ")."
      );
    }
  }

  // Row 2 presence (warning only)
  try {
    var lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      var row2 = sheet.getRange(2, 1, 1, Math.max(1, payloadHeaders.length)).getValues()[0];
      var row2HasContent = row2.some(function(c) {
        return c !== null && c !== undefined && String(c).trim() !== "";
      });
      result.row2_present = row2HasContent;
      if (!row2HasContent) {
        result.warnings.push("Row 2 exists but all cells are empty; no comment/hint row found.");
      }
    } else {
      result.row2_present = false;
      result.warnings.push("Row 2 does not exist in sheet '" + sheetName + "'.");
    }
  } catch (e) {
    result.warnings.push("Could not read row 2: " + e.message);
  }

  result.ok = (result.errors.length === 0);
  return result;
}


// ---------------------------------------------------------------------------
// Sheet writer
// ---------------------------------------------------------------------------

function _writeSheet(ss, sheetName, sheetData, allowEmptyClear, accountLabel) {
  var result = {
    existing_last_row_before_write: null,
    existing_last_column_before_write: null,
    cleared_range: null,
    cleared_rows: null,
    written_range: null,
    written_rows: null,
    skipped: false,
    skipped_reason: null,
    errors: [],
    warnings: []
  };

  var headers = sheetData.headers || [];
  var rows    = sheetData.rows    || [];

  if (rows.length === 0 && !allowEmptyClear) {
    result.skipped        = true;
    result.skipped_reason = "empty_rows_no_clear";
    result.warnings.push(
      "Sheet '" + sheetName + "' has 0 rows and allow_empty_clear=false; data rows not touched."
    );
    return result;
  }

  var sheet;
  try {
    sheet = ss.getSheetByName(sheetName);
  } catch (e) {
    result.errors.push("Cannot get sheet '" + sheetName + "': " + e.message);
    return result;
  }
  if (!sheet) {
    result.errors.push("Sheet '" + sheetName + "' not found.");
    return result;
  }

  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  result.existing_last_row_before_write    = lastRow;
  result.existing_last_column_before_write = lastCol;

  var writeStartRow = REQUIRED_START_ROW;
  var lastColLetter = _colLetter(headers.length);

  if (accountLabel && accountLabel.trim() !== "" && lastRow >= REQUIRED_START_ROW) {
    // Scan column A from row 3 to lastRow — find rows matching accountLabel
    var colARange  = sheet.getRange(REQUIRED_START_ROW, 1, lastRow - REQUIRED_START_ROW + 1, 1);
    var colAValues = colARange.getValues();
    var firstMatchRow = -1;
    var lastMatchRow  = -1;

    for (var ri = 0; ri < colAValues.length; ri++) {
      var cellVal = String(colAValues[ri][0] || "").trim();
      // Use indexOf so we match regardless of historical format:
      // "kate.jet", "https://www.instagram.com/kate.jet/", "@kate.jet https://..."
      if (cellVal !== "" && cellVal.indexOf(accountLabel.trim()) !== -1) {
        if (firstMatchRow === -1) firstMatchRow = REQUIRED_START_ROW + ri;
        lastMatchRow = REQUIRED_START_ROW + ri;
      }
    }

    if (firstMatchRow !== -1) {
      // Found existing rows for this account — clear them
      var existingCount = lastMatchRow - firstMatchRow + 1;
      var clearRange = sheet.getRange(firstMatchRow, 1, existingCount, headers.length);
      clearRange.clearContent();
      result.cleared_range = "A" + firstMatchRow + ":" + lastColLetter + lastMatchRow;
      result.cleared_rows  = existingCount;
      writeStartRow = firstMatchRow;

      // Warning if row count changed
      if (rows.length !== existingCount) {
        result.warnings.push(
          "Row count changed for '" + accountLabel + "' in sheet '" + sheetName + "': " +
          "was " + existingCount + ", now " + rows.length + ". " +
          "Existing rows cleared, new rows written. Check for gaps if count decreased."
        );
      }
    } else {
      // Not found — append after last data row
      writeStartRow = lastRow + 1;
      result.cleared_range = null;
      result.cleared_rows  = 0;
    }

  } else {
    // No accountLabel — fallback: clear from row 3 (original behavior)
    if (lastRow >= REQUIRED_START_ROW) {
      var clearRows  = lastRow - REQUIRED_START_ROW + 1;
      var clearRange = sheet.getRange(REQUIRED_START_ROW, 1, clearRows, headers.length);
      clearRange.clearContent();
      result.cleared_range = "A" + REQUIRED_START_ROW + ":" + lastColLetter + lastRow;
      result.cleared_rows  = clearRows;
    } else {
      result.cleared_range = null;
      result.cleared_rows  = 0;
    }
    writeStartRow = REQUIRED_START_ROW;
  }

  // Write rows starting at writeStartRow
  if (rows.length > 0) {
    try {
      var writeRange = sheet.getRange(writeStartRow, 1, rows.length, headers.length);
      writeRange.setValues(rows);
      var endRow = writeStartRow + rows.length - 1;
      result.written_range = "A" + writeStartRow + ":" + lastColLetter + endRow;
      result.written_rows  = rows.length;
    } catch (writeErr) {
      result.errors.push("Error writing rows to '" + sheetName + "': " + writeErr.message);
    }
  } else {
    result.written_range = null;
    result.written_rows  = 0;
  }

  // Restore header/hint row styles after any write operation
  try {
    _restoreHeaderStyle(sheet, headers.length);
  } catch (styleErr) {
    result.warnings.push("Could not restore header style: " + styleErr.message);
  }

  return result;
}


// ---------------------------------------------------------------------------
// Header style restorer
// ---------------------------------------------------------------------------

function _restoreHeaderStyle(sheet, numCols) {
  var cols = numCols || sheet.getLastColumn();
  if (cols < 1) return;

  // Row 1: bold, pink background, black text, wrap
  var r1 = sheet.getRange(1, 1, 1, cols);
  r1.setFontWeight("bold");
  r1.setBackground("#f4c7cd");
  r1.setFontColor("#000000");
  r1.setWrap(true);

  // Row 2: italic, green background, black text, wrap, 40px height
  var r2 = sheet.getRange(2, 1, 1, cols);
  r2.setFontStyle("italic");
  r2.setBackground("#d9ead3");
  r2.setFontColor("#000000");
  r2.setWrap(true);
  sheet.setRowHeight(2, 40);

  // Freeze first 2 rows
  sheet.setFrozenRows(2);
}


// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function _colLetter(n) {
  // Convert 1-based column number to A-Z, AA-ZZ, etc.
  var result = "";
  while (n > 0) {
    var rem = (n - 1) % 26;
    result  = String.fromCharCode(65 + rem) + result;
    n       = Math.floor((n - 1) / 26);
  }
  return result;
}

function _similarNames(target, candidates) {
  var tLower  = target.toLowerCase().trim().replace(/\s+/g, " ");
  var similar = [];
  candidates.forEach(function(c) {
    var cLower = c.toLowerCase().trim().replace(/\s+/g, " ");
    if (cLower === tLower || cLower.indexOf(tLower) !== -1 || tLower.indexOf(cLower) !== -1) {
      similar.push(c);
    } else if (_editDistance(tLower, cLower) <= Math.max(2, Math.floor(tLower.length * 0.25))) {
      similar.push(c);
    }
  });
  return similar.filter(function(c) { return c !== target; });
}

function _editDistance(a, b) {
  var m = a.length, n = b.length;
  var dp = [];
  for (var i = 0; i <= m; i++) {
    dp[i] = [i];
    for (var j = 1; j <= n; j++) dp[i][j] = 0;
  }
  for (var j = 0; j <= n; j++) dp[0][j] = j;
  for (var i = 1; i <= m; i++) {
    for (var j = 1; j <= n; j++) {
      dp[i][j] = a[i-1] === b[j-1]
        ? dp[i-1][j-1]
        : 1 + Math.min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]);
    }
  }
  return dp[m][n];
}

function _jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
