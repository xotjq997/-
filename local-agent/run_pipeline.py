"""
로컬 RPA 에이전트 진입점.

세무사랑 Pro가 설치된 Windows PC에서 실행한다. Google Drive의 "RPA_원천세"
스프레드시트에서 급여자료를 읽어온 뒤, 회사별로 세무사랑 Pro를 조작해
급여구분별(정규직/일용직/사업소득자/기타소득자) 등록 -> 자료입력 -> 마감을 수행하고,
회사 하나가 끝날 때마다 세무신고서류(원천징수이행상황신고서, 지방소득세납부서)를
작성/마감한 뒤 다음 회사로 넘어간다.

실행:
    python run_pipeline.py [config.yaml 경로]

처음 세팅할 때는 반드시 config.yaml의 dry_run: true 상태로 먼저 돌려서
로그에 찍히는 동작 순서가 기대와 맞는지 확인한 뒤 false로 바꿀 것.
"""

from __future__ import annotations

import logging
import sys

import yaml

from models import INCOME_TYPE_ORDER, group_by_company
from run_log import RunLogClient
from setax_automation import SetaxProAppConfig, SetaxProAutomation
from sheet_source import PayrollSheetSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)

    sheets_cfg = config["google_sheets"]
    source = PayrollSheetSource(
        service_account_json=sheets_cfg["service_account_json"],
        spreadsheet_id=sheets_cfg["spreadsheet_id"],
        worksheet_name=sheets_cfg.get("data_sheet_name", "시트1"),
    )
    log_client = RunLogClient(
        service_account_json=sheets_cfg["service_account_json"],
        spreadsheet_id=sheets_cfg["spreadsheet_id"],
        sheet_name=sheets_cfg.get("log_sheet_name", "처리로그"),
    )

    records = source.read_records()
    companies = group_by_company(records)

    setax_cfg = config["setax_pro"]
    dry_run = setax_cfg.get("dry_run", True)
    logger.info("회사 %d곳, 총 %d건 읽음 (dry_run=%s)", len(companies), len(records), dry_run)

    app_config = SetaxProAppConfig(
        exe_path=setax_cfg["exe_path"],
        window_title_regex=setax_cfg["window_title_regex"],
        backend=setax_cfg["backend"],
        dry_run=dry_run,
        launch_wait_seconds=setax_cfg.get("launch_wait_seconds", 5),
    )
    automation = SetaxProAutomation(app_config, setax_cfg)
    automation.connect_or_launch()

    for company in companies:
        by_type = company.by_income_type()
        try:
            automation.switch_company(company.company_name, company.biz_reg_no)
            for income_type in INCOME_TYPE_ORDER:
                type_records = by_type.get(income_type)
                if not type_records:
                    continue
                automation.process_income_type(income_type, type_records)
                log_client.log(company.company_name, company.biz_reg_no, income_type, "완료")

            automation.file_tax_reports()
            log_client.log(company.company_name, company.biz_reg_no, "세무신고서류", "완료")
        except Exception as exc:  # noqa: BLE001 - 한 회사의 실패가 다른 회사 처리를 막으면 안 됨
            logger.exception("%s 처리 중 오류", company.company_name)
            log_client.log(company.company_name, company.biz_reg_no, "처리중단", "오류", str(exc))
            continue

    logger.info("전체 처리 완료")


if __name__ == "__main__":
    main()
