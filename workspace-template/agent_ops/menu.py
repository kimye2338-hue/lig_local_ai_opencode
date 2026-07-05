# -*- coding: utf-8 -*-
"""AI비서 일일 메뉴 — launch\\menu.bat 가 호출한다.

배치(.bat)에는 로직을 두지 않는다(코드페이지/경로 재해석 함정) — 메뉴 로직은
전부 여기(파이썬)에 있고, 리눅스 CI에서도 stdin 주입으로 실행 검증된다.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]          # workspace root
AGENTOPS = WS / "agent_ops" / "agentops.py"
ARTIFACTS = WS / "agent_ops" / "results" / "artifacts"
REPORTS = WS / "agent_ops" / "results" / "reports"
DIAG = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "OpenCodeLIG_USERDATA" / "diagnostics"

MENU = """
 ============================================
   AI비서 - 무엇을 도와드릴까요?
 ============================================
   1. 업무 시키기      (예: 회의록 초안 만들어줘)
   2. 아침 브리핑      (오늘 일정/할일/어제 요약)
   3. 주간보고 초안
   4. 일정 추가        (예: 금요일 14시 보고서 마감)
   5. 오늘/이번주 일정 보기
   6. Outlook 일정 가져오기
   7. 상태 진단        (doctor)
   0. 종료
 --------------------------------------------"""


def _run(args: list[str]) -> int:
    return subprocess.call([sys.executable, str(AGENTOPS)] + args, cwd=str(WS))


def _open_folder(path: Path) -> None:
    print(f" 폴더: {path}")
    if os.name == "nt":
        try:
            os.startfile(str(path))  # noqa: S606 - explorer open, user-requested
        except OSError:
            pass


def _latest_artifact_dir() -> Path:
    runs = sorted([p for p in ARTIFACTS.glob("*") if p.is_dir()], reverse=True)
    return runs[0] if runs else ARTIFACTS


def do_task() -> None:
    task = input("무슨 작업을 할까요? (한 줄로): ").strip().strip('"')
    if not task:
        print(" 작업 내용이 비어 있습니다.")
        return
    ref = input("참고할 파일/폴더 경로 (없으면 Enter): ").strip().strip('"')
    args = ["work", "--task", task, "--mode", "real"]
    if ref:
        args += ["--input", ref]
    rc = _run(args)
    if rc != 0:
        print("\n [안내] 작업이 완료되지 못했습니다. 메뉴 7번(상태 진단)을 실행하거나")
        print(f"        {DIAG} 를 확인하세요.")
        return
    print("\n 완료. 산출물:")
    _open_folder(_latest_artifact_dir())


def main() -> int:
    if not AGENTOPS.exists():
        print(f"[오류] agentops.py 를 찾지 못했습니다: {AGENTOPS}")
        return 9
    actions = {
        "1": do_task,
        "2": lambda: (_run(["briefing"]), print(f" 보고서: {REPORTS}  (.md는 메모장으로 열어도 됩니다)")),
        "3": lambda: (_run(["weekly"]), print(f" 보고서: {REPORTS}")),
        "4": lambda: (lambda s: _run(["schedule", "add", s]) if s else print(" 일정 내용이 비어 있습니다."))(
            input("일정 내용 (예: 금요일 14시 진동시험 보고서 마감): ").strip().strip('"')),
        "5": lambda: _run(["schedule", "list", "--when", "week"]),
        "6": lambda: _run(["schedule", "sync-outlook"]),
        "7": lambda: _run(["doctor"]),
    }
    while True:
        print(MENU)
        try:
            sel = input("번호 선택: ").strip()
        except EOFError:
            return 0
        if sel == "0":
            return 0
        action = actions.get(sel)
        if action is None:
            print(" 잘못된 선택입니다.")
            continue
        try:
            action()
        except KeyboardInterrupt:
            print("\n (취소됨)")
        input("\n[Enter] 메뉴로 돌아갑니다...")


if __name__ == "__main__":
    raise SystemExit(main())
