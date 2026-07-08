# -*- coding: utf-8 -*-
"""Windows .bat 함정 린트 — 실제 설치를 3번 깨뜨린 함정 4종을 영구 차단한다.

Run: py -3.11 tests\\test_launch_bats.py   (리눅스에서도 동작 — 바이트 검사)

함정과 규칙:
  1) LF 줄바꿈  -> cmd가 if 블록을 오파싱: 전 .bat는 CRLF 강제.
  2) py -3.11 하드코딩 -> py 런처 없는 PC에서 사망: _py.bat 리졸버만 사용.
  3) %~dp0 재해석 -> 상대 call 후 cd 하면 현재 폴더로 풀림: %~dp0는
     `set "HERE=%~dp0"` 한 줄에서만 캡처하고 이후엔 %HERE%만.
  4) cp949 파싱 -> 더블클릭된 bat 내용은 기본 코드페이지로 읽힘: call/cd/start
     줄(경로 참조)은 ASCII만. 한글은 chcp 65001 이후의 echo/rem/title에만.
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
REPO = WS.parent
BATS = sorted(WS.glob("launch/*.bat"))
release_setup = REPO / "release" / "setup.bat"
if release_setup.exists():
    BATS.append(release_setup)
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    check("bat files found", len(BATS) >= 12, str(len(BATS)))
    for p in BATS:
        raw = p.read_bytes()
        name = p.name

        # 1) CRLF 강제
        check(f"{name}: CRLF only",
              raw.count(b"\n") == raw.count(b"\r\n") > 0, "LF line endings")

        text = raw.decode("utf-8")
        lines = text.splitlines()

        # 2) 하드코딩 금지 (_py.bat 자신만 예외)
        if name != "_py.bat":
            check(f"{name}: no hardcoded 'py -3.11' invocation",
                  not any(ln.strip().startswith("py -3.11 ") and "--version" not in ln
                          for ln in lines), "hardcoded launcher")

        # 3) %~dp0는 HERE 캡처 한 줄에서만
        dp0_lines = [ln for ln in lines if "%~dp0" in ln]
        allowed = [ln for ln in dp0_lines
                   if 'set "HERE=%~dp0"' in ln or 'for %%I in ("%~dp0..")' in ln
                   or ln.strip().lower().startswith("rem ")]
        check(f"{name}: %~dp0 only captured once into HERE",
              dp0_lines == allowed, str([l.strip() for l in dp0_lines if l not in allowed]))
        # HERE 캡처는 어떤 cd 보다 먼저
        if any('set "HERE=' in ln for ln in lines):
            cap_idx = next(i for i, ln in enumerate(lines) if 'set "HERE=' in ln)
            cd_idx = next((i for i, ln in enumerate(lines) if ln.strip().lower().startswith("cd ")), None)
            check(f"{name}: HERE captured before any cd",
                  cd_idx is None or cap_idx < cd_idx, f"cap={cap_idx} cd={cd_idx}")

        # 4) 경로 참조 줄은 ASCII만
        for i, ln in enumerate(lines, 1):
            s = ln.strip().lower()
            if s.startswith(("call ", "cd ", "start ", "xcopy ", "copy ")):
                check(f"{name}:{i} path-referencing line is ASCII",
                      all(ord(c) < 128 for c in ln), ln.strip()[:60])
        # 한글이 있으면 chcp 65001이 그보다 먼저
        # rem 주석 속 한글은 표시/실행되지 않으므로 위치 무관 — echo/title 등만 검사
        first_kr = next((i for i, ln in enumerate(lines)
                         if any(ord(c) > 127 for c in ln)
                         and not ln.strip().lower().startswith("rem ")), None)
        if first_kr is not None:
            chcp = next((i for i, ln in enumerate(lines) if "chcp 65001" in ln), None)
            check(f"{name}: chcp 65001 precedes Korean text",
                  chcp is not None and chcp < first_kr, f"chcp={chcp} kr={first_kr}")

    # Launcher paths stay ASCII-only above. Korean knowledge/docs filenames are
    # product content now, so the old whole-workspace non-ASCII ban no longer
    # applies to the package tree.

    print(f"\nALL {PASS} CHECKS PASSED (launch bats lint)")


if __name__ == "__main__":
    main()
