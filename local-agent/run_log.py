"""처리 결과를 RPA_원천세 스프레드시트의 "처리로그" 시트에 기록하기 위한 얇은 gspread 래퍼."""

from __future__ import annotations

import datetime as _dt

import gspread
from google.oauth2.service_account import Credentials

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_HEADERS = ["처리시각", "회사명", "사업자등록번호", "단계", "상태", "비고"]


class RunLogClient:
    def __init__(self, service_account_json: str, spreadsheet_id: str, sheet_name: str = "처리로그"):
        creds = Credentials.from_service_account_file(service_account_json, scopes=_SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(spreadsheet_id)
        try:
            self._worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            self._worksheet = spreadsheet.add_worksheet(sheet_name, rows=1000, cols=len(_HEADERS))
            self._worksheet.append_row(_HEADERS)

    def log(self, company_name: str, biz_reg_no: str, stage: str, status: str, note: str = "") -> None:
        timestamp = _dt.datetime.now().isoformat(timespec="seconds")
        self._worksheet.append_row([timestamp, company_name, biz_reg_no, stage, status, note])
