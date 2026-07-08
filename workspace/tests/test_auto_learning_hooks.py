# -*- coding: utf-8 -*-
"""WS-3 공통 실행 완료 후크(_complete_activity) 검증.

핵심: 결과가 어느 명령 경로에서 나오든 같은 방식으로 기억/audit에 축적되되,
① 성공은 activity 1건만(이중 적재 금지) ② 실패는 당일+동일원인 중복억제
③ 적재 실패가 본 작업을 막지 않음 ④ cmd_auto 위임 시 work/agent 경로 이중 적재 없음
⑤ recall --pinned 의 activity outcome 표시 절단.

Run: py -3.11 tests\test_auto_learning_hooks.py
(실제 USERDATA 미접촉 — AGENTOPS_MEMORY_DIR/AGENTOPS_ROOT 를 tmp 로 격리)
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="agentops_hooks_"))

# 반드시 agent_ops import 전에 격리 env 설정 (core.MEMORY 는 import 시 확정된다)
os.environ["AGENTOPS_MEMORY_DIR"] = str(TMP / "memory")
os.environ["AGENTOPS_ROOT"] = str(TMP / "workspace")
os.environ["LIG_DIAG_DIR"] = str(TMP / "diag")

sys.path.insert(0, str(WS))

import agent_ops.memory_manager as M  # noqa: E402
from agent_ops.core import write_jsonl  # noqa: E402
import agent_ops.agentops as A  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def reset_ledger() -> None:
    M.ensure_memory()
    write_jsonl(M.MEMORY_JSONL, [])


def rows(kind: str) -> list:
    return [r for r in M.load_memory(status="active") if r.get("kind") == kind]


def main() -> None:
    # ① 성공 후크: activity 1건만 적재(같은 날 같은 작업 재호출/얇은 래퍼 경유 모두 이중 아님)
    reset_ledger()
    res = A._complete_activity("보고서 작성", "완료", ok=True, files=["a.docx"])
    check("① 성공 후크 적재됨", res["logged"] is True and res["kind"] == "activity", str(res))
    A._log_activity("보고서 작성", "완료")           # 래퍼 경유 재호출
    A._complete_activity("보고서 작성", "완료", ok=True)  # 직접 재호출
    acts = rows("activity")
    check("① activity 정확히 1건(이중 적재 없음)", len(acts) == 1, str(len(acts)))
    check("① files 가 outcome 에 부가됨", "산출물" in str(acts[0].get("body")), str(acts[0]))

    # ② 실패 후크: error_pattern 1건 + 당일 동일원인 중복억제 + 다른 원인은 기록
    reset_ledger()
    r1 = A._complete_activity("엑셀 변환", ok=False, error_detail="원인X: 파일 잠김")
    r2 = A._complete_activity("엑셀 변환", ok=False, error_detail="원인X: 파일 잠김")
    check("② 첫 실패 기록됨", r1["logged"] is True and r1["kind"] == "error_pattern", str(r1))
    check("② 같은 날 같은 원인 중복 억제", r2["logged"] is False, str(r2))
    errs = rows("error_pattern")
    check("② error_pattern 1건 유지", len(errs) == 1, str(len(errs)))
    A._complete_activity("엑셀 변환", ok=False, error_detail="원인Y: 다른 오류")
    check("② 다른 원인은 새로 기록됨(해시 판별)", len(rows("error_pattern")) == 2,
          str(len(rows("error_pattern"))))

    # ③ 기억 저장 실패가 예외로 새어나오지 않는다
    reset_ledger()

    def _boom(*a, **k):
        raise RuntimeError("storage down")

    orig_add, orig_err = M.add_activity, M.record_self_error
    try:
        M.add_activity = _boom
        M.record_self_error = _boom
        res_ok = A._complete_activity("저장실패 작업", "완료", ok=True)
        res_ng = A._complete_activity("저장실패 작업", ok=False, error_detail="e")
        check("③ 저장 실패에도 예외 없음(성공 경로)", res_ok["logged"] is False, str(res_ok))
        check("③ 저장 실패에도 예외 없음(실패 경로)", res_ng["logged"] is False, str(res_ng))
    finally:
        M.add_activity, M.record_self_error = orig_add, orig_err

    # ④ cmd_auto 위임: auto 자체 경로(memory_wiki)는 auto 레벨에서 1건 적재,
    #    work(artifact) 경로는 하위 명령 적재에 맡기고 auto 레벨 이중 적재 없음
    def run_auto(task: str) -> tuple[Path, dict, int]:
        tmp = Path(tempfile.mkdtemp(prefix="agentops_auto_hook_"))
        env = dict(os.environ)
        env.update({
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "AGENTOPS_ROOT": str(tmp / "workspace"),
            "AGENTOPS_MEMORY_DIR": str(tmp / "memory"),
            "LIG_DIAG_DIR": str(tmp / "diag"),
        })
        cp = subprocess.run(
            [sys.executable, str(WS / "agent_ops" / "agentops.py"), "auto", "--task", task],
            cwd=str(WS), env=env, capture_output=True, timeout=180)
        trace = json.loads((tmp / "diag" / "auto-route-last.json").read_text(encoding="utf-8"))
        return tmp / "memory" / "memory.jsonl", trace, cp.returncode

    mem_path, trace, rc = run_auto("위키 정리해줘")
    check("④ auto(memory_wiki) 종료코드 0", rc == 0, str(trace))
    ledger = [json.loads(l) for l in mem_path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if mem_path.exists() else []
    auto_acts = [r for r in ledger if r.get("kind") == "activity"
                 and str(r.get("title", "")).startswith("auto: ")]
    check("④ auto 자체 경로는 후크 1건 적재", len(auto_acts) == 1, str(ledger))
    check("④ trace 에 후크 발화 기록", trace["memory_hooks"]
          and trace["memory_hooks"][0].startswith("_complete_activity fired"), str(trace["memory_hooks"]))

    mem_path, trace, rc = run_auto("이 내용으로 문서 작성해줘")
    check("④ auto(artifact→work) 종료코드 0", rc == 0, str(trace))
    ledger = [json.loads(l) for l in mem_path.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if mem_path.exists() else []
    work_acts = [r for r in ledger if r.get("kind") == "activity"]
    auto_acts = [r for r in work_acts if str(r.get("title", "")).startswith("auto: ")]
    check("④ work 위임 경로: 하위 명령 적재 1건 + auto 레벨 이중 적재 없음",
          len(work_acts) == 1 and len(auto_acts) == 0, str(work_acts))
    check("④ trace 에 위임 표시", trace["memory_hooks"]
          and trace["memory_hooks"][0].startswith("delegated:"), str(trace["memory_hooks"]))

    # ⑤ recall --pinned: activity outcome 표시 절단(원장 원본은 불변)
    reset_ledger()
    long_body = "가" * 500
    M.add_memory_event("activity", "긴작업기록", long_body, priority="low", source="agent")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        A.cmd_recall(argparse.Namespace(pinned=True, keywords=[], kind="", limit=6))
    out = buf.getvalue()
    check("⑤ pinned 출력에 activity 노출", "긴작업기록" in out, out[:300])
    check("⑤ activity outcome 이 상한(200자) 이하로 절단", "가" * 201 not in out and "절단" in out,
          out[:400])
    stored = [r for r in M.load_memory() if r.get("title") == "긴작업기록"]
    check("⑤ 원장 원본은 절단되지 않음", stored and stored[0].get("body") == long_body,
          str(len(str(stored[0].get('body'))) if stored else 0))

    print(f"\nALL {PASS} CHECKS PASSED (auto learning hooks)")


if __name__ == "__main__":
    main()
