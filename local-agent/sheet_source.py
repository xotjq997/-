"""구글 드라이브의 "RPA_원천세" 스프레드시트에서 급여 데이터를 읽어온다."""

from __future__ import annotations

import gspread
from google.oauth2.service_account import Credentials

from models import PayrollDataError, PayrollRecord

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


class PayrollSheetSource:
    def __init__(self, service_account_json: str, spreadsheet_id: str, worksheet_name: str):
        creds = Credentials.from_service_account_file(service_account_json, scopes=_SCOPES)
        client = gspread.authorize(creds)
        self._worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)

    def read_records(self) -> list:
        rows = self._worksheet.get_all_records()
        records = []
        errors = []
        for idx, row in enumerate(rows, start=2):  # 1행은 헤더이므로 데이터는 2행부터
            if not any(str(v).strip() for v in row.values()):
                continue  # 빈 행은 건너뜀
            try:
                records.append(PayrollRecord(row_number=idx, raw=row))
            except PayrollDataError as exc:
                errors.append(str(exc))
        if errors:
            raise PayrollDataError("RPA_원천세 시트에 오류가 있습니다:\n" + "\n".join(errors))
        return records
