/**
 * 원천세/4대보험 계산을 실행하여 "계산결과" 시트를 채운다.
 * "계산결과" 시트는 스크립트 전용 출력 시트이므로 매 실행마다 전체를 다시 씀.
 */
function calculateAll() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var config = getConfig_();
  var rates = getInsuranceRates_();

  var payrollSheet = ss.getSheetByName(SHEET_NAMES.PAYROLL);
  var lastRow = payrollSheet.getLastRow();
  if (lastRow < 2) throw new Error('"급여입력" 시트에 데이터가 없습니다.');

  var payrollValues = payrollSheet.getRange(2, 1, lastRow - 1, PAYROLL_HEADERS.length).getValues();
  var targetYm = String(config['TARGET_YM'] || '').trim();

  var results = [];
  var now = new Date();

  payrollValues.forEach(function (row) {
    var ym = String(row[0]).trim();
    if (!ym) return; // 빈 행
    if (targetYm && ym !== targetYm) return;

    var empId = String(row[1]).trim();
    var name = row[2];
    var basePay = Number(row[3]) || 0;
    var bonus = Number(row[4]) || 0;
    var mealAllowance = Number(row[5]) || 0;
    var carAllowance = Number(row[6]) || 0;
    var otherNonTax = Number(row[7]) || 0;
    var otherTax = Number(row[8]) || 0;
    var familyCount = Number(row[9]) || 1;
    var childCount = Number(row[10]) || 0;

    var taxablePay = basePay + bonus + otherTax; // 비과세 항목 제외
    var totalPay = taxablePay + mealAllowance + carAllowance + otherNonTax;

    var incomeTax = lookupWithholdingTax_(taxablePay, familyCount);
    incomeTax = applyChildTaxCredit_(incomeTax, childCount, config);
    var localTax = calcLocalIncomeTax_(incomeTax);
    var ins = calculateInsurance_(taxablePay, rates, config);

    var deductionTotal = incomeTax + localTax + ins.pension + ins.health + ins.longTermCare + ins.employment;
    var netPay = totalPay - deductionTotal;

    results.push([
      ym, empId, name, taxablePay, incomeTax, localTax,
      ins.pension, ins.health, ins.longTermCare, ins.employment,
      deductionTotal, netPay, now
    ]);
  });

  var resultSheet = ss.getSheetByName(SHEET_NAMES.RESULTS);
  var existingLastRow = resultSheet.getLastRow();
  if (existingLastRow > 1) {
    resultSheet.getRange(2, 1, existingLastRow - 1, RESULT_HEADERS.length).clearContent();
  }
  if (results.length > 0) {
    resultSheet.getRange(2, 1, results.length, RESULT_HEADERS.length).setValues(results);
  }

  SpreadsheetApp.getUi().alert('계산 완료: ' + results.length + '건 (' + (targetYm || '전체 월') + ')');
  return results.length;
}

/**
 * "계산결과"를 세무사랑 Pro로 가져오기 위한 CSV 파일로 만들어 Drive에 저장하고,
 * "연동로그"에 상태 "대기"로 기록한다. 로컬 PC에서 도는 RPA 에이전트가 이 로그를 보고
 * 파일을 집어가서 실제 화면 입력을 수행한다 (local-agent/ 참고).
 *
 * 주의: 아래 CSV 헤더는 범용 초안이다. 세무사랑 Pro 프로그램 자체에서 제공하는
 * "엑셀 양식 다운로드" 기능으로 실제 가져오기 템플릿을 받아 헤더/컬럼 순서를
 * 반드시 비교하고 필요시 EXPORT_HEADERS를 수정하라.
 */
var EXPORT_HEADERS = [
  '귀속연월', '사번', '성명', '과세대상급여', '소득세', '지방소득세',
  '국민연금', '건강보험', '장기요양보험', '고용보험', '공제총액', '차인지급액'
];

function buildExportFile() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var config = getConfig_();
  var folderId = String(config['EXPORT_FOLDER_ID'] || '').trim();
  if (!folderId) {
    throw new Error('"설정" 시트의 EXPORT_FOLDER_ID를 먼저 채우세요. ' +
      '세무사랑 Pro가 설치된 PC에서 Google Drive for Desktop으로 동기화되는 폴더의 ID여야 합니다.');
  }

  var resultSheet = ss.getSheetByName(SHEET_NAMES.RESULTS);
  var lastRow = resultSheet.getLastRow();
  if (lastRow < 2) {
    throw new Error('"계산결과" 시트가 비어 있습니다. 먼저 "3) 원천세/4대보험 계산"을 실행하세요.');
  }

  var values = resultSheet.getRange(2, 1, lastRow - 1, RESULT_HEADERS.length).getValues();

  var csvRows = [EXPORT_HEADERS.join(',')];
  values.forEach(function (row) {
    if (!row[0]) return;
    var mapped = [row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11]];
    csvRows.push(mapped.map(csvEscape_).join(','));
  });
  var csvContent = csvRows.join('\r\n');

  var targetYm = String(config['TARGET_YM'] || '전체').trim();
  var prefix = String(config['EXPORT_FILE_PREFIX'] || '원천세_입력').trim();
  var timestamp = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyyMMdd_HHmmss');
  var fileName = prefix + '_' + targetYm + '_' + timestamp + '.csv';

  var folder = DriveApp.getFolderById(folderId);
  // CSV를 세무사랑/엑셀에서 한글이 깨지지 않게 BOM을 붙여 UTF-8로 저장
  var blob = Utilities.newBlob('﻿' + csvContent, 'text/csv', fileName);
  var file = folder.createFile(blob);

  var logSheet = ss.getSheetByName(SHEET_NAMES.SYNC_LOG);
  logSheet.appendRow([new Date(), targetYm, fileName, file.getId(), '대기', '로컬 RPA 에이전트 처리 대기 중']);

  SpreadsheetApp.getUi().alert(
    '연동파일 생성 완료: ' + fileName + '\n\n' +
    '이 파일은 Drive 폴더(' + folderId + ')에 저장되었습니다.\n' +
    '세무사랑 Pro가 설치된 PC의 로컬 RPA 에이전트가 이 파일을 감지하여 자동 입력을 진행합니다.\n' +
    '"연동로그" 시트에서 처리 상태를 확인하세요.'
  );

  return file.getId();
}

function csvEscape_(value) {
  var s = String(value === null || value === undefined ? '' : value);
  if (s.indexOf(',') !== -1 || s.indexOf('"') !== -1 || s.indexOf('\n') !== -1) {
    s = '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}
