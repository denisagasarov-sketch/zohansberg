// ============================================================
// EdTech Analytics MVP — Identity Map + People Layer
// ============================================================
//
// Reads clean_events, resolves person_id for each row,
// writes identity_map (8 cols) and people (21 cols).
//
// Depends on: normalize.gs (isEmpty), clean_events.gs (_getSheet)

// ── constants ───────────────────────────────────────────────

// clean_events column indices (0-based), matches clean_events.gs output
var CE_COL = {
  EVENT_ID:      0,
  TIMESTAMP:     1,
  SOURCE_TABLE:  2,
  EVENT_TYPE:    3,
  CLIENT_ID:     4,
  TELEGRAM_ID:   5,
  TELEGRAM_NORM: 6,
  PHONE_NORM:    7,
  EMAIL_NORM:    8,
  NAME_NORM:     9,
  UTM_SOURCE:    10,
  UTM_MEDIUM:    11,
  UTM_CAMPAIGN:  12,
  UTM_CONTENT:   13,
  WEBINAR_ID:    14,
  DURATION_MIN:  15,
  STATUS:        16,
  AMOUNT:        17,
  RAW_ROW_ID:    18
};

// Priority order matters: first match wins in conflict resolution
var ID_TYPES_BY_PRIORITY = ['telegram_id', 'telegram', 'phone', 'email', 'client_id'];

var ID_STRENGTH = {
  telegram_id: 'STRONG',
  telegram:    'STRONG',
  phone:       'STRONG',
  email:       'MEDIUM',
  client_id:   'WEAK'
};

// ── public helpers ───────────────────────────────────────────

function generatePersonId(index) {
  var s = String(index);
  while (s.length < 4) s = '0' + s;
  return 'P' + s;
}

function getMatchStrength(identifierType) {
  return ID_STRENGTH[identifierType] || 'WEAK';
}

// Returns [{type, value}, ...] in priority order, skipping empty values.
// Uses isEmpty() from normalize.gs.
function getIdentifiersFromEvent(eventRow) {
  var candidates = [
    { type: 'telegram_id', value: eventRow[CE_COL.TELEGRAM_ID]   },
    { type: 'telegram',    value: eventRow[CE_COL.TELEGRAM_NORM]  },
    { type: 'phone',       value: eventRow[CE_COL.PHONE_NORM]     },
    { type: 'email',       value: eventRow[CE_COL.EMAIL_NORM]     },
    { type: 'client_id',   value: eventRow[CE_COL.CLIENT_ID]      }
  ];
  var result = [];
  candidates.forEach(function(c) {
    if (!isEmpty(c.value)) {
      result.push({ type: c.type, value: String(c.value).trim() });
    }
  });
  return result;
}

// Returns person_id of the first identifier (by priority) already in idMap.
// identifiers must be in priority order (as returned by getIdentifiersFromEvent).
function resolvePersonId(identifiers, idMap) {
  for (var i = 0; i < identifiers.length; i++) {
    var entry = idMap[identifiers[i].type + ':' + identifiers[i].value];
    if (entry) return entry.person_id;
  }
  return null;
}

// ── internal person helpers ──────────────────────────────────

function _newPerson(personId) {
  return {
    person_id:          personId,
    first_seen_at:      '',
    last_seen_at:       '',
    first_source:       '',
    first_utm_medium:   '',
    first_utm_campaign: '',
    first_utm_content:  '',
    telegram_id:        '',
    telegram_norm:      '',
    phone_norm:         '',
    email_norm:         '',
    client_ids:         {},   // value → true (dedup set)
    has_conflict:       false,
    has_webinar_form:   false,
    has_bot:            false,
    has_zoom:           false,
    has_course_form:    false,
    has_sale:           false,
    has_payment:        false,
    total_amount:       0
  };
}

function _applyEvent(person, eventRow, identifiers) {
  var ts          = eventRow[CE_COL.TIMESTAMP];
  var source      = String(eventRow[CE_COL.SOURCE_TABLE]);
  var eventType   = String(eventRow[CE_COL.EVENT_TYPE]);
  var utmMedium   = String(eventRow[CE_COL.UTM_MEDIUM]);
  var utmCampaign = String(eventRow[CE_COL.UTM_CAMPAIGN]);
  var utmContent  = String(eventRow[CE_COL.UTM_CONTENT]);
  var amount      = parseFloat(String(eventRow[CE_COL.AMOUNT])) || 0;

  // first_seen_at: keep earliest; carry first_* attribution with it
  if (!person.first_seen_at || (ts && ts < person.first_seen_at)) {
    person.first_seen_at      = ts;
    person.first_source       = source;
    person.first_utm_medium   = utmMedium;
    person.first_utm_campaign = utmCampaign;
    person.first_utm_content  = utmContent;
  }
  if (!person.last_seen_at || (ts && ts > person.last_seen_at)) {
    person.last_seen_at = ts;
  }

  // identifiers: first value wins per slot; client_ids are accumulated
  identifiers.forEach(function(id) {
    switch (id.type) {
      case 'telegram_id': if (!person.telegram_id)   person.telegram_id   = id.value; break;
      case 'telegram':    if (!person.telegram_norm)  person.telegram_norm = id.value; break;
      case 'phone':       if (!person.phone_norm)     person.phone_norm    = id.value; break;
      case 'email':       if (!person.email_norm)     person.email_norm    = id.value; break;
      case 'client_id':   person.client_ids[id.value] = true;                          break;
    }
  });

  // funnel flags
  if (eventType === 'webinar_form_submit')               person.has_webinar_form = true;
  if (eventType === 'bot_start' || eventType === 'bot_event') person.has_bot    = true;
  if (eventType === 'zoom_attended')                     person.has_zoom         = true;
  if (eventType === 'course_form_submit')                person.has_course_form  = true;
  if (source     === 'sales_raw')                        person.has_sale         = true;
  if (eventType  === 'payment')                          person.has_payment      = true;

  person.total_amount += amount;
}

// Merge loser into winner in place; used when conflict is resolved.
function _mergePersons(winner, loser) {
  // attribution: keep the earlier first_seen record
  if (loser.first_seen_at && (!winner.first_seen_at || loser.first_seen_at < winner.first_seen_at)) {
    winner.first_seen_at      = loser.first_seen_at;
    winner.first_source       = loser.first_source;
    winner.first_utm_medium   = loser.first_utm_medium;
    winner.first_utm_campaign = loser.first_utm_campaign;
    winner.first_utm_content  = loser.first_utm_content;
  }
  if (loser.last_seen_at && loser.last_seen_at > winner.last_seen_at) {
    winner.last_seen_at = loser.last_seen_at;
  }
  // identifiers: fill empty slots from loser
  if (!winner.telegram_id   && loser.telegram_id)   winner.telegram_id   = loser.telegram_id;
  if (!winner.telegram_norm && loser.telegram_norm)  winner.telegram_norm = loser.telegram_norm;
  if (!winner.phone_norm    && loser.phone_norm)     winner.phone_norm    = loser.phone_norm;
  if (!winner.email_norm    && loser.email_norm)     winner.email_norm    = loser.email_norm;
  Object.keys(loser.client_ids).forEach(function(k) { winner.client_ids[k] = true; });
  // flags: OR
  winner.has_conflict    = winner.has_conflict    || loser.has_conflict;
  winner.has_webinar_form= winner.has_webinar_form|| loser.has_webinar_form;
  winner.has_bot         = winner.has_bot         || loser.has_bot;
  winner.has_zoom        = winner.has_zoom        || loser.has_zoom;
  winner.has_course_form = winner.has_course_form || loser.has_course_form;
  winner.has_sale        = winner.has_sale        || loser.has_sale;
  winner.has_payment     = winner.has_payment     || loser.has_payment;
  winner.total_amount   += loser.total_amount;
}

function _computeMatchQuality(person) {
  if (person.has_conflict)                                          return 'CHECK';
  if (person.telegram_id || person.telegram_norm || person.phone_norm) return 'STRONG';
  if (person.email_norm)                                            return 'MEDIUM';
  return 'WEAK';
}

// ── main ────────────────────────────────────────────────────

function buildIdentityAndPeople() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  // Read clean_events
  var cleanSheet = _getSheet(ss, 'clean_events');
  var lastRow = cleanSheet.getLastRow();
  if (lastRow < 2) {
    Logger.log('buildIdentityAndPeople: clean_events is empty, nothing to process');
    return;
  }
  var events = cleanSheet.getRange(2, 1, lastRow - 1, 19).getValues();

  // In-memory state
  // idMap:     "type:value" → { person_id, match_strength, first_seen_at, last_seen_at,
  //                             source_tables:{}, conflict_flag }
  // personMap: person_id → person object
  var idMap       = {};
  var personMap   = {};
  var personCount = 0;

  events.forEach(function(row) {
    var identifiers = getIdentifiersFromEvent(row);
    if (identifiers.length === 0) return; // row has no usable identifiers

    var ts     = row[CE_COL.TIMESTAMP];
    var source = String(row[CE_COL.SOURCE_TABLE]);

    // Collect all person_ids already linked to any identifier in this event
    var matchedSet = {};
    identifiers.forEach(function(id) {
      var entry = idMap[id.type + ':' + id.value];
      if (entry) matchedSet[entry.person_id] = true;
    });
    var matchedList = Object.keys(matchedSet);
    var isConflict  = matchedList.length > 1;

    var personId;

    if (matchedList.length === 0) {
      // No match → new person
      personCount++;
      personId = generatePersonId(personCount);
      personMap[personId] = _newPerson(personId);

    } else if (matchedList.length === 1) {
      personId = matchedList[0];

    } else {
      // Conflict: pick winner by highest-priority identifier already in idMap
      personId = resolvePersonId(identifiers, idMap);
      if (!personId) personId = matchedList[0]; // fallback (shouldn't happen)

      // Merge all losing persons into winner
      matchedList.forEach(function(pid) {
        if (pid === personId) return;
        if (!personMap[pid]) return;

        _mergePersons(personMap[personId], personMap[pid]);

        // Remap every idMap entry that pointed at the loser
        Object.keys(idMap).forEach(function(key) {
          if (idMap[key].person_id === pid) {
            idMap[key].person_id    = personId;
            idMap[key].conflict_flag = true;
          }
        });

        delete personMap[pid];
      });
    }

    // Apply this event to the person record
    _applyEvent(personMap[personId], row, identifiers);
    if (isConflict) personMap[personId].has_conflict = true;

    // Update idMap entries for all identifiers in this event
    identifiers.forEach(function(id) {
      var key = id.type + ':' + id.value;
      if (!idMap[key]) {
        idMap[key] = {
          person_id:     personId,
          match_strength:getMatchStrength(id.type),
          first_seen_at: ts,
          last_seen_at:  ts,
          source_tables: {},
          conflict_flag: false
        };
      } else {
        idMap[key].last_seen_at = ts;
      }
      idMap[key].source_tables[source] = true;
      if (isConflict) idMap[key].conflict_flag = true;
    });
  });

  // ── write identity_map (8 columns) ──────────────────────────
  var imSheet  = _getSheet(ss, 'identity_map');
  var imLast   = imSheet.getLastRow();
  if (imLast > 1) imSheet.getRange(2, 1, imLast - 1, 8).clearContent();

  var imRows = Object.keys(idMap).map(function(key) {
    var colonIdx = key.indexOf(':');
    var idType   = key.slice(0, colonIdx);
    var idValue  = key.slice(colonIdx + 1);
    var rec      = idMap[key];
    return [
      idType,
      idValue,
      rec.person_id,
      rec.match_strength,
      rec.first_seen_at,
      rec.last_seen_at,
      Object.keys(rec.source_tables).join(', '),
      rec.conflict_flag ? 'TRUE' : 'FALSE'
    ];
  });

  if (imRows.length > 0) {
    imSheet.getRange(2, 1, imRows.length, 8).setValues(imRows);
  }

  // ── write people (21 columns) ────────────────────────────────
  var pSheet = _getSheet(ss, 'people');
  var pLast  = pSheet.getLastRow();
  if (pLast > 1) pSheet.getRange(2, 1, pLast - 1, 21).clearContent();

  var pRows = Object.keys(personMap).map(function(pid) {
    var p = personMap[pid];
    return [
      p.person_id,
      p.first_seen_at,
      p.last_seen_at,
      p.first_source,
      p.first_utm_medium,
      p.first_utm_campaign,
      p.first_utm_content,
      p.telegram_id,
      p.telegram_norm,
      p.phone_norm,
      p.email_norm,
      Object.keys(p.client_ids).join(', '),
      _computeMatchQuality(p),
      p.has_webinar_form  ? 'TRUE' : 'FALSE',
      p.has_bot           ? 'TRUE' : 'FALSE',
      p.has_zoom          ? 'TRUE' : 'FALSE',
      p.has_course_form   ? 'TRUE' : 'FALSE',
      p.has_sale          ? 'TRUE' : 'FALSE',
      p.has_payment       ? 'TRUE' : 'FALSE',
      p.total_amount > 0 ? p.total_amount : '',
      ''  // notes — manual field, never overwritten
    ];
  });

  if (pRows.length > 0) {
    pSheet.getRange(2, 1, pRows.length, 21).setValues(pRows);
  }

  Logger.log(
    'buildIdentityAndPeople: ' + pRows.length + ' persons, ' +
    imRows.length + ' identifiers'
  );
}
