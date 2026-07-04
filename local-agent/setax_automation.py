"""
세무사랑 Pro 화면 자동입력(RPA) 드라이버.

중요한 제약: 세무사랑 Pro는 한국세무사회가 배포하는 상용 프로그램으로 공개 API/공개 UI 자동화
스펙이 없다. 아래 코드의 컨트롤 식별자(자동화ID, 버튼 이름 등)는 전부 config.yaml의 placeholder를
그대로 사용한다 — 실제 값은 inspect_controls.py로 프로그램을 직접 열어 확인한 뒤 채워야 동작한다.

이 드라이버는 "파일 가져오기(Import)" 기능을 우선적으로 사용하도록 설계했다.
세무사랑 Pro가 엑셀/CSV 가져오기 기능을 지원한다면, 필드 하나하나를 타이핑하는 것보다
프로그램 자체의 가져오기 대화상자를 이용하는 편이 훨씬 안전하고 안정적이다.
(가져오기 기능이 없다면 field-by-field 입력 방식으로 별도 구현해야 하며, 그 경우
 잘못된 셀에 잘못된 값이 들어갈 위험이 커지므로 실제 신고 전 반드시 화면으로 결과를 재확인해야 한다.)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from pywinauto import Application

logger = logging.getLogger(__name__)


@dataclass
class SetaxProConfig:
    exe_path: str
    window_title_regex: str
    backend: str
    menu_path: str
    import_button_control_id: str
    file_path_input_control_id: str
    confirm_button_control_id: str
    dry_run: bool = True


class SetaxAutomationError(RuntimeError):
    pass


class SetaxProAutomation:
    def __init__(self, config: SetaxProConfig):
        self._config = config
        self._app: Application | None = None

    def connect_or_launch(self) -> None:
        cfg = self._config
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
            time.sleep(5)  # 프로그램 초기 로딩 대기. 느리면 config에 값 추가해 늘릴 것.
            self._app = Application(backend=cfg.backend).connect(
                title_re=cfg.window_title_regex, timeout=30
            )

    def import_payroll_file(self, csv_path: str) -> None:
        """메뉴로 이동 -> 가져오기 버튼 -> 파일 경로 입력 -> 확인.

        모든 control_id는 placeholder이므로, 실제 환경에 맞게 config.yaml을 채우기 전까지는
        dry_run=True 상태로만 실행해서 "어떤 순서로 동작할지" 로그로 검증하는 용도로 쓴다.
        """
        cfg = self._config
        logger.info("가져오기 시작: %s", csv_path)

        if cfg.dry_run:
            logger.info("[dry-run] 메뉴 이동: %s", cfg.menu_path)
            logger.info("[dry-run] 가져오기 버튼 클릭: %s", cfg.import_button_control_id)
            logger.info("[dry-run] 파일 경로 입력: %s -> %s", cfg.file_path_input_control_id, csv_path)
            logger.info("[dry-run] 확인 버튼 클릭: %s", cfg.confirm_button_control_id)
            logger.info("[dry-run] 실제 입력은 수행하지 않았습니다.")
            return

        if self._app is None:
            raise SetaxAutomationError("connect_or_launch()를 먼저 호출해야 합니다.")

        window = self._app.top_window()

        for step in cfg.menu_path.split("|"):
            window.menu_select(step.strip())

        window.child_window(auto_id=cfg.import_button_control_id).click_input()
        window.child_window(auto_id=cfg.file_path_input_control_id).set_edit_text(csv_path)
        window.child_window(auto_id=cfg.confirm_button_control_id).click_input()

        logger.warning(
            "화면 입력을 실행했습니다. 실제 신고서에 반영되기 전에 반드시 "
            "세무사랑 Pro 화면에서 값을 직접 재확인하세요."
        )
