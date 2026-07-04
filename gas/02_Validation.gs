/**
 * "급여입력" 시트의 데이터 검증.
 * 문제가 있는 셀은 빨간 배경 + 메모로 표시하고, 문제 없는 셀은 서식을 초기화한다.
 *
 * @param {boolean=} silent true면 알림창을 띄우지 않고 결과 객체만 반환 (runFullPipeline에서 사용)
 * @return {{errorCount: number, checkedRows: number}}
 */
function validatePayrollData(silent) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var payrollSheet = ss.getSheetByName(SHEET_NAMES.PAYROLL);
  var employeeSheet = ss.getSheetByName(SHEET_NAMES.EMPLOYEES);
  if (!payrollSheet || !employeeSheet) {
    throw new Error('필요한 시트가 없습니다. 먼저 "1) 시트 최초 설정"을 실행하세요.');
  }

  var employeeIds = {};
  var empData = employeeSheet.getDataRange().getValues();
  for (var e = 1; e < empData.length; e++) {
    var empId = String(empData[e][0]).trim();
    if (empId) employeeIds[empId] = true;
  }

  var lastRow = payrollSheet.getLastRow();
  var lastCol = PAYROLL_HEADERS.length;
  if (lastRow < 2) {
    if (!silent) SpreadsheetApp.getUi().alert('"급여입력" 시트에 입력된 데이터가 없습니다.');
    return { errorCount: 0, checkedRows: 0 };
  }

  var range = payrollSheet.getRange(2, 1, lastRow - 1, lastCol);
  var values = range.getValues();
  var errorCount = 0;

  // 서식 초기화
  range.setBackground(null);
  range.clearNote();

  var col = {
    YM: 0, EMP_ID: 1, NAME: 2, BASE_PAY: 3, BONUS: 4, MEAL: 5,
    CAR: 6, OTHER_NONTAX: 7, OTHER_TAX: 8, FAMILY_COUNT: 9, CHILD_COUNT: 10
  };

  var ymPattern = /^\d{4}-(0[1-9]|1[0-2])$/;

  for (var r = 0; r < values.length; r++) {
    var row = values[r];
    var sheetRow = r + 2;
    var rowHasContent = row.some(function (v) { return v !== '' && v !== null; });
    if (!rowHasContent) continue;

    var ym = String(row[col.YM]).trim();
    if (!ymPattern.test(ym)) {
      markError_(payrollSheet, sheetRow, col.YM + 1, '귀속연월은 "YYYY-MM" 형식이어야 합니다. 예: 2026-07');
      errorCount++;
    }

    var empId = String(row[col.EMP_ID]).trim();
    if (!empId) {
      markError_(payrollSheet, sheetRow, col.EMP_ID + 1, '사번이 비어 있습니다.');
      errorCount++;
    } else if (!employeeIds[empId]) {
      markError_(payrollSheet, sheetRow, col.EMP_ID + 1, '"직원마스터" 시트에 없는 사번입니다: ' + empId);
      errorCount++;
    }

    if (!String(row[col.NAME]).trim()) {
      markError_(payrollSheet, sheetRow, col.NAME + 1, '성명이 비어 있습니다.');
      errorCount++;
    }

    var numericCols = [col.BASE_PAY, col.BONUS, col.MEAL, col.CAR, col.OTHER_NONTAX, col.OTHER_TAX];
    numericCols.forEach(function (c) {
      var v = row[c];
      if (v === '' || v === null) return; // 선택 입력 항목은 허용
      if (typeof v !== 'number' || v < 0 || isNaN(v)) {
        markError_(payrollSheet, sheetRow, c + 1, '숫자(0 이상)만 입력 가능합니다.');
        errorCount++;
      }
    });

    var familyCount = row[col.FAMILY_COUNT];
    if (familyCount === '' || familyCount === null || typeof familyCount !== 'number' || familyCount < 1) {
      markError_(payrollSheet, sheetRow, col.FAMILY_COUNT + 1,
        '공제대상가족수(본인포함)는 1 이상의 숫자여야 합니다.');
      errorCount++;
    }
  }

  if (!silent) {
    if (errorCount === 0) {
      SpreadsheetApp.getUi().alert('검증 완료: 오류가 없습니다. (' + values.length + '행 확인)');
    } else {
      SpreadsheetApp.getUi().alert('검증 완료: 오류 ' + errorCount + '건 발견. 빨간 셀의 메모를 확인하세요.');
    }
  }

  return { errorCount: errorCount, checkedRows: values.length };
}

function markError_(sheet, row, col, message) {
  var cell = sheet.getRange(row, col);
  cell.setBackground('#f4cccc');
  cell.setNote(message);
}
