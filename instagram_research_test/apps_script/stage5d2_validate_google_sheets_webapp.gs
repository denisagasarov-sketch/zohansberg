/**
 * Stage 5D-2: Google Sheets Validate-Only Web App
 *
 * Exposes doPost(e) only.
 * Supported mode: "validate"
 * Rejected modes: "write", "sync", "append", "clear", and any unknown mode.
 *
 * Required Script Property (Project Settings → Script Properties):
 *   SYNC_SECRET — long random secret string; never hardcoded here.
 *
 * This script performs READ-ONLY operations only.
 * It never writes, clears, inserts, appends, or deletes any cell, row, or sheet.
 */

var EXPECTED_SPREADSHEET_ID = "1xXyd9B_OmAD48tTSY3K82cv5YKUEMwBmKLFUPcTqDzQ";
var REQUIRED_START_ROW = 3;
var REJECTED_MODES = ["write", "sync", "append", "clear"];

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

function doPost(e) {
  var response = {
    ok: false,
    mode: null,
    spreadsheet_id: null,
    start_row: REQUIRED_START_ROW,
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
      response.errors.push("Mode '" + mode + "' is rejected. This Web App is validate-only.");
      return _jsonResponse(response);
    }
    if (mode !== "validate") {
      response.errors.push("Unknown mode: '" + mode + "'. Only 'validate' is supported.");
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

    // Validate sheets payload structure
    var sheetsPayload = body.sheets;
    if (!sheetsPayload || typeof sheetsPayload !== "object") {
      response.errors.push("'sheets' field is required and must be an object.");
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

    // Collect all actual sheet names for similarity checks
    var allSheets = ss.getSheets();
    var allSheetNames = allSheets.map(function(s) { return s.getName(); });

    // Check for extra sheets in spreadsheet not in payload
    var payloadSheetNames = Object.keys(sheetsPayload);
    allSheetNames.forEach(function(ssName) {
      if (payloadSheetNames.indexOf(ssName) === -1) {
        response.warnings.push(
          "Sheet '" + ssName + "' exists in spreadsheet but is not in payload. " +
          "It will not be touched."
        );
      }
    });

    // Validate each sheet in payload
    var allOk = true;
    payloadSheetNames.forEach(function(sheetName) {
      var sheetResult = _validateSheet(ss, sheetName, sheetsPayload[sheetName], allSheetNames);
      response.sheets[sheetName] = sheetResult;
      if (!sheetResult.ok) {
        allOk = false;
      }
    });

    if (response.errors.length === 0 && allOk) {
      response.ok = true;
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
  var props = PropertiesService.getScriptProperties();
  var expectedSecret = props.getProperty("SYNC_SECRET");
  if (!expectedSecret) {
    return "SYNC_SECRET is not set in Script Properties. Configure it before using this Web App.";
  }
  if (!providedSecret) {
    return "Request is missing 'secret' field.";
  }
  // Constant-time comparison to avoid timing attacks
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
    sheet_headers_count: 0,
    payload_rows_count: 0,
    row2_present: false,
    mismatches: [],
    errors: [],
    warnings: [],
    similar_sheet_names: []
  };

  var payloadHeaders = sheetPayload.headers || [];
  var payloadRows    = sheetPayload.rows    || [];
  result.payload_headers_count = payloadHeaders.length;
  result.payload_rows_count    = payloadRows.length;

  // Find sheet
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

  // Read row 1 (headers) — read enough columns to cover payload width + a few extra
  var checkWidth = payloadHeaders.length + 5;
  var lastCol    = sheet.getLastColumn();
  var readWidth  = Math.max(checkWidth, lastCol > 0 ? Math.min(lastCol, checkWidth) : checkWidth);
  readWidth      = Math.max(readWidth, payloadHeaders.length);

  var row1Values = [];
  try {
    if (lastCol >= 1) {
      var readCols = Math.min(readWidth, lastCol);
      var range    = sheet.getRange(1, 1, 1, readCols);
      row1Values   = range.getValues()[0];
    }
  } catch (e) {
    result.errors.push("Cannot read row 1: " + e.message);
    return result;
  }

  // Trim trailing empty cells
  var row1Trimmed = _trimTrailing(row1Values);
  result.sheet_headers_count = row1Trimmed.length;

  // Compare header names and order
  for (var i = 0; i < payloadHeaders.length; i++) {
    var expected = payloadHeaders[i];
    var actual   = (row1Values[i] !== undefined && row1Values[i] !== null)
                   ? String(row1Values[i])
                   : "";
    if (actual !== expected) {
      if (actual === "") {
        result.errors.push(
          "Column " + (i + 1) + ": expected '" + expected + "', but cell is empty."
        );
      } else {
        result.errors.push(
          "Column " + (i + 1) + ": expected '" + expected + "', got '" + actual + "'."
        );
      }
      result.mismatches.push({
        col: i + 1,
        expected: expected,
        actual: actual
      });
    }
  }

  // Check for extra non-empty headers beyond payload width
  for (var j = payloadHeaders.length; j < row1Values.length; j++) {
    var extra = (row1Values[j] !== null && row1Values[j] !== undefined)
                ? String(row1Values[j]).trim()
                : "";
    if (extra !== "") {
      result.errors.push(
        "Extra non-empty header at column " + (j + 1) + ": '" + extra +
        "' (beyond payload width of " + payloadHeaders.length + ")."
      );
    }
  }

  // Check row 2 presence (warning only if missing/empty)
  try {
    var lastRow = sheet.getLastRow();
    if (lastRow >= 2) {
      var row2Range  = sheet.getRange(2, 1, 1, Math.max(1, payloadHeaders.length));
      var row2Values = row2Range.getValues()[0];
      var row2HasContent = row2Values.some(function(c) {
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
// Utilities
// ---------------------------------------------------------------------------

function _trimTrailing(arr) {
  var i = arr.length - 1;
  while (i >= 0 && (arr[i] === null || arr[i] === undefined || String(arr[i]).trim() === "")) {
    i--;
  }
  return arr.slice(0, i + 1);
}

function _similarNames(target, candidates) {
  var tLower   = target.toLowerCase().trim().replace(/\s+/g, " ");
  var similar  = [];
  candidates.forEach(function(c) {
    var cLower = c.toLowerCase().trim().replace(/\s+/g, " ");
    // Match if normalized names equal, or one contains the other, or both share >60% chars
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
    for (var j = 1; j <= n; j++) {
      dp[i][j] = 0;
    }
  }
  for (var j = 0; j <= n; j++) dp[0][j] = j;
  for (var i = 1; i <= m; i++) {
    for (var j = 1; j <= n; j++) {
      if (a[i-1] === b[j-1]) {
        dp[i][j] = dp[i-1][j-1];
      } else {
        dp[i][j] = 1 + Math.min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]);
      }
    }
  }
  return dp[m][n];
}

function _jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
