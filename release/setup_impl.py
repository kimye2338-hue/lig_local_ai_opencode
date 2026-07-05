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
    env = dict(os.environ, USERPROFILE=str(workspace.parents[1]), HOME=str(workspace.parents[1]))
    r = subprocess.run([sys.executable, str(workspace / "agent_ops" / "agentops.py"), "doctor"],
                       cwd=str(workspace), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    out.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    if r.returncode != 0:
        print(f"[주의] 진단에서 경고 — {out} 참고.")
        return False
    print("       정상.")
    return True


def install_global_brain(home: Path, workspace: Path) -> None:
    """OpenCode 전역 설정(~/.config/opencode)에 페르소나/명령을 설치한다.

    이렇게 하면 사용자가 '아무 폴더'에서 opencode를 켜도 같은 업무 비서
    페르소나가 뜨고, agent_ops 런타임을 절대경로로 호출한다(폴더 무관).
    기억/일정/감사는 USERDATA 전역이므로 폴더가 달라도 이어진다.
    """
    src = workspace / ".opencode"
    if not src.is_dir():
        return
    # 두 곳 모두: 표준(~/.config/opencode)과 하드닝 런처의 XDG 재지정 대상.
    destinations = [home / ".config" / "opencode",
                    home / "OpenCodeLIG" / "userdata" / "config" / "opencode"]
    abs_runtime = (workspace / "agent_ops" / "agentops.py").as_posix()
    for dst in destinations:
        for sub in ("agents", "commands", "plugins"):
            s = src / sub
            if not s.is_dir():
                continue
            d = dst / sub
            d.mkdir(parents=True, exist_ok=True)
            for f in s.rglob("*"):
                if not f.is_file():
                    continue
                rel = f.relative_to(s)
                out = d / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                if f.suffix in (".md", ".ts", ".json"):
                    text = f.read_text(encoding="utf-8")
                    # 전역 사본은 어느 폴더에서든 동작해야 하므로 런타임 경로를 절대화.
                    text = text.replace("agent_ops/agentops.py", abs_runtime)
                    text = text.replace("agent_ops/menu.py",
                                        (workspace / "agent_ops" / "menu.py").as_posix())
                    out.write_text(text, encoding="utf-8")
                else:
                    shutil.copy2(f, out)
    print("       OpenCode 전역 페르소나 설치 (아무 폴더에서나 동일 비서)")




# ---------------- OpenCode TUI (선택 동봉: release/vendor/opencode/) ----------

OC_JSON = """{
  "$schema": "https://opencode.ai/config.json",
  "autoupdate": false,
  "share": "disabled",
  "provider": {
    "lig-gateway": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "LIG Gateway (EXAONE)",
      "options": {
        "baseURL": "{env:LIG_GATEWAY_BASE_URL}/gateway/EXAONE-4.5-33B-vibe_coding_think_off/v1",
        "apiKey": "{env:LIG_API_KEY}"
      },
      "models": { "EXAONE-4.5-33B": { "name": "EXAONE 4.5 33B (in-house)" } }
    }
  }
}
"""

# oc.bat: '현재 폴더'에서 OpenCode를 여는 런처 (PATH에 등록됨 -> 아무 폴더에서 `oc`).
# 내용은 ASCII만(cp949 파싱 안전). lig-api.env 를 프로세스 env로 로드해 {env:} 치환을 살린다.
OC_BAT = (
    "@echo off\r\n"
    "set \"OCODE_EXE=%USERPROFILE%\\OpenCodeLIG\\bin\\opencode.exe\"\r\n"
    "set \"OPENCODE_USERDATA=%USERPROFILE%\\OpenCodeLIG\\userdata\"\r\n"
    "set \"XDG_CONFIG_HOME=%OPENCODE_USERDATA%\\config\"\r\n"
    "set \"XDG_DATA_HOME=%OPENCODE_USERDATA%\\data\"\r\n"
    "set \"XDG_CACHE_HOME=%OPENCODE_USERDATA%\\cache\"\r\n"
    "set \"OPENCODE_DISABLE_DEFAULT_PLUGINS=1\"\r\n"
    "set \"OPENCODE_PURE=1\"\r\n"
    "set \"NO_UPDATE_NOTIFIER=1\"\r\n"
    "if not exist \"%OPENCODE_USERDATA%\" mkdir \"%OPENCODE_USERDATA%\"\r\n"
    "set \"LIGENV=%USERPROFILE%\\OpenCodeLIG_USERDATA\\secrets\\lig-api.env\"\r\n"
    "if exist \"%LIGENV%\" for /f \"usebackq eol=# tokens=1,* delims==\" %%A in (\"%LIGENV%\") do set \"%%A=%%B\"\r\n"
    "\"%OCODE_EXE%\" %*\r\n"
)

RUN_BAT = (
    "@echo off\r\n"
    "cd /d \"%USERPROFILE%\\OpenCodeLIG\\workspace\"\r\n"
    "call \"%USERPROFILE%\\OpenCodeLIG\\bin\\oc.bat\" %*\r\n"
)

# ocd.bat: '현재 폴더'를 프로젝트로 여는 런처 — .opencodelig 로컬 프로필을
# 시드하고 전역 기억을 공유한 채 OpenCode를 그 폴더에서 실행한다.
# 로직은 전부 agent_ops/ocd.py (파이썬)에 있다. 내용은 ASCII만.
OCD_BAT = (
    "@echo off\r\n"
    "set \"LIG_WS=%USERPROFILE%\\OpenCodeLIG\\workspace\"\r\n"
    "call \"%LIG_WS%\\launch\\_py.bat\"\r\n"
    "if errorlevel 1 exit /b 9\r\n"
    "%PY% \"%LIG_WS%\\agent_ops\\ocd.py\" %*\r\n"
)

# ai.bat: 아무 폴더에서 `ai` 로 일일 메뉴를 연다.
AI_BAT = (
    "@echo off\r\n"
    "call \"%USERPROFILE%\\OpenCodeLIG\\workspace\\launch\\menu.bat\"\r\n"
)

VERIFY_BAT = (
    "@echo off\r\n"
    "\"%USERPROFILE%\\OpenCodeLIG\\bin\\opencode.exe\" --version\r\n"
    "if errorlevel 1 exit /b 1\r\n"
    "echo [OK] patched opencode.exe exists and runs.\r\n"
)


def _write_ascii_bat(path: Path, content: str) -> None:
    data = content.encode("ascii")           # 비ASCII 섞이면 여기서 즉시 실패(가드)
    assert data.count(b"\n") == data.count(b"\r\n") > 0
    path.write_bytes(data)


def _add_user_path(bin_dir: Path) -> None:
    """HKCU\Environment PATH 에 bin 추가 (Windows 전용; 실패해도 설치는 계속)."""
    if os.name != "nt":
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as k:
            try:
                cur, typ = winreg.QueryValueEx(k, "Path")
            except OSError:
                cur, typ = "", winreg.REG_EXPAND_SZ
            if str(bin_dir).lower() in cur.lower():
                return
            new = (cur.rstrip(";") + ";" if cur else "") + str(bin_dir)
            winreg.SetValueEx(k, "Path", 0, typ, new)
        print("       PATH에 등록: 새 명령창부터 아무 폴더에서 `oc` 로 실행 가능.")
    except Exception as exc:  # noqa: BLE001 - 설치는 계속
        print(f"       (PATH 등록 생략: {type(exc).__name__} — oc.bat 전체 경로로 실행하세요)")


def install_bin_launchers(home: Path) -> Path:
    """bin 런처(ocd/ai) 설치 + PATH 등록 — OpenCode 동봉 여부와 무관하게 항상.

    ocd 는 폴더-로컬 프로필 기능의 진입점이라 agent_ops-only 설치에서도
    (프로필 시드/진단까지는) 동작해야 한다. 기존 파일은 덮어써 갱신하지만
    사용자 데이터(OpenCodeLIG_USERDATA)는 절대 건드리지 않는다.
    """
    bin_dir = home / "OpenCodeLIG" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_ascii_bat(bin_dir / "ocd.bat", OCD_BAT)
    _write_ascii_bat(bin_dir / "ai.bat", AI_BAT)
    _add_user_path(bin_dir)
    print("       명령 설치: 새 명령창에서 아무 폴더든 `ocd`(그 폴더에서 비서) / `ai`(메뉴)")
    return bin_dir


def install_opencode(home: Path, workspace: Path) -> None:
    vend = BUNDLE / "release" / "vendor" / "opencode" / "opencode.exe"
    if not vend.exists():
        _say("7/8", "OpenCode 동봉 없음 — agent_ops만 설치합니다 (나중에 추가 가능).")
        return
    _say("7/8", "OpenCode 설치 중 ...")
    # exe 무결성: 동봉 .sha256 과 대조
    sha_file = vend.with_suffix(".exe.sha256")
    if sha_file.exists():
        import hashlib
        actual = hashlib.sha256(vend.read_bytes()).hexdigest()
        expected = sha_file.read_text().split()[0].strip().lower()
        if actual != expected:
            print("[중단] opencode.exe 해시 불일치 — 번들 손상. 재복사/재전송 필요.")
            raise SystemExit(4)
    bin_dir = home / "OpenCodeLIG" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vend, bin_dir / "opencode.exe")
    # 전역 opencode.json (게이트웨이 provider) — 표준/XDG 두 위치
    for cfg_dir in (home / ".config" / "opencode",
                    home / "OpenCodeLIG" / "userdata" / "config" / "opencode"):
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "opencode.json").write_text(OC_JSON, encoding="utf-8")
    # 워크스페이스 로컬 안전판 (CI 설치기와 동일)
    (workspace / "opencode.json").write_text('{\n  "autoupdate": false\n}\n', encoding="utf-8")
    # 런처 3종 (ASCII+CRLF 가드)
    _write_ascii_bat(bin_dir / "oc.bat", OC_BAT)
    _write_ascii_bat(workspace / "RUN_OPENCODE_LIG.bat", RUN_BAT)
    _write_ascii_bat(workspace / "VERIFY_OFFLINE_INSTALL.bat", VERIFY_BAT)
    _add_user_path(bin_dir)
    print(f"       완료: {bin_dir / 'opencode.exe'}")


WIKI_SEED = """# 업무 위키 (전역 기억 — 폴더가 달라도 공유)

비서가 배운 규칙/선호/교훈이 여기에 쌓인다. 사람이 직접 편집해도 된다.
등록: 오픈코드 채팅에서 "기억해: ..." / CLI: agentops.py remember "..."
조회: agentops.py recall <키워드>   정리: agentops.py memorycheck

## 사용자 선호
- (예) 보고서 마감 기한 표기는 항상 'D-일' 형식으로.

## 반복 실수 금지
- (예) 원본 파일 직접 수정 금지 — 항상 사본에서.

## 프로젝트 노트
"""


def seed_wiki(home: Path, workspace: Path) -> None:
    wiki = home / "OpenCodeLIG_USERDATA" / "memory" / "WIKI.md"
    if not wiki.exists():
        wiki.parent.mkdir(parents=True, exist_ok=True)
        wiki.write_text(WIKI_SEED, encoding="utf-8")
    # 지식책 최초 생성 (이후 remember/브리핑 때마다 자동 갱신)
    env = dict(os.environ, USERPROFILE=str(home), HOME=str(home))
    r = subprocess.run([sys.executable, str(workspace / "agent_ops" / "agentops.py"), "book"],
                       cwd=str(workspace), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if r.returncode == 0:
        print("       지식책 생성: USERDATA\\memory\\book\\knowledge_book.html")


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
    book = home / "OpenCodeLIG_USERDATA" / "memory" / "book" / "knowledge_book.html"
    if book.exists():
        content = ('@echo off\r\n'
                   'start "" "%USERPROFILE%\\OpenCodeLIG_USERDATA\\memory\\book\\knowledge_book.html"\r\n')
        (desktop / "지식책.bat").write_bytes(content.encode("ascii"))
    oc = home / "OpenCodeLIG" / "bin" / "oc.bat"
    if oc.exists():
        content = ('@echo off\r\n'
                   'call "%USERPROFILE%\\OpenCodeLIG\\workspace\\RUN_OPENCODE_LIG.bat"\r\n')
        (desktop / "오픈코드.bat").write_bytes(content.encode("ascii"))
        print("       바탕화면에 [AI비서]/[오픈코드] 바로가기를 만들었습니다.")
    else:
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
    install_global_brain(home, workspace)
    install_bin_launchers(home)
    install_opencode(home, workspace)
    seed_wiki(home, workspace)
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
