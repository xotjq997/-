"""
세무사랑 Pro의 실제 화면 컨트롤 식별자를 확인하기 위한 도우미 스크립트.

이 저장소는 세무사랑 Pro의 내부 UI 구조를 알지 못한다 (공개된 사양이 없음).
config.yaml에 있는 control_id 값들은 전부 placeholder이므로, 실제 자동화를 만들려면
이 스크립트로 프로그램을 열어둔 상태에서 컨트롤 트리를 덤프해 진짜 이름/ID를 알아내야 한다.

사용법:
  1. 세무사랑 Pro를 수동으로 실행하고, 자동화하려는 화면(예: 원천세 신고서 작성)까지 이동해 둔다.
  2. 이 스크립트를 실행한다:  python inspect_controls.py
  3. 콘솔에 출력되는 컨트롤 트리에서 버튼/입력창의 automation_id, title, control_type을 확인한다.
  4. 확인한 값을 config.yaml의 *_control_id 항목에 반영한다.

backend는 "uia"(최신 표준)와 "win32"(구형 프로그램) 두 가지를 모두 시도해보는 것이 좋다.
"""

import sys

from pywinauto import Application


def dump_window(title_re: str, backend: str) -> None:
    print(f"\n=== backend={backend}, title_re={title_re!r} 로 연결 시도 ===")
    try:
        app = Application(backend=backend).connect(title_re=title_re, timeout=5)
    except Exception as exc:  # noqa: BLE001 - 진단용 스크립트이므로 광범위하게 잡아 사용자에게 보여줌
        print(f"  연결 실패: {exc}")
        return

    window = app.top_window()
    print(f"  연결 성공: {window.window_text()!r}")
    print("  --- 컨트롤 트리 (자식 요소의 automation_id / title / control_type) ---")
    window.print_control_identifiers(depth=6)


def main() -> None:
    title_re = sys.argv[1] if len(sys.argv) > 1 else ".*세무사랑.*"
    for backend in ("uia", "win32"):
        dump_window(title_re, backend)


if __name__ == "__main__":
    main()
