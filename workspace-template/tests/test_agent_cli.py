# -*- coding: utf-8 -*-
"""User-facing CLI/BAT smoke: real subprocess runs of the agent entrypoint.

Run: py -3.11 tests\\test_agent_cli.py
Mock mode exercises the whole chain (CLI/BAT -> run_agent_loop -> dispatch ->
file ops -> diagnostics) offline. Real provider behavior stays company
validation pending.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def make_env(tmp: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["AGENTOPS_ROOT"] = str(tmp / "작업공간")          # isolated Korean workspace
    env["LIG_DIAG_DIR"] = str(tmp / "diag")
    env["LIG_API_ENV_FILE"] = str(tmp / "no-such-lig-api.env")  # real mode must not be ready
    return env


def run(cmd: list, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(WS_TEMPLATE), env=env,
                          capture_output=True, timeout=120)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agentops_cli_"))
    (tmp / "작업공간").mkdir()
    env = make_env(tmp)
    py = ["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "agentops.py")]

    # --- mock mode via CLI ---
    r = run(py + ["agent", "--mode", "mock", "--task", "한글 문서 작성해줘"], env)
    out = r.stdout.decode("utf-8", errors="replace")
    check("mock CLI exits 0", r.returncode == 0, out + r.stderr.decode("utf-8", errors="replace"))
    check("mock CLI reports completed", "completed" in out, out)
    check("mock CLI labels mock mode", "mock" in out and "실제 모델 응답" in out, out)
    result_file = tmp / "작업공간" / "모의_결과" / "작업_요약.md"
    check("mock run created Korean output file", result_file.exists())
    check("output embeds the user task", "한글 문서 작성" in result_file.read_text(encoding="utf-8"))
    saved = tmp / "작업공간" / "agent_ops" / "results" / "llm_responses" / "agent_cli_last.md"
    check("final answer saved for user", saved.exists() and "모의 실행이 완료" in saved.read_text(encoding="utf-8"))

    # --- diagnostics ---
    loop_diag = tmp / "diag" / "agent-loop-last.json"
    check("agent-loop diagnostics written", loop_diag.exists())
    diag_data = json.loads(loop_diag.read_text(encoding="utf-8"))
    check("diagnostics show 2 tool executions", len(diag_data.get("tool_results", [])) == 2, str(diag_data))
    runtime_diag = tmp / "diag" / "runtime-last.json"
    runtime_data = json.loads(runtime_diag.read_text(encoding="utf-8"))
    check("mock agent routes document task to chat", runtime_data.get("route_selected") == "lig-chat" and runtime_data.get("route_reason") == "document_generation", str(runtime_data))

    # --- real mode without config: clear failure, exit 2 ---
    r2 = run(py + ["agent", "--mode", "real", "--task", "아무 작업"], env)
    err = r2.stderr.decode("utf-8", errors="replace")
    check("real mode unconfigured exits 2", r2.returncode == 2, err)
    check("real mode explains missing config", "lig-api.env" in err and "준비되지 않았습니다" in err, err)

    # --- missing --task: usage error ---
    r3 = run(py + ["agent", "--mode", "mock"], env)
    check("missing task exits 2", r3.returncode == 2, r3.stderr.decode("utf-8", errors="replace"))

    # --- BAT launcher end-to-end (the actual user command) ---
    bat = WS_TEMPLATE / "launch" / "run-agent.bat"
    tmp2 = Path(tempfile.mkdtemp(prefix="agentops_bat_"))
    (tmp2 / "작업공간").mkdir()
    env2 = make_env(tmp2)
    r4 = run([str(bat), "--mode", "mock", "--task", "BAT 한글 스모크"], env2)
    out4 = r4.stdout.decode("utf-8", errors="replace")
    check("run-agent.bat mock exits 0", r4.returncode == 0, out4 + r4.stderr.decode("utf-8", errors="replace"))
    check("run-agent.bat produced output file",
          (tmp2 / "작업공간" / "모의_결과" / "작업_요약.md").exists(), out4)
    check("run-agent.bat output embeds BAT task",
          "BAT 한글 스모크" in (tmp2 / "작업공간" / "모의_결과" / "작업_요약.md").read_text(encoding="utf-8"))

    print(f"\nALL {PASS} CHECKS PASSED (agent CLI/BAT smoke)")


if __name__ == "__main__":
    main()
