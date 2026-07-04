"""
세무사랑 Pro 화면 자동입력(RPA) 드라이버.

중요한 제약: 세무사랑 Pro는 한국세무사회가 배포하는 상용 프로그램으로 공개 API/공개 UI 자동화
스펙이 없다. 아래 코드가 사용하는 메뉴 경로/컨트롤 식별자는 전부 config.yaml의 placeholder이며,
실제 값은 inspect_controls.py로 프로그램을 직접 열어 확인한 뒤 채워야 동작한다.

회사 1곳을 처리하는 순서:
    회사 변경
    -> 그 회사에 존재하는 급여구분(정규직/일용직/사업소득자/기타소득자)마다
       해당 탭으로 이동 -> 등록 화면에 사원(소득자) 정보 입력 -> 급여자료 입력 화면에
       금액 등을 입력 -> 마감
    -> 세무신고서류 탭 -> 원천징수이행상황신고서 작성 -> 지방소득세납부서(명세서) 중
       현재회사 지방소득세 계산서/납부서 작성 -> 마감
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from pywinauto import Application

from models import PayrollRecord

logger = logging.getLogger(__name__)


@dataclass
class SetaxProAppConfig:
    exe_path: str
    window_title_regex: str
    backend: str
    dry_run: bool = True
    launch_wait_seconds: int = 5


class SetaxAutomationError(RuntimeError):
    pass


class SetaxProAutomation:
    def __init__(self, app_config: SetaxProAppConfig, screens_config: dict):
        self._app_cfg = app_config
        self._cfg = screens_config
        self._app: Application | None = None

    # ------------------------------------------------------------------
    # 연결/실행
    # ------------------------------------------------------------------
    def connect_or_launch(self) -> None:
        cfg = self._app_cfg
        try:
            self._app = Application(backend=cfg.backend).connect(
                title_re=cfg.window_title_regex, timeout=5
            )
            logger.info("세무사랑 Pro에 이미 실행 중인 창을 연결했습니다.")
        except Exception:
            logger.info("실행 중인 창을 찾지 못해 새로 실행합니다: %s", cfg.exe_path)
            if cfg.dry_run:
                logger.info("[dry-run] 실제로는 실행하지 않음")
                return
            self._app = Application(backend=cfg.backend).start(cfg.exe_path)
            time.sleep(cfg.launch_wait_seconds)
            self._app = Application(backend=cfg.backend).connect(
                title_re=cfg.window_title_regex, timeout=30
            )

    # ------------------------------------------------------------------
    # 회사 변경 (자료에 등장하는 회사를 순서대로 처리하기 위함)
    # ------------------------------------------------------------------
    def switch_company(self, company_name: str, biz_reg_no: str) -> None:
        cfg = self._require_section("company_switch")
        logger.info("회사 변경: %s (%s)", company_name, biz_reg_no)
        self._navigate(cfg["menu_path"])
        self._set_text(cfg["search_input_control_id"], biz_reg_no)
        self._click(cfg["confirm_button_control_id"])

    # ------------------------------------------------------------------
    # 급여구분별 등록 -> 자료입력 -> 마감
    # ------------------------------------------------------------------
    def process_income_type(self, income_type: str, records: list[PayrollRecord]) -> None:
        income_types_cfg = self._require_section("income_types")
        cfg = income_types_cfg.get(income_type)
        if cfg is None:
            raise SetaxAutomationError(
                f"config.yaml의 setax_pro.income_types에 '{income_type}' 화면 설정이 없습니다."
            )

        logger.info("[%s] %d건 처리 시작", income_type, len(records))
        self._navigate(cfg["tab_menu_path"])

        register_cfg = cfg["register"]
        self._navigate(register_cfg["menu_path"])
        for record in records:
            self._fill_record(register_cfg["field_control_ids"], record)
            self._click(register_cfg["save_button_control_id"])

        payroll_cfg = cfg["payroll"]
        self._navigate(payroll_cfg["menu_path"])
        for record in records:
            self._fill_record(payroll_cfg["field_control_ids"], record)
            self._click(payroll_cfg["save_button_control_id"])

        self._click(payroll_cfg["close_button_control_id"])  # 마감
        logger.info("[%s] 마감 완료", income_type)

    # ------------------------------------------------------------------
    # 세무신고서류: 원천징수이행상황신고서 + 지방소득세납부서(명세서) -> 마감
    # ------------------------------------------------------------------
    def file_tax_reports(self) -> None:
        cfg = self._require_section("tax_filing")
        self._navigate(cfg["tab_menu_path"])

        withholding_cfg = cfg["withholding_report"]
        self._navigate(withholding_cfg["menu_path"])
        self._click(withholding_cfg["create_button_control_id"])

        local_tax_cfg = cfg["local_income_tax"]
        self._navigate(local_tax_cfg["menu_path"])
        if local_tax_cfg.get("current_company_filter_control_id"):
            self._click(local_tax_cfg["current_company_filter_control_id"])  # "현재회사" 필터
        self._click(local_tax_cfg["calculation_button_control_id"])  # 지방소득세 계산서
        self._click(local_tax_cfg["payment_button_control_id"])  # 납부서

        self._click(cfg["close_button_control_id"])  # 마감
        logger.warning(
            "원천징수이행상황신고서/지방소득세납부서 작성 및 마감을 실행했습니다. "
            "실제 신고 접수 전에 반드시 세무사랑 Pro 화면에서 값을 직접 재확인하세요."
        )

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------
    def _require_section(self, key: str) -> dict:
        cfg = self._cfg.get(key)
        if cfg is None:
            raise SetaxAutomationError(f"config.yaml의 setax_pro.{key} 설정이 없습니다.")
        return cfg

    def _fill_record(self, field_control_ids: dict, record: PayrollRecord) -> None:
        for column, control_id in field_control_ids.items():
            self._set_text(control_id, record.field(column))

    def _navigate(self, menu_path: str) -> None:
        if self._app_cfg.dry_run:
            logger.info("[dry-run] 메뉴 이동: %s", menu_path)
            return
        window = self._app.top_window()
        for step in menu_path.split("|"):
            window.menu_select(step.strip())

    def _set_text(self, control_id: str, value: str) -> None:
        if self._app_cfg.dry_run:
            logger.info("[dry-run] 입력: %s -> %r", control_id, value)
            return
        window = self._app.top_window()
        window.child_window(auto_id=control_id).set_edit_text(value)

    def _click(self, control_id: str) -> None:
        if self._app_cfg.dry_run:
            logger.info("[dry-run] 클릭: %s", control_id)
            return
        window = self._app.top_window()
        window.child_window(auto_id=control_id).click_input()
