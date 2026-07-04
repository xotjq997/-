"""RPA_원천세 시트의 급여 데이터 레코드와 회사/급여구분별 그룹핑."""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIRED_COLUMNS = ["회사명", "사업자등록번호", "이름", "급여구분", "금액"]

INCOME_TYPE_ORDER = [
    "1_정규직근로자",
    "2_일용직근로자",
    "3_사업소득자",
    "4_기타소득자",
]


class PayrollDataError(ValueError):
    pass


@dataclass
class PayrollRecord:
    row_number: int  # 시트 상 행 번호 (오류 메시지용)
    raw: dict

    def __post_init__(self) -> None:
        missing = [c for c in REQUIRED_COLUMNS if not str(self.raw.get(c, "")).strip()]
        if missing:
            raise PayrollDataError(f"{self.row_number}행: 필수 컬럼이 비어 있습니다 ({', '.join(missing)})")
        if self.income_type not in INCOME_TYPE_ORDER:
            raise PayrollDataError(
                f"{self.row_number}행: 급여구분 '{self.income_type}'은(는) 알 수 없는 값입니다. "
                f"허용값: {', '.join(INCOME_TYPE_ORDER)}"
            )

    @property
    def company_name(self) -> str:
        return str(self.raw["회사명"]).strip()

    @property
    def biz_reg_no(self) -> str:
        return str(self.raw["사업자등록번호"]).strip()

    @property
    def name(self) -> str:
        return str(self.raw["이름"]).strip()

    @property
    def income_type(self) -> str:
        return str(self.raw["급여구분"]).strip()

    @property
    def amount(self) -> str:
        return str(self.raw["금액"]).strip()

    def field(self, column: str) -> str:
        """등록/자료입력 화면에 채울 값을 컬럼명으로 조회한다.

        필수 컬럼(회사명/사업자등록번호/이름/급여구분/금액)뿐 아니라, 시트에 추가로
        넣어둔 임의 컬럼(예: 주민등록번호, 입사일 등)도 config.yaml에서 컬럼명만
        참조하면 그대로 조회된다.
        """
        return str(self.raw.get(column, "")).strip()


@dataclass
class CompanyGroup:
    company_name: str
    biz_reg_no: str
    records: list = field(default_factory=list)

    def by_income_type(self) -> dict:
        grouped: dict = {}
        for record in self.records:
            grouped.setdefault(record.income_type, []).append(record)
        return grouped


def group_by_company(records: list) -> list:
    """자료를 회사(회사명+사업자등록번호) 등장 순서대로 묶는다."""
    groups: dict = {}
    order: list = []
    for record in records:
        key = (record.company_name, record.biz_reg_no)
        if key not in groups:
            groups[key] = CompanyGroup(record.company_name, record.biz_reg_no, [])
            order.append(key)
        groups[key].records.append(record)
    result = [groups[key] for key in order]
    for company in result:
        assign_auto_employee_numbers(company.records)
    return result


def assign_auto_employee_numbers(records: list) -> None:
    """"RPA_원천세" 시트에 사번 컬럼이 없거나 비어 있는 행에 회사 내 순번(1,2,3...)을 채운다."""
    next_number = 1
    for record in records:
        if not record.field("사번"):
            record.raw["사번"] = str(next_number)
        next_number += 1
