"""
세무사랑 Pro 화면 자동입력(RPA) 드라이버.

중요한 제약: 세무사랑 Pro는 한국세무사회가 배포하는 상용 프로그램으로 공개 API/공개 UI 자동화
스펙이 없다. 아래 코드가 사용하는 메뉴 경로/컨트롤 식별자는 전부 config.yaml의 placeholder이며,
실제 값은 inspect_controls.py로 프로그램을 직접 열어 확인한 뒤 채워야 동작한다.

사원등록/급여자료입력 등 자료입력 화면은 개별 입력창이 아니라 fpUSpread80이라는 스프레드시트형
그리드 컨트롤 하나로 되어 있어(컨트롤 트리에 셀 단위 자동화ID가 없음), 필드마다 컨트롤ID를 지정하는
방식이 통하지 않는다. 대신 사람이 입력하듯 "값 타이핑 -> 확정키(Enter/Tab) -> 다음 칸" 방식의
키보드 기반 입력(그리드 입력, grid_entry)으로 처리한다.

회사 1곳을 처리하는 순서:
    회사 변경
    -> 그 회사에 존재하는 급여구분(정규직/일용직/사업소득자/기타소득자)마다
       해당 탭으로 이동 -> 등록 화면에 사원(소득자) 정보 입력(그리드) -> 급여자료 입력 화면에
       금액 등을 입력(그리드) -> 마감
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

_COMMIT_KEYS = {"enter": "{ENTER}", "tab": "{TAB}"}


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
        self._enter_grid_rows(register_cfg["grid_entry"], records)
        if register_cfg.get("save_button_control_id"):
            self._click(register_cfg["save_button_control_id"])

        payroll_cfg = cfg["payroll"]
        self._navigate(payroll_cfg["menu_path"])
        self._enter_grid_rows(payroll_cfg["grid_entry"], records)
        if payroll_cfg.get("save_button_control_id"):
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
    # 그리드(fpUSpread80) 입력: 등록/급여자료입력 화면 공용
    # ------------------------------------------------------------------
    def _enter_grid_rows(self, grid_cfg: dict, records: list[PayrollRecord]) -> None:
        """화면당 한 번만 그리드에 포커스를 준 뒤, 행마다 필드를 타이핑 -> 확정키로 커밋한다.

        마지막 필드의 확정키(보통 tab)를 누르면 그리드가 자동으로 다음 빈 행의 첫 칸으로
        이동하는 것이 확인됐으므로(사원등록 기준), 새 행마다 다시 클릭할 필요는 없다.
        단, 화면을 처음 열었을 때 첫 빈 행에 포커스를 주려면 마우스 클릭이 필요하다는 것도
        확인됐다 - 그 클릭 위치가 화면/회사마다 달라질 수 있어 config의
        grid_control_class_name + initial_focus_keys로 조정 가능하게 열어둔다.
        """
        self._focus_grid_first_row(grid_cfg)
        for record in records:
            for field_cfg in grid_cfg["fields"]:
                value = record.field(field_cfg["column"]) or field_cfg.get("default", "")
                commit_key = field_cfg["commit_key"]
                self._type_and_commit(value, commit_key)

    def _focus_grid_first_row(self, grid_cfg: dict) -> None:
        class_name = grid_cfg.get("grid_control_class_name", "fpUSpread80")
        initial_focus_keys = grid_cfg.get("initial_focus_keys", "")
        if self._app_cfg.dry_run:
            logger.info(
                "[dry-run] 그리드(%s) 클릭 후 첫 빈 행으로 이동: 키입력 %r",
                class_name,
                initial_focus_keys,
            )
            return
        window = self._app.top_window()
        grid = window.child_window(class_name=class_name)
        grid.click_input()
        if initial_focus_keys:
            grid.type_keys(initial_focus_keys)

    def _type_and_commit(self, value: str, commit_key: str) -> None:
        if commit_key not in _COMMIT_KEYS:
            raise SetaxAutomationError(f"알 수 없는 commit_key입니다: {commit_key!r} (enter/tab만 지원)")
        if self._app_cfg.dry_run:
            logger.info("[dry-run] 입력: %r -> %s", value, commit_key)
            return
        window = self._app.top_window()
        window.type_keys(value, with_spaces=True)
        window.type_keys(_COMMIT_KEYS[commit_key])

    # ------------------------------------------------------------------
    # 내부 헬퍼 (일반 컨트롤: 회사변경 검색창, 세무신고서류 버튼 등)
    # ------------------------------------------------------------------
    def _require_section(self, key: str) -> dict:
        cfg = self._cfg.get(key)
        if cfg is None:
            raise SetaxAutomationError(f"config.yaml의 setax_pro.{key} 설정이 없습니다.")
        return cfg

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
