"""
세무사랑 Pro의 실제 화면 컨트롤 식별자를 확인하기 위한 도우미 스크립트.

이 저장소는 세무사랑 Pro의 내부 UI 구조를 알지 못한다 (공개된 사양이 없음).
config.yaml에 있는 control_id 값들은 전부 placeholder이므로, 실제 자동화를 만들려면
이 스크립트로 프로그램을 열어둔 상태에서 컨트롤 트리를 덤프해 진짜 이름/ID를 알아내야 한다.

사용법:
  1. 세무사랑 Pro를 수동으로 실행하고, 자동화하려는 화면(예: 사원등록)까지 이동해 둔다.
  2. 이 스크립트를 실행한다:  python inspect_controls.py
  3. 콘솔에 출력되는 컨트롤 트리에서 버튼/입력창의 automation_id, title, control_type을 확인한다.
  4. 확인한 값을 config.yaml의 *_control_id 항목에 반영한다.

backend는 "uia"(최신 표준)와 "win32"(구형 프로그램) 두 가지를 모두 시도해보는 것이 좋다.

세무사랑 Pro처럼 MDI(하나의 메인 프레임 창 안에 여러 자식 창) 구조인 프로그램은 메인 프레임과
그 안의 화면(자식 창)이 제목에 같은 문자열을 공유해서, title_re만으로는 창이 여러 개 잡혀
모호(ambiguous)해지는 경우가 흔하다. 이 스크립트는 그런 경우 후보 목록을 번호와 함께 보여주고,
두 번째 인자로 몇 번째 창인지(found_index)를 지정해 다시 실행하도록 안내한다.
"""

import sys

from pywinauto import Application
from pywinauto.findwindows import ElementAmbiguousError, find_elements


def _print_candidates(title_re: str, backend: str) -> None:
    elements = find_elements(title_re=title_re, backend=backend)
    print(f"  후보 {len(elements)}개가 잡혔습니다 (메인 프레임과 그 안의 자식 창이 같은 제목을 "
          "공유하는 MDI 구조일 가능성이 높습니다):")
    for idx, el in enumerate(elements):
        print(f"    [{idx}] title={el.name!r} class_name={el.class_name!r} handle={el.handle}")
    print(f"  원하는 화면의 번호를 확인한 뒤 아래처럼 found_index를 지정해 다시 실행하세요:")
    print(f"    python inspect_controls.py \"{title_re}\" <번호>")


def dump_window(title_re: str, backend: str, found_index: int | None) -> None:
    print(f"\n=== backend={backend}, title_re={title_re!r}"
          f"{f', found_index={found_index}' if found_index is not None else ''} 로 연결 시도 ===")
    try:
        connect_kwargs = {"title_re": title_re, "timeout": 5}
        if found_index is not None:
            connect_kwargs["found_index"] = found_index
        app = Application(backend=backend).connect(**connect_kwargs)
    except ElementAmbiguousError:
        _print_candidates(title_re, backend)
        return
    except Exception as exc:  # noqa: BLE001 - 진단용 스크립트이므로 광범위하게 잡아 사용자에게 보여줌
        print(f"  연결 실패: {exc}")
        return

    window = app.top_window()
    print(f"  연결 성공: {window.window_text()!r}")
    print("  --- 컨트롤 트리 (자식 요소의 automation_id / title / control_type) ---")
    window.print_control_identifiers(depth=6)


def main() -> None:
    title_re = sys.argv[1] if len(sys.argv) > 1 else ".*세무사랑.*"
    found_index = int(sys.argv[2]) if len(sys.argv) > 2 else None
    for backend in ("uia", "win32"):
        dump_window(title_re, backend, found_index)


if __name__ == "__main__":
    main()
