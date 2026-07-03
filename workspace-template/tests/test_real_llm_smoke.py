# -*- coding: utf-8 -*-
"""Real local OpenAI-compatible LLM smoke test.

Run: py -3.11 tests\test_real_llm_smoke.py

If no local server is listening, this prints an honest SKIP and exits 0. When a
local OpenAI-compatible endpoint is available, it runs real-mode subprocess
scenarios through run-agent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def base_url() -> str:
    return (os.environ.get("LIG_LOCAL_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def local_llm_is_running() -> bool:
    try:
        with urllib.request.urlopen(base_url() + "/models", timeout=2) as response:
            response.read(256)
        return True
    except Exception:
        return False


def make_env(tmp: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["AGENTOPS_ROOT"] = str(tmp / "작업공간")
    env["LIG_DIAG_DIR"] = str(tmp / "diag")
    env["LIG_API_ENV_FILE"] = str(tmp / "no-such-lig-api.env")
    env["LIG_PROVIDER_PROFILE"] = "local_openai"
    env["LIG_LOCAL_BASE_URL"] = base_url()
    env["LIG_LOCAL_MODEL"] = os.environ.get("LIG_LOCAL_MODEL") or "qwen2.5:7b-instruct"
    env["LIG_API_TIMEOUT_SEC"] = os.environ.get("LIG_API_TIMEOUT_SEC") or "120"
    return env


def run_agent(task: str, env: dict) -> subprocess.CompletedProcess:
    cmd = ["py", "-3.11", str(WS_TEMPLATE / "agent_ops" / "agentops.py"),
           "agent", "--mode", "real", "--max-turns", "8", "--task", task]
    return subprocess.run(cmd, cwd=str(WS_TEMPLATE), env=env,
                          capture_output=True, timeout=180)


def output_text(result: subprocess.CompletedProcess) -> str:
    return (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")


def copy_diag(tmp: Path, scenario: str) -> None:
    out_dir = tmp / "smoke_diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    diag = tmp / "diag"
    for name in ("runtime-last.json", "agent-loop-last.json", "tool-dispatch-last.json"):
        src = diag / name
        if src.exists():
            (out_dir / f"{scenario}-{name}").write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")


def main() -> None:
    if not local_llm_is_running():
        print("SKIP  local llm not running — skipped, not failed")
        return

    tmp = Path(tempfile.mkdtemp(prefix="agentops_real_llm_"))
    root = tmp / "작업공간"
    root.mkdir(parents=True)
    env = make_env(tmp)

    (root / "input").mkdir()
    memo = root / "input" / "memo.txt"
    memo.write_text("회의 메모: 배터리 브라켓 도면 검토, 케이블 간섭 확인, 금요일까지 요약 필요", encoding="utf-8")

    r1 = run_agent("input/memo.txt 파일을 읽고 summary.md로 요약해서 저장해줘", env)
    out1 = output_text(r1)
    copy_diag(tmp, "summary")
    check("real scenario 1 exits 0", r1.returncode == 0, out1)
    summary = root / "summary.md"
    check("real scenario 1 creates summary.md", summary.exists(), out1)
    check("summary mentions source memo", "브라켓" in summary.read_text(encoding="utf-8", errors="replace"))

    r2 = run_agent("new_note.md 파일을 만들고 'local llm smoke ok'라고 적어줘", env)
    out2 = output_text(r2)
    copy_diag(tmp, "create")
    check("real scenario 2 exits 0", r2.returncode == 0, out2)
    note = root / "new_note.md"
    check("real scenario 2 creates new_note.md", note.exists(), out2)
    check("created file has requested text", "local llm smoke ok" in note.read_text(encoding="utf-8", errors="replace").lower())

    r3 = run_agent("가능한 도구만 사용해서 현재 폴더를 확인하고 done.md를 만들어줘", env)
    out3 = output_text(r3)
    copy_diag(tmp, "recovery")
    check("real scenario 3 exits 0", r3.returncode == 0, out3)
    check("real scenario 3 reaches normal completion", "결과: completed" in out3, out3)
    check("diagnostics copied", (tmp / "smoke_diagnostics").exists())

    diag = json.loads((tmp / "diag" / "runtime-last.json").read_text(encoding="utf-8"))
    check("runtime diag records local_openai profile", diag.get("profile") == "local_openai", str(diag))
    check("runtime diag records selected route", bool(diag.get("route_selected")), str(diag))

    print(f"\nALL {PASS} CHECKS PASSED (real local LLM smoke)")


if __name__ == "__main__":
    main()
