/**
 * Google Apps Script webhook receiver for internship tracker rows.
 */
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var payload = JSON.parse(e.postData.contents || '{}');
  var rows = payload.rows || [];

  var headers = [
    'company', 'title', 'location', 'deadline', 'description',
    'url', 'source', 'posted_at', 'score', 'matched_keywords', 'reasons',
    'first_seen_utc', 'last_seen_utc', 'status'
  ];

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
  }

  var values = sheet.getDataRange().getValues();
  var urlIdx = headers.indexOf('url');
  var rowMap = {};
  for (var i = 1; i < values.length; i++) {
    rowMap[values[i][urlIdx]] = i + 1;
  }

  rows.forEach(function(row) {
    var rowValues = headers.map(function(h) { return row[h] || ''; });
    var existingRow = rowMap[row.url];
    if (existingRow) {
      sheet.getRange(existingRow, 1, 1, headers.length).setValues([rowValues]);
    } else {
      sheet.appendRow(rowValues);
    }
  });

  return ContentService
    .createTextOutput(JSON.stringify({ ok: true, updated: rows.length }))
    .setMimeType(ContentService.MimeType.JSON);
}
