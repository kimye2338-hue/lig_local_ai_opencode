# -*- coding: utf-8 -*-
"""OpenCodeLIG 오프라인 설치 로직 — setup.bat 이 파이썬만 찾아서 이 파일에 위임한다.

배치(.bat)에는 로직을 두지 않는다: 줄바꿈/코드페이지/%~dp0 재해석 등 cmd 함정으로
세 번 연속 설치가 깨졌다. 이 파일은 리눅스 CI에서도 --home 오버라이드로 전 단계가
실제 실행-검증된다. stdlib only, 네트워크 없음(pip --no-index).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]      # 번들 루트 (release/ 의 부모)


def _say(step: str, msg: str) -> None:
    print(f"[{step}] {msg}", flush=True)


def install_wheels(prefetch: Path) -> bool:
    if not prefetch.is_dir() or not any(prefetch.glob("*.whl")):
        _say("2/6", "번들에 라이브러리가 없어 건너뜁니다 (핵심 기능은 동작).")
        return True
    _say("2/6", "부속 라이브러리 설치 중 (인터넷 사용 안 함) ...")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index",
                        "--find-links", str(prefetch),
                        "pywin32", "openpyxl", "python-pptx"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("[주의] 일부 라이브러리 설치 실패 — 핵심 기능은 그대로 동작합니다.")
        print((r.stdout + r.stderr)[-400:])
        return False
    _say("2/6", "라이브러리 설치 완료.")
    return True


def copy_workspace(home: Path) -> Path:
    src = BUNDLE / "workspace-template"
    if not src.is_dir():
        raise SystemExit(f"[중단] 번들 구조를 찾지 못했습니다: {src}\n"
                         "       zip을 통째로 푼 폴더의 설치.bat 으로 실행했는지 확인하세요.")
    target = home / "OpenCodeLIG" / "workspace"
    _say("3/6", f"프로그램 설치 중: {target} ...")
    shutil.copytree(src, target, dirs_exist_ok=True)
    return target


def make_userdata(home: Path) -> Path:
    ud = home / "OpenCodeLIG_USERDATA"
    for sub in ("diagnostics", "audit", "secrets"):
        (ud / sub).mkdir(parents=True, exist_ok=True)
    _say("4/6", f"데이터 폴더 준비: {ud}")
    return ud


def gateway_env(ud: Path, interactive: bool) -> None:
    envfile = ud / "secrets" / "lig-api.env"
    if envfile.exists():
        _say("5/6", "게이트웨이 설정: 기존 설정 발견 — 그대로 사용합니다.")
        return
    url = key = ""
    if interactive:
        _say("5/6", "게이트웨이(사내 LLM) 설정 — 모르면 그냥 Enter 두 번 (나중에 설정 가능).")
        try:
            url = input("  게이트웨이 주소 붙여넣기 (예: http://호스트): ").strip()
            key = input("  API 키 붙여넣기: ").strip()
        except EOFError:
            url = key = ""
    lines = ["# LIG 사내 게이트웨이 설정 - 이 파일은 절대 커밋/반출 금지",
             f"LIG_GATEWAY_BASE_URL={url or 'REPLACE_WITH_GATEWAY_URL'}",
             f"LIG_API_KEY={key or 'REPLACE_WITH_KEY'}", ""]
    envfile.write_text("\n".join(lines), encoding="utf-8")
    if url:
        print(f"       저장됨: {envfile}")
    else:
        print(f"       건너뜀 — 나중에 {envfile} 을 열어 두 값을 채우면 됩니다.")


def run_doctor(workspace: Path, ud: Path) -> bool:
    _say("6/6", "자가 진단 중 ...")
    out = ud / "diagnostics" / "setup_doctor.txt"
    r = subprocess.run([sys.executable, str(workspace / "agent_ops" / "agentops.py"), "doctor"],
                       cwd=str(workspace), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        print(f"[주의] 진단에서 경고 — {out} 참고.")
        return False
    print("       정상.")
    return True


def desktop_launcher(home: Path) -> None:
    desktop = home / "Desktop"
    if not desktop.is_dir():
        print("       바탕화면 폴더를 찾지 못해 바로가기는 건너뜁니다.")
        print(f"       직접 실행: {home / 'OpenCodeLIG' / 'workspace' / 'launch' / 'menu.bat'}")
        return
    # 내용은 반드시 ASCII만 (더블클릭 시 cp949로 파싱됨). 한글은 파일 '이름'에만.
    content = ('@echo off\r\n'
               'call "%USERPROFILE%\\OpenCodeLIG\\workspace\\launch\\menu.bat"\r\n')
    (desktop / "AI비서.bat").write_bytes(content.encode("ascii"))
    print("       바탕화면에 [AI비서] 바로가기를 만들었습니다.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="", help="설치 홈 (기본 %USERPROFILE% — 테스트용 오버라이드)")
    ap.add_argument("--no-input", action="store_true", help="게이트웨이 프롬프트 생략 (테스트/자동화)")
    a = ap.parse_args(argv)
    home = Path(a.home) if a.home else Path(os.environ.get("USERPROFILE", str(Path.home())))

    ok = True
    ok &= install_wheels(BUNDLE / "release" / "prefetch")
    workspace = copy_workspace(home)
    ud = make_userdata(home)
    gateway_env(ud, interactive=not a.no_input)
    ok &= run_doctor(workspace, ud)
    desktop_launcher(home)

    print()
    print(" ==============================================")
    if ok:
        print("   설치 완료. 바탕화면의 [AI비서] 를 실행하세요.")
    else:
        print("   설치 완료 (일부 경고 있음 - 위 메시지 참고).")
        print("   바탕화면의 [AI비서] 를 실행하세요.")
    print(" ==============================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
