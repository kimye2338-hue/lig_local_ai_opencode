# -*- coding: utf-8 -*-
"""E2E tests for the agentops work command.

Run: py -3.11 tests\test_work_command.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS_TEMPLATE = Path(__file__).resolve().parents[1]
AGENTOPS = WS_TEMPLATE / "agent_ops" / "agentops.py"
PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def env_for(case: str) -> tuple[Path, dict]:
    tmp = Path(tempfile.mkdtemp(prefix=f"work_cmd_{case}_"))
    ws = tmp / "작업공간"
    env = dict(os.environ)
    env.update({
        "AGENTOPS_ROOT": str(ws),
        "LIG_AUDIT_DIR": str(tmp / "audit"),
        "LIG_DIAG_DIR": str(tmp / "diag"),
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    return ws, env


def run_work(args: list[str], env: dict, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(["py", "-3.11", str(AGENTOPS), "work", *args],
                          cwd=str(WS_TEMPLATE), env=env, input=stdin.encode("utf-8"),
                          capture_output=True, timeout=180)


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_report(ws: Path) -> Path:
    reports = sorted((ws / "agent_ops" / "results" / "reports").glob("work_*.md"))
    return reports[-1] if reports else Path("")


def test_success_with_execute_pending() -> None:
    ws, env = env_for("success")
    r = run_work(["--task", "Excel 매크로 만들어줘", "--execute", "--yes"], env)
    out = decode(r.stdout) + decode(r.stderr)
    check("work --yes mock exits 0", r.returncode == 0, out)
    report = latest_report(ws)
    check("work report md exists", report.exists(), out)
    body = report.read_text(encoding="utf-8")
    required = ["## 요청", "## 계획", "## 승인", "## 산출물과 품질", "## audit 요약", "## pending", "## 다음 명령"]
    check("work report has required sections", all(item in body for item in required), body)
    # --execute semantics: kinds without a safe auto-mapping are reported
    # honestly as no-auto-run (vba_macro without an input .xlsx here).
    check("work report records no-auto-run for unmapped execute", "no-auto-run" in body, body)
    check("no-auto-run explains manual path", "수동" in body or "실행 생략" in body, body)
    run_id = report.stem.replace("work_", "")
    check("artifact folder reuses run id", (ws / "agent_ops" / "results" / "artifacts" / run_id).exists(), run_id)
    rows = read_jsonl(Path(env["LIG_AUDIT_DIR"]) / "audit.jsonl")
    run_ids = {row["run_id"] for row in rows if row.get("run_id")}
    check("audit uses one run id for success", run_ids == {run_id}, str(rows))
    # adapters append their own audit rows (kind=adapter, no run task) — scope
    # the task-summary assertion to the work command's own rows.
    work_rows = [row for row in rows if row.get("kind") == "work"]
    check("audit stores task summary", work_rows and all("Excel 매크로" in row.get("task", "") for row in work_rows), str(rows))


def test_denied_before_artifacts() -> None:
    ws, env = env_for("denied")
    # matlab task: matlab adapter is available -> --execute creates a dangerous
    # approval row -> interactive prompt -> 'n' denies. (Kinds with no auto-run
    # mapping no longer create fake dangerous rows, so use an executable kind.)
    r = run_work(["--task", "시험 데이터 매트랩 후처리 스크립트 만들어줘", "--execute"], env, stdin="n\n")
    out = decode(r.stdout) + decode(r.stderr)
    check("work denial exits 3", r.returncode == 3, out)
    check("work denial explains stop", "승인 거부로 중단" in out, out)
    artifacts = ws / "agent_ops" / "results" / "artifacts"
    check("denial creates no artifacts", not artifacts.exists() or not list(artifacts.rglob("*")), str(artifacts))
    rows = read_jsonl(Path(env["LIG_AUDIT_DIR"]) / "audit.jsonl")
    check("denial audit recorded", any(row.get("verdict") == "denied" for row in rows), str(rows))


def test_input_grounded_and_task_file() -> None:
    ws, env = env_for("input")
    data_dir = ws / "inputs"
    data_dir.mkdir(parents=True)
    csv = data_dir / "시험결과.csv"
    csv.write_text("항목,값\n치수B,불합격\n", encoding="utf-8")
    task_file = data_dir / "task.txt"
    task_file.write_text("시험 결과 파일 읽고 보고서 만들어줘", encoding="utf-8")
    r = run_work(["--task-file", str(task_file), "--input", str(csv), "--yes"], env)
    out = decode(r.stdout) + decode(r.stderr)
    check("work --task-file with input exits 0", r.returncode == 0, out)
    check("work reports input summary", "입력 자료 요약" in out, out)
    report = latest_report(ws)
    body = report.read_text(encoding="utf-8")
    check("work report includes input file name", "시험결과.csv" in body, body)
    docs = list((ws / "agent_ops" / "results" / "artifacts").rglob("문서.md"))
    check("input-grounded artifact reflects CSV contents",
          bool(docs) and any("치수B" in p.read_text(encoding="utf-8") for p in docs),
          str(docs))
    rows = read_jsonl(Path(env["LIG_AUDIT_DIR"]) / "audit.jsonl")
    run_ids = {row["run_id"] for row in rows if row.get("run_id")}
    check("input run audit has one run id", len(run_ids) == 1, str(rows))


def test_file_ops_uses_agent_loop() -> None:
    ws, env = env_for("fileops")
    r = run_work(["--task", "read file", "--yes"], env)
    out = decode(r.stdout) + decode(r.stderr)
    check("file_ops work exits 0", r.returncode == 0, out)
    report = latest_report(ws)
    body = report.read_text(encoding="utf-8")
    check("file_ops work writes final report", report.exists() and "agent_loop" in body, body)
    responses = list((ws / "agent_ops" / "results" / "llm_responses").glob("work_*.md"))
    check("file_ops work used mock agent loop", bool(responses) and "모의 실행이 완료" in responses[-1].read_text(encoding="utf-8"),
          str(responses))


def main() -> None:
    test_success_with_execute_pending()
    test_denied_before_artifacts()
    test_input_grounded_and_task_file()
    test_file_ops_uses_agent_loop()
    print(f"\nALL {PASS} CHECKS PASSED (work command)")


if __name__ == "__main__":
    main()
