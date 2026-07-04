/**
 * 근로소득 간이세액표 조회 기반 소득세 계산.
 *
 * 중요: 세액을 임의의 수식으로 "추정"하지 않는다. 반드시 "간이세액표" 시트에 사용자가
 * 붙여넣은 국세청 공식 표에서 정확히 일치하는 구간을 찾아 그 값을 그대로 사용한다.
 * 표에 해당 구간이 없으면(예: 급여가 표의 최고 구간을 초과) 에러를 던져 사람이 직접 확인하게 한다.
 */

/**
 * @param {number} taxableMonthlyPay 과세대상 월급여액 (비과세 항목 제외)
 * @param {number} familyCount 공제대상가족수(본인 포함)
 * @return {number} 소득세 (원 단위)
 */
function lookupWithholdingTax_(taxableMonthlyPay, familyCount) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TAX_TABLE);
  var data = sheet.getDataRange().getValues();

  if (data.length < 2) {
    throw new Error('"간이세액표" 시트가 비어 있습니다. 국세청 공식 표를 붙여넣으세요.');
  }

  var famCol = Math.min(Math.max(Math.round(familyCount), 1), 11) - 1 + TAX_TABLE_FAMILY_COL_OFFSET;

  for (var r = 1; r < data.length; r++) {
    var lower = data[r][0];
    var upper = data[r][1];
    if (typeof lower !== 'number' || typeof upper !== 'number') continue;

    if (taxableMonthlyPay >= lower && taxableMonthlyPay < upper) {
      var tax = data[r][famCol];
      if (typeof tax !== 'number') {
        throw new Error('간이세액표 ' + (r + 1) + '행, 가족수 ' + Math.min(familyCount, 11) +
          '명 열의 값이 숫자가 아닙니다. 시트 내용을 확인하세요.');
      }
      return tax;
    }
  }

  throw new Error('과세대상 월급여액 ' + taxableMonthlyPay + '원에 해당하는 간이세액표 구간을 찾지 못했습니다. ' +
    '"간이세액표" 시트에 해당 구간(특히 고액 구간)이 붙여넣어져 있는지 확인하세요.');
}

/**
 * 8세 이상 20세 이하 자녀 2인 이상인 경우의 추가 세액 차감.
 * 금액은 "설정" 시트의 CHILD_TAX_CREDIT_PER_EXTRA_CHILD 값을 사용한다 (기본 0 = 미적용).
 * 정확한 최신 금액은 소득세법 시행령 별표를 확인해 "설정" 시트에 직접 입력할 것.
 */
function applyChildTaxCredit_(incomeTax, childCount, config) {
  var perChild = Number(config['CHILD_TAX_CREDIT_PER_EXTRA_CHILD']) || 0;
  if (perChild <= 0 || childCount < 2) return incomeTax;
  var deduction = (childCount - 1) * perChild;
  return Math.max(0, incomeTax - deduction);
}

/** 지방소득세(소득세분) = 소득세의 10%, 원단위 미만 절사 */
function calcLocalIncomeTax_(incomeTax) {
  return Math.floor(incomeTax * 0.1);
}
