# -*- coding: utf-8 -*-
"""Weak-model capability-floor harness.

Run: py -3.11 tests\\test_capability_floor.py

If no local OpenAI-compatible server is listening, this runs mock self-checks,
prints the required SKIP line, and exits 0. When a local endpoint is available,
it executes the fixed scenario set and writes agent_ops/results/reports/
capability_floor.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

WS_TEMPLATE = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
REPORT_DIR = WS_TEMPLATE / "agent_ops" / "results" / "reports"
PASS = 0

sys.path.insert(0, str(WS_TEMPLATE))

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


SCENARIOS = [
    (1, "input/memo.txt 파일을 읽고 floor_요약.md로 요약해서 저장해줘. 반드시 브라켓 단어를 포함해줘", "floor_요약.md", "브라켓"),
    (2, "floor_노트.md 파일을 만들고 'floor smoke ok'라고 적어줘", "floor_노트.md", "floor smoke ok"),
    (3, "현재 폴더의 파일 목록을 확인하고 floor_목록.md에 저장해줘", "floor_목록.md", "memo"),
    (4, "input/데이터.csv 파일을 읽고 행 수를 floor_행수.md에 적어줘", "floor_행수.md", "3"),
    (5, "input/memo.txt를 읽고 액션아이템을 floor_액션.md로 정리해줘. 반드시 금요일 단어를 포함해줘", "floor_액션.md", "금요일"),
    (6, "floor_보고.md 파일을 만들고 제목과 결론 섹션을 포함한 보고서 틀을 적어줘", "floor_보고.md", "결론"),
    (7, "input/memo.txt 내용을 floor_사본.md로 복사해줘", "floor_사본.md", "케이블"),
    (8, "input/데이터.csv를 읽고 헤더 컬럼 이름들을 floor_컬럼.md에 나열해줘", "floor_컬럼.md", "이름"),
    (9, "floor_점검.md를 만들어 오늘 점검 항목 3개를 번호 목록으로 적어줘", "floor_점검.md", "1"),
    (10, "input/memo.txt를 읽고 한 줄 요약을 floor_한줄.md에 적어줘. 반드시 도면 단어를 포함해줘", "floor_한줄.md", "도면"),
]


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
                          capture_output=True, timeout=240)


def output_text(result: subprocess.CompletedProcess) -> str:
    return (result.stdout + b"\n" + result.stderr).decode("utf-8", errors="replace")


def copy_diag(tmp: Path, scenario: str) -> None:
    out_dir = tmp / "floor_diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)
    diag = tmp / "diag"
    for name in ("runtime-last.json", "agent-loop-last.json", "tool-dispatch-last.json"):
        src = diag / name
        if src.exists():
            (out_dir / f"{scenario}-{name}").write_text(
                src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")


def prepare_fixture(root: Path) -> None:
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "input" / "memo.txt").write_text(
        "회의 메모: 배터리 브라켓 도면 검토, 케이블 간섭 확인, 금요일까지 요약 필요",
        encoding="utf-8")
    (root / "input" / "데이터.csv").write_text("이름,값\nA,1\nB,2\nC,3\n", encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def classify_failure(row: Dict[str, Any]) -> str:
    if row.get("success"):
        return ""
    mode = row.get("tool_call_mode", "")
    outcome = row.get("outcome", "")
    if row.get("exit0") and not row.get("output_ok"):
        return "wrong_output"
    if mode == "none":
        return "parse_fail"
    if outcome == "tool_loop_cutoff":
        return "loop_cutoff"
    if outcome == "max_turns_exceeded":
        return "max_turns"
    if outcome == "llm_failed":
        return "llm_failed"
    return "other"


def summarize(rows: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    summary: Dict[int, Dict[str, Any]] = {}
    for num, task, _path, _word in SCENARIOS:
        items = [r for r in rows if r["scenario"] == num]
        modes: Dict[str, int] = {}
        failures: Dict[str, int] = {}
        for row in items:
            modes[row.get("tool_call_mode") or "missing"] = modes.get(row.get("tool_call_mode") or "missing", 0) + 1
            failure = classify_failure(row)
            if failure:
                failures[failure] = failures.get(failure, 0) + 1
        summary[num] = {
            "task": task,
            "success": sum(1 for r in items if r.get("success")),
            "total": len(items),
            "modes": modes,
            "failures": failures,
            "last_failure": next((r for r in reversed(items) if not r.get("success")), {}),
        }
    return summary


def format_counts(counts: Dict[str, int]) -> str:
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())) if counts else "-"


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(model or "unknown")).strip("_") or "unknown"


def report_path_for_model(model: str) -> Path:
    if model == "mock-self-check":
        return REPORT_DIR / "capability_floor_mock.md"
    return REPORT_DIR / f"capability_floor_{safe_model_name(model)}.md"


def write_report(rows: List[Dict[str, Any]], repeat: int, model: str) -> Path:
    total = len(rows)
    success = sum(1 for r in rows if r.get("success"))
    native = sum(1 for r in rows if r.get("tool_call_mode") == "native")
    pct = (success / total * 100.0) if total else 0.0
    summary = summarize(rows)
    lines = [
        "# capability floor 리포트",
        f"- 실행: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} / 모델: {model} / 반복: {repeat}",
        f"- 총 성공률: {success}/{total} ({pct:.1f}%)  / native 비율: {native}/{total}",
        "",
        "| # | 시나리오 | 성공 | tool_call_mode 분포 | 실패 유형 |",
        "|---|----------|------|--------------------|-----------|",
    ]
    for num, _task, _path, _word in SCENARIOS:
        item = summary[num]
        lines.append("| %d | %s | %d/%d | %s | %s |" % (
            num, item["task"], item["success"], item["total"],
            format_counts(item["modes"]), format_counts(item["failures"])))
    failures = [summary[num]["last_failure"] for num, _task, _path, _word in SCENARIOS
                if summary[num]["last_failure"]]
    if failures:
        lines.extend(["", "## 실패 사례 요약"])
        for row in failures:
            lines.append("- #%s %s: %s" % (
                row.get("scenario"), classify_failure(row),
                str(row.get("detail", ""))[:180].replace("\n", " ")))
    report_path = report_path_for_model(model)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def mock_selfcheck() -> None:
    fake_rows = [
        {"scenario": 1, "success": True, "exit0": True, "output_ok": True,
         "tool_call_mode": "native", "outcome": "completed"},
        {"scenario": 1, "success": False, "exit0": True, "output_ok": False,
         "tool_call_mode": "native", "outcome": "completed", "detail": "missing word"},
        {"scenario": 2, "success": False, "exit0": False, "output_ok": False,
         "tool_call_mode": "none", "outcome": "llm_failed", "detail": "no tool call"},
    ]
    for num, _task, _path, _word in SCENARIOS[2:]:
        fake_rows.append({"scenario": num, "success": True, "exit0": True, "output_ok": True,
                          "tool_call_mode": "text_fallback", "outcome": "completed"})
    summary = summarize(fake_rows)
    check("mock aggregation counts success", summary[1]["success"] == 1 and summary[1]["total"] == 2, str(summary[1]))
    check("mock aggregation classifies wrong_output",
          summary[1]["failures"].get("wrong_output") == 1, str(summary[1]))
    check("mock aggregation classifies parse_fail",
          summary[2]["failures"].get("parse_fail") == 1, str(summary[2]))
    report = write_report(fake_rows, repeat=1, model="mock-self-check")
    text = report.read_text(encoding="utf-8", errors="replace")
    check("report md generated", report.exists(), str(report))
    check("report has success line and table header",
          "- 총 성공률:" in text and "| # | 시나리오 | 성공 | tool_call_mode 분포 | 실패 유형 |" in text)
    scenario_rows = [line for line in text.splitlines() if line.startswith("| ") and line[2:4].strip().isdigit()]
    check("report has exactly 10 scenario rows", len(scenario_rows) == 10, str(len(scenario_rows)))
    from agent_ops.doctor import run_doctor
    doctor = run_doctor()
    floor_info = doctor.get("artifact_pipeline", {}).get("capability_floor_report")
    check("doctor reports capability floor report",
          isinstance(floor_info, dict) and Path(floor_info.get("path", "")).name.startswith("capability_floor_"),
          str(floor_info))
    check("mock report path is separated from real reports", report.name == "capability_floor_mock.md", str(report))


def run_real_floor() -> None:
    repeat = int(os.environ.get("FLOOR_REPEAT") or "3")
    if repeat < 1:
        repeat = 1
    rows: List[Dict[str, Any]] = []
    for run_idx in range(1, repeat + 1):
        for num, task, expected_file, required_word in SCENARIOS:
            tmp = Path(tempfile.mkdtemp(prefix=f"agentops_floor_{num}_{run_idx}_"))
            root = tmp / "작업공간"
            root.mkdir(parents=True)
            prepare_fixture(root)
            env = make_env(tmp)
            result = run_agent(task, env)
            out = output_text(result)
            copy_diag(tmp, f"{num}-{run_idx}")
            runtime = read_json(tmp / "diag" / "runtime-last.json")
            loop = read_json(tmp / "diag" / "agent-loop-last.json")
            target = root / expected_file
            target_text = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
            output_ok = target.exists() and required_word in target_text
            row = {
                "scenario": num,
                "run": run_idx,
                "exit0": result.returncode == 0,
                "output_ok": output_ok,
                "success": result.returncode == 0 and output_ok,
                "tool_call_mode": runtime.get("tool_call_mode", ""),
                "outcome": loop.get("outcome", ""),
                "detail": out if result.returncode != 0 else (target_text[:180] if target.exists() else "missing expected file"),
            }
            rows.append(row)
            print("INFO  scenario %d run %d exit=%s output_ok=%s mode=%s outcome=%s" % (
                num, run_idx, result.returncode, output_ok,
                row["tool_call_mode"] or "missing", row["outcome"] or "missing"))
    model = os.environ.get("LIG_LOCAL_MODEL") or "qwen2.5:7b-instruct"
    report = write_report(rows, repeat=repeat, model=model)
    text = report.read_text(encoding="utf-8", errors="replace")
    check("real report generated", report.exists(), str(report))
    check("real report records success rate", "- 총 성공률:" in text, text)
    check("real measurement covers all scenarios", len(rows) == len(SCENARIOS) * repeat, str(len(rows)))


def main() -> None:
    mock_selfcheck()
    if not local_llm_is_running():
        print("SKIP  local llm not running — skipped, not failed")
        return
    run_real_floor()
    print(f"\nALL {PASS} CHECKS PASSED (capability floor)")


if __name__ == "__main__":
    main()
