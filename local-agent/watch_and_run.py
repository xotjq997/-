"""
로컬 RPA 에이전트 진입점.

세무사랑 Pro가 설치된 Windows PC에서 실행한다 (GAS/구글시트가 아니라 여기서 실행).
Google Drive for Desktop으로 동기화되는 로컬 폴더를 감시하다가, GAS가 생성한
연동파일(csv)이 새로 나타나면 세무사랑 Pro 화면에 자동 입력하고, 결과를
Google Sheets의 "연동로그" 시트에 다시 기록한다.

실행:
    python watch_and_run.py [config.yaml 경로]

처음 세팅할 때는 반드시 config.yaml의 dry_run: true 상태로 먼저 돌려서
로그에 찍히는 동작 순서가 기대와 맞는지 확인한 뒤 false로 바꿀 것.
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from pathlib import Path

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from setax_automation import SetaxProAutomation, SetaxProConfig
from sheets_log import SyncLogClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class ExportFileHandler(FileSystemEventHandler):
    def __init__(self, config: dict):
        self._config = config
        self._settle_seconds = int(config.get("settle_seconds", 5))
        self._automation = SetaxProAutomation(
            SetaxProConfig(dry_run=config.get("dry_run", True), **config["setax_pro"])
        )
        sheets_cfg = config["google_sheets"]
        self._log_client = SyncLogClient(
            service_account_json=sheets_cfg["service_account_json"],
            spreadsheet_id=sheets_cfg["spreadsheet_id"],
            sheet_name=sheets_cfg.get("sync_log_sheet_name", "연동로그"),
        )

    def on_created(self, event):
        if event.is_directory or not event.src_path.lower().endswith(".csv"):
            return
        # Drive 동기화가 파일을 다 내려받을 때까지 잠시 대기
        time.sleep(self._settle_seconds)
        self._process_file(Path(event.src_path))

    def _process_file(self, file_path: Path) -> None:
        logger.info("새 연동파일 감지: %s", file_path)
        pending_rows = self._log_client.find_pending_rows()
        matching_row = next(
            (r for r in pending_rows if r.get("파일명") == file_path.name), None
        )
        if matching_row is None:
            logger.warning(
                "%s 에 해당하는 '대기' 상태 로그 행을 찾지 못했습니다. "
                "그래도 자동입력은 시도하되, 상태 기록은 건너뜁니다.",
                file_path.name,
            )

        try:
            self._automation.connect_or_launch()
            self._automation.import_payroll_file(str(file_path))
        except Exception as exc:  # noqa: BLE001 - 실패 원인을 로그/시트에 그대로 남겨야 함
            logger.exception("자동입력 실패: %s", file_path)
            self._move_file(file_path, self._config.get("failed_folder"))
            if matching_row is not None:
                self._log_client.update_status(matching_row["_row"], "오류", str(exc))
            return

        self._move_file(file_path, self._config.get("processed_folder"))
        if matching_row is not None:
            self._log_client.update_status(matching_row["_row"], "완료", "로컬 RPA 처리 완료")
        logger.info("처리 완료: %s", file_path)

    def _move_file(self, file_path: Path, dest_folder: str | None) -> None:
        if not dest_folder:
            return
        dest_dir = Path(dest_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(dest_dir / file_path.name))


def main() -> None:
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = load_config(config_path)

    watch_folder = config["watch_folder"]
    logger.info("감시 시작: %s (dry_run=%s)", watch_folder, config.get("dry_run", True))

    handler = ExportFileHandler(config)
    observer = Observer()
    observer.schedule(handler, watch_folder, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
