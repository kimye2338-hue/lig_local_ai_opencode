# -*- coding: utf-8 -*-
"""ocd — 현재 폴더에서 OpenCodeLIG 를 연다 (폴더-로컬 프로필 + 전역 기억).

사용법 (설치 후 아무 폴더의 새 CMD 창에서):
    cd C:\\some\\project
    ocd

동작 (plan/tasks/FABLE-OCD-WORKSPACE-PROFILES.md):
  1. 현재 폴더에 .opencodelig 프로필이 없으면 시드 파일을 만든다(있으면 보존).
  2. 전역 기억(%USERPROFILE%\\OpenCodeLIG_USERDATA\\memory)은 그대로 공유한다.
  3. AGENTOPS_PROJECT_* 환경변수를 채워 런처(oc.bat/opencode.exe)를 현재
     폴더에서 실행한다 — 에이전트 루프가 로컬 페르소나/규칙/기억을 주입한다.

stdlib only. 기억 폴더는 절대 쓰지/지우지 않는다(읽기 경로만 알려줌).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ocd.bat 이 이 파일을 직접 실행하므로(패키지 밖) 부모를 sys.path에 올린다.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.project_profile import (  # noqa: E402
    PROFILE_DIRNAME,
    global_memory_dir,
    profile_diagnostics,
    seed_profile,
)


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def find_launcher(home: Path) -> Path | None:
    """설치된 OpenCode 런처를 찾는다. oc.bat(환경/secret 로드 포함)이 1순위."""
    for cand in (home / "OpenCodeLIG" / "bin" / "oc.bat",
                 home / "OpenCodeLIG" / "bin" / "opencode.exe"):
        if cand.is_file():
            return cand
    return None


def build_env(cwd: Path) -> dict:
    """자식 프로세스(OpenCode/에이전트)에 전역+로컬 컨텍스트 위치를 알린다."""
    profile_dir = cwd / PROFILE_DIRNAME
    env = dict(os.environ)
    env.setdefault("AGENTOPS_MEMORY_DIR", str(global_memory_dir()))
    env["AGENTOPS_PROJECT_DIR"] = str(profile_dir)
    env["AGENTOPS_PROJECT_PERSONA"] = str(profile_dir / "PERSONA.md")
    env["AGENTOPS_PROJECT_MEMORY"] = str(profile_dir / "PROJECT_MEMORY.md")
    env["AGENTOPS_PROJECT_RULES"] = str(profile_dir / "RULES.md")
    return env


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ocd", description="현재 폴더에서 OpenCodeLIG 실행")
    ap.add_argument("--no-launch", action="store_true",
                    help="프로필 시드/진단만 하고 OpenCode는 띄우지 않음")
    ap.add_argument("--status", action="store_true",
                    help="프로필/기억 진단을 JSON으로 출력")
    a, passthrough = ap.parse_known_args(argv)

    cwd = Path.cwd()
    seeded = seed_profile(cwd)
    from agent_ops.project_profile import LAUNCHER_NAME  # noqa: E402
    sep0 = "\\" if os.name == "nt" else "/"
    if seeded["created"]:
        print(f"[OpenCodeLIG] Local profile created: {PROFILE_DIRNAME}")
        for name in seeded["created"]:
            if name == LAUNCHER_NAME:  # 폴더 루트 런처(클릭용) — 별도 안내
                print(f"[OpenCodeLIG]   + {name}  (다음부터 이 파일 더블클릭하면 여기서 OpenCode 가 열림)")
            else:
                print(f"[OpenCodeLIG]   + {PROFILE_DIRNAME}{sep0}{name}")
    else:
        print(f"[OpenCodeLIG] Local profile found: {PROFILE_DIRNAME}")
        if seeded.get("launcher"):
            print(f"[OpenCodeLIG] 폴더 런처: {LAUNCHER_NAME} (더블클릭하면 여기서 OpenCode 가 열림)")
    print(f"[OpenCodeLIG] Global memory: {global_memory_dir()}")
    sep = "\\" if os.name == "nt" else "/"
    print(f"[OpenCodeLIG] Local persona: {PROFILE_DIRNAME}{sep}PERSONA.md")

    if a.status:
        print(json.dumps(profile_diagnostics(cwd), ensure_ascii=False, indent=2))
    if a.no_launch:
        return 0

    launcher = find_launcher(_home())
    if launcher is None:
        print("[OpenCodeLIG] OpenCode 런처를 찾지 못했습니다 "
              "(%USERPROFILE%\\OpenCodeLIG\\bin\\oc.bat 없음).")
        print("[OpenCodeLIG] 전체 번들의 설치.bat 으로 먼저 설치하세요. "
              "프로필 파일은 이미 준비됐습니다.")
        return 3

    print("[OpenCodeLIG] Starting OpenCode in this folder...")
    env = build_env(cwd)
    if launcher.suffix.lower() == ".bat":
        args = ["cmd", "/c", str(launcher)] + list(passthrough)
    else:
        args = [str(launcher)] + list(passthrough)
    try:
        return subprocess.call(args, cwd=str(cwd), env=env)
    except OSError as exc:
        print(f"[OpenCodeLIG] 실행 실패: {exc}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
