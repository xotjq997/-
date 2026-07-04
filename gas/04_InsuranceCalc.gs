/**
 * 4대보험 근로자부담분 계산.
 * 요율은 코드에 하드코딩하지 않고 "보험료율설정" 시트 값을 읽어서 사용한다 (매년 변경되므로).
 */

function getInsuranceRates_() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.INSURANCE_RATES);
  var data = sheet.getDataRange().getValues();
  var rates = {};
  for (var i = 1; i < data.length; i++) {
    var name = data[i][0];
    if (!name) continue;
    rates[name] = {
      employeeRate: Number(data[i][1]) || 0,
      employerRate: Number(data[i][2]) || 0
    };
  }
  return rates;
}

/**
 * @param {number} insurancePay 보험료 산정 기준이 되는 과세대상급여(비과세 제외)
 * @param {object} rates getInsuranceRates_() 결과
 * @param {object} config getConfig_() 결과 (국민연금 기준소득월액 상하한 적용용)
 * @return {{pension:number, health:number, longTermCare:number, employment:number}}
 */
function calculateInsurance_(insurancePay, rates, config) {
  var npsBase = insurancePay;
  var min = Number(config['NPS_MONTHLY_BASE_MIN']);
  var max = Number(config['NPS_MONTHLY_BASE_MAX']);
  if (min > 0 && npsBase < min) npsBase = min;
  if (max > 0 && npsBase > max) npsBase = max;

  var pensionRate = rates['국민연금'] ? rates['국민연금'].employeeRate : 0;
  var healthRate = rates['건강보험'] ? rates['건강보험'].employeeRate : 0;
  var ltcRate = rates['장기요양보험'] ? rates['장기요양보험'].employeeRate : 0; // 건강보험료 대비 %
  var employmentRate = rates['고용보험(실업급여)'] ? rates['고용보험(실업급여)'].employeeRate : 0;

  var pension = Math.floor(npsBase * pensionRate / 100);
  var health = Math.floor(insurancePay * healthRate / 100);
  var longTermCare = Math.floor(health * ltcRate / 100);
  var employment = Math.floor(insurancePay * employmentRate / 100);

  return { pension: pension, health: health, longTermCare: longTermCare, employment: employment };
}
