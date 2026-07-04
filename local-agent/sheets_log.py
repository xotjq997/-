"""'연동로그' 시트에 처리 상태를 기록하기 위한 얇은 gspread 래퍼."""

from __future__ import annotations

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 01_Setup.gs의 SYNC_LOG_HEADERS와 순서를 맞춘다.
_COL_TIMESTAMP = 1
_COL_YM = 2
_COL_FILENAME = 3
_COL_DRIVE_FILE_ID = 4
_COL_STATUS = 5
_COL_NOTE = 6


class SyncLogClient:
    def __init__(self, service_account_json: str, spreadsheet_id: str, sheet_name: str):
        creds = Credentials.from_service_account_file(service_account_json, scopes=_SCOPES)
        client = gspread.authorize(creds)
        self._worksheet = client.open_by_key(spreadsheet_id).worksheet(sheet_name)

    def find_pending_rows(self) -> list[dict]:
        """상태가 "대기"인 행을 (1-indexed row number 포함) 반환한다."""
        records = self._worksheet.get_all_records()
        pending = []
        for idx, record in enumerate(records, start=2):  # 헤더가 1행이므로 데이터는 2행부터
            if str(record.get("상태", "")).strip() == "대기":
                record["_row"] = idx
                pending.append(record)
        return pending

    def update_status(self, row: int, status: str, note: str = "") -> None:
        self._worksheet.update_cell(row, _COL_STATUS, status)
        if note:
            self._worksheet.update_cell(row, _COL_NOTE, note)
