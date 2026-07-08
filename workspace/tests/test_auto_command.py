# -*- coding: utf-8 -*-
"""WS-1 auto command routing + WS-7 policy layer tests.

Run: py -3.11 tests\test_auto_command.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def run_auto(task: str, *extra: str) -> tuple[subprocess.CompletedProcess[bytes], Path]:
    tmp = Path(tempfile.mkdtemp(prefix="agentops_auto_"))
    root = tmp / "workspace"
    diag = tmp / "diag"
    env = dict(os.environ)
    env.update({
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "AGENTOPS_ROOT": str(root),
        "AGENTOPS_MEMORY_DIR": str(tmp / "memory"),
        "LIG_DIAG_DIR": str(diag),
    })
    cmd = ["py", "-3.11", str(WS / "agent_ops" / "agentops.py"),
           "auto", "--task", task, *extra]
    cp = subprocess.run(cmd, cwd=str(WS), env=env, capture_output=True, timeout=120)
    return cp, diag / "auto-route-last.json"


def read_trace(path: Path) -> dict:
    check("auto trace exists", path.exists(), str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    cp, trace_path = run_auto("2026-07-10까지 진동시험 보고서 마감 일정 등록해줘")
    out = cp.stdout.decode("utf-8", errors="replace")
    err = cp.stderr.decode("utf-8", errors="replace")
    trace = read_trace(trace_path)
    check("auto schedule exits 0", cp.returncode == 0, out + err)
    check("auto routes high-confidence schedule to command-native",
          trace["selected_path"] == "command_native" and trace["command"] == "schedule_add",
          str(trace))
    check("auto schedule keeps safety note", trace["safety"]["approval_bypass"] is False)
    check("auto schedule policy stays execute (no ask spam on reversible native path)",
          trace["policy"]["mode"] == "execute"
          and trace["policy"]["requires_confirmation"] is False, str(trace.get("policy")))

    cp, trace_path = run_auto("이 내용으로 문서 작성해줘")
    trace = read_trace(trace_path)
    check("auto artifact exits 0", cp.returncode == 0,
          cp.stdout.decode("utf-8", errors="replace") + cp.stderr.decode("utf-8", errors="replace"))
    check("auto routes document to work artifact path",
          trace["selected_path"] == "artifact" and trace["command"] == "work"
          and "document" in trace["artifact_kinds"], str(trace))
    check("auto artifact policy stays execute (reversible output)",
          trace["policy"]["mode"] == "execute", str(trace.get("policy")))

    cp, trace_path = run_auto("업무 폴더의 임시 파일 전부 삭제해줘")
    out = cp.stdout.decode("utf-8", errors="replace")
    err = cp.stderr.decode("utf-8", errors="replace")
    trace = read_trace(trace_path)
    check("auto delete request exits 0 without executing", cp.returncode == 0, out + err)
    check("auto delete request asks the user (policy ask_user)",
          trace["policy"]["mode"] == "ask_user"
          and trace["policy"]["requires_confirmation"] is True, str(trace.get("policy")))
    check("auto delete request falls back to plan, not silent execution",
          trace.get("effective_mode") == "ask_user"
          and trace.get("outcome") == "needs_confirmation", str(trace))
    check("auto delete trace records the question for WS-8 evaluation",
          bool(trace["policy"].get("question")), str(trace.get("policy")))
    check("auto delete keeps approval note (no safety bypass)",
          trace["safety"]["approval_bypass"] is False)
    check("auto delete prints confirmation guidance", "확인 필요" in out, out)

    cp, trace_path = run_auto("메모 파일 읽어줘", "--dry-run")
    trace = read_trace(trace_path)
    check("auto dry-run exits 0", cp.returncode == 0)
    check("auto routes no-artifact file task to tool agent",
          trace["selected_path"] == "tool_agent" and trace["command"] == "agent"
          and trace["outcome"] == "dry_run", str(trace))

    cp, trace_path = run_auto("아무 관련 없는 요청 xyz", "--dry-run")
    trace = read_trace(trace_path)
    check("auto ambiguous request falls back to plan_only",
          trace["selected_path"] == "plan_only" and trace["command"] == "plan",
          str(trace))

    cp, trace_path = run_auto("위키 정리해줘", "--dry-run")
    trace = read_trace(trace_path)
    check("auto routes wiki keyword to memory_wiki",
          trace["selected_path"] == "memory_wiki" and trace["command"] == "wiki",
          str(trace))

    cp, trace_path = run_auto("크롬으로 회사 포털 확인해줘", "--dry-run")
    trace = read_trace(trace_path)
    check("auto browser trace exits 0", cp.returncode == 0)
    hints = trace.get("route_hints", {})
    check("auto trace records tool hints",
          "browser_action" in hints.get("tools", []), str(trace))
    check("auto trace records skill hints",
          "웹" in hints.get("skill_sections", []), str(trace))

    print(f"\nALL {PASS} CHECKS PASSED (auto command)")


if __name__ == "__main__":
    main()
