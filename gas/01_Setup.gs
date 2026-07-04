/**
 * 급여 -> 원천세 자동화 파이프라인 공통 설정
 *
 * 시트 구성:
 *  - 설정            : key/value 형태의 환경설정
 *  - 직원마스터       : 직원 기본정보
 *  - 급여입력         : 월별 급여 원본 입력 (사용자가 직접 입력하는 시트)
 *  - 간이세액표       : 국세청 근로소득 간이세액표 원본을 그대로 붙여넣는 참조 시트
 *  - 보험료율설정     : 4대보험 요율 (매년 변경되므로 코드에 하드코딩하지 않음)
 *  - 계산결과         : 원천징수세액/4대보험 계산 결과 (스크립트가 기록, 수기 입력 금지)
 *  - 연동로그         : 세무사랑 Pro 연동용 내보내기 파일과 로컬 RPA 처리 상태
 */

var SHEET_NAMES = {
  CONFIG: '설정',
  EMPLOYEES: '직원마스터',
  PAYROLL: '급여입력',
  TAX_TABLE: '간이세액표',
  INSURANCE_RATES: '보험료율설정',
  RESULTS: '계산결과',
  SYNC_LOG: '연동로그'
};

var PAYROLL_HEADERS = [
  '귀속연월', '사번', '성명', '기본급', '상여', '식대(비과세)',
  '자가운전보조금(비과세)', '기타비과세', '기타과세수당', '공제대상가족수(본인포함)',
  '20세이하자녀수', '비고'
];

var EMPLOYEE_HEADERS = [
  '사번', '성명', '주민등록번호(뒷자리마스킹 권장)', '입사일', '퇴사일',
  '거주자구분(거주자/비거주자)', '근무형태(상용/일용)', '부서', '비고'
];

// 국세청 "근로소득 간이세액표" 공식 배포 파일과 동일한 형태(이상/미만 + 공제대상가족수 1~11 열).
// 홈택스에서 받은 엑셀의 데이터 구간을 그대로 이 헤더 순서에 맞춰 붙여넣으면 된다.
var TAX_TABLE_HEADERS = ['이상', '미만', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11'];
var TAX_TABLE_FAMILY_COL_OFFSET = 2; // '이상','미만' 다음부터 가족수 1명 열 시작 (0-indexed)

var INSURANCE_RATE_HEADERS = ['항목', '근로자부담률(%)', '사업주부담률(%)', '비고'];

var RESULT_HEADERS = [
  '귀속연월', '사번', '성명', '과세대상급여', '소득세(간이세액표)', '지방소득세(10%)',
  '국민연금(근로자)', '건강보험(근로자)', '장기요양보험(근로자)', '고용보험(근로자)',
  '공제총액', '차인지급액', '계산시각'
];

var SYNC_LOG_HEADERS = ['타임스탬프', '귀속연월', '파일명', 'Drive파일ID', '상태', '메모'];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('원천세 자동화')
    .addItem('1) 시트 최초 설정', 'setupSheets')
    .addSeparator()
    .addItem('2) 급여자료 검증', 'validatePayrollData')
    .addItem('3) 원천세/4대보험 계산', 'calculateAll')
    .addItem('4) 세무사랑 연동파일 생성', 'buildExportFile')
    .addSeparator()
    .addItem('전체 실행 (검증→계산→내보내기)', 'runFullPipeline')
    .addToUi();
}

/**
 * 최초 1회 실행: 필요한 시트와 헤더, 안내문구를 생성한다.
 * 이미 존재하는 시트는 건드리지 않는다.
 */
function setupSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  ensureSheetWithHeaders_(ss, SHEET_NAMES.PAYROLL, PAYROLL_HEADERS);
  ensureSheetWithHeaders_(ss, SHEET_NAMES.EMPLOYEES, EMPLOYEE_HEADERS);
  ensureSheetWithHeaders_(ss, SHEET_NAMES.TAX_TABLE, TAX_TABLE_HEADERS);
  ensureSheetWithHeaders_(ss, SHEET_NAMES.INSURANCE_RATES, INSURANCE_RATE_HEADERS);
  ensureSheetWithHeaders_(ss, SHEET_NAMES.RESULTS, RESULT_HEADERS);
  ensureSheetWithHeaders_(ss, SHEET_NAMES.SYNC_LOG, SYNC_LOG_HEADERS);

  setupConfigSheet_(ss);
  setupInsuranceDefaults_(ss);
  setupTaxTablePlaceholder_(ss);

  SpreadsheetApp.getUi().alert(
    '시트 설정 완료.\n\n' +
    '이어서 해야 할 일:\n' +
    '1) "간이세액표" 시트에 국세청 근로소득 간이세액표(엑셀)를 그대로 붙여넣으세요.\n' +
    '   (홈택스 > 조회/발급 > 근로소득 간이세액표에서 다운로드)\n' +
    '2) "보험료율설정" 시트의 요율이 최신인지 반드시 확인/수정하세요. (매년 변경됨)\n' +
    '3) "설정" 시트에서 EXPORT_FOLDER_ID 등 값을 채우세요.'
  );
}

function ensureSheetWithHeaders_(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
    sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  }
  return sheet;
}

function setupConfigSheet_(ss) {
  var sheet = ss.getSheetByName(SHEET_NAMES.CONFIG);
  if (sheet.getLastRow() > 0) return;

  var rows = [
    ['키', '값', '설명'],
    ['COMPANY_NAME', '', '회사명 (내보내기 파일 헤더에 사용)'],
    ['BIZ_REG_NO', '', '사업자등록번호'],
    ['EXPORT_FOLDER_ID', '', '세무사랑 Pro 연동용 파일을 저장할 Google Drive 폴더 ID. ' +
      '이 폴더는 세무사랑 Pro가 설치된 PC에서 "Google Drive for Desktop"으로 동기화되어 있어야 ' +
      '로컬 RPA 에이전트가 파일을 감지할 수 있습니다.'],
    ['EXPORT_FILE_PREFIX', '원천세_입력', '내보내기 파일명 접두어'],
    ['TARGET_YM', '', '이번에 계산/내보내기할 귀속연월 (예: 2026-07). 비우면 급여입력 시트의 모든 월을 처리'],
    ['CHILD_TAX_CREDIT_PER_EXTRA_CHILD', 0,
      '8세~20세 자녀 2인 이상 시 간이세액표 산출세액에서 추가로 차감하는 금액(원/1인당). ' +
      '소득세법 시행령 별표 상 최신 금액을 확인 후 직접 입력하세요. 기본값 0은 "적용 안 함"을 의미합니다.'],
    ['NPS_MONTHLY_BASE_MIN', 0,
      '국민연금 기준소득월액 하한액(원). 국민연금공단이 매년 7월 고시. 0이면 상하한 미적용.'],
    ['NPS_MONTHLY_BASE_MAX', 0,
      '국민연금 기준소득월액 상한액(원). 국민연금공단이 매년 7월 고시. 0이면 상하한 미적용.'],
  ];
  sheet.getRange(1, 1, rows.length, 3).setValues(rows);
  sheet.getRange(1, 1, 1, 3).setFontWeight('bold');
  sheet.setFrozenRows(1);
  sheet.setColumnWidth(3, 500);
}

function setupInsuranceDefaults_(ss) {
  var sheet = ss.getSheetByName(SHEET_NAMES.INSURANCE_RATES);
  if (sheet.getLastRow() > 1) return; // 이미 값이 있으면 덮어쓰지 않음

  // 참고용 기본값. 실제 신고 전 반드시 최신 고시 요율로 확인/수정할 것.
  var rows = [
    ['국민연금', 4.75, 4.75, '기준소득월액 상하한 적용 필요. 매년 변경되므로 국민연금공단 고시 확인'],
    ['건강보험', 3.595, 3.595, '국민건강보험공단 고시 요율 확인 필요'],
    ['장기요양보험', 13.14, 13.14, '건강보험료 대비 비율(%). 건강보험공단 고시 확인 필요'],
    ['고용보험(실업급여)', 0.9, 0.9, '사업주는 업종별 고용안정/직업능력개발 부담분 별도 추가'],
  ];
  sheet.getRange(2, 1, rows.length, 4).setValues(rows);
  sheet.getRange(2, 2, rows.length, 2).setNumberFormat('0.000');
}

function setupTaxTablePlaceholder_(ss) {
  var sheet = ss.getSheetByName(SHEET_NAMES.TAX_TABLE);
  if (sheet.getLastRow() > 1) return;

  var note = '국세청 홈택스(www.hometax.go.kr) > 조회/발급 > 기타조회 > 근로소득 간이세액표에서 ' +
    '엑셀을 받아, "이상/미만/가족수 1~11" 데이터 구간만 이 시트의 2행부터 붙여넣으세요. ' +
    '수식으로 세액을 추정하지 말고 반드시 국세청 공식 표를 그대로 사용해야 합니다.';
  sheet.getRange(2, 1).setValue('이 시트는 비워두면 계산이 불가능합니다 ↓');
  sheet.getRange(2, 1).setNote(note);
}

/** '설정' 시트의 key/value를 object로 읽어온다. */
function getConfig_() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.CONFIG);
  if (!sheet) throw new Error('"설정" 시트가 없습니다. 먼저 "1) 시트 최초 설정"을 실행하세요.');

  var data = sheet.getDataRange().getValues();
  var config = {};
  for (var i = 1; i < data.length; i++) {
    var key = data[i][0];
    if (!key) continue;
    config[key] = data[i][1];
  }
  return config;
}

function runFullPipeline() {
  var ui = SpreadsheetApp.getUi();
  var report = validatePayrollData(true);
  if (report.errorCount > 0) {
    ui.alert('검증 오류 ' + report.errorCount + '건이 있어 계산/내보내기를 중단했습니다.\n' +
      '"급여입력" 시트의 빨간색 셀과 메모를 확인하세요.');
    return;
  }
  calculateAll();
  buildExportFile();
}
