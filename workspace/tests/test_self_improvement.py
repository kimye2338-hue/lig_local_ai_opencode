# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import importlib
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _reload_modules() -> None:
    for name in ["agent_ops.core", "agent_ops.memory_manager", "agent_ops.self_improvement"]:
        if name in sys.modules:
            importlib.reload(sys.modules[name])


def test_self_improvement_defaults_on_and_can_be_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIG_SELF_IMPROVEMENT_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTOPS_MEMORY_DIR", str(tmp_path / "memory"))
    _reload_modules()
    from agent_ops.self_improvement import get_settings, record_error, set_enabled

    assert get_settings()["enabled"] is True
    first = record_error("tool", "missing required argument", task="read memo")
    assert first is not None

    set_enabled(False)
    second = record_error("tool", "another failure", task="read memo")
    assert second is None

    rows = _read_jsonl(tmp_path / "memory" / "memory.jsonl")
    assert len(rows) == 1
    assert rows[0]["kind"] == "error_pattern"
    assert rows[0]["source"] == "self_observed"


def test_failure_then_success_creates_actionable_lesson(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIG_SELF_IMPROVEMENT_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTOPS_MEMORY_DIR", str(tmp_path / "memory"))
    _reload_modules()
    from agent_ops.self_improvement import capture_task_result, lessons_for_injection

    capture_task_result(
        "햄스터 상태 표시 수정",
        ok=False,
        area="hamster_status",
        detail="subagent 작업 중 상태가 보이지 않음",
        run_id="run1",
    )
    capture_task_result(
        "햄스터 상태 표시 수정",
        ok=True,
        area="hamster_status",
        detail="hamster-status.ts에서 task/subagent 이벤트를 working으로 기록",
        route="plugin",
        run_id="run1",
    )

    rows = _read_jsonl(tmp_path / "memory" / "memory.jsonl")
    assert [e["kind"] for e in rows] == ["error_pattern", "lesson"]
    assert rows[1]["source"] == "self_fix"
    assert "hamster_status" in rows[1]["body"]
    assert lessons_for_injection(limit=3)[0]["id"] == rows[1]["id"]


def test_self_improvement_injection_is_limited_and_formatted(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LIG_SELF_IMPROVEMENT_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTOPS_MEMORY_DIR", str(tmp_path / "memory"))
    _reload_modules()
    from agent_ops.memory_manager import add_memory_event
    from agent_ops.self_improvement import format_injection_block

    for i in range(5):
        add_memory_event(
            "lesson",
            f"자가개선 교훈: area{i}",
            f"next action {i}",
            source="self_fix",
        )

    block = format_injection_block(limit=3)
    assert "OpenCodeLIG 자가개선 지침" in block
    assert block.count("- ") == 3
    assert "next action 4" in block
    assert "next action 0" not in block


def test_agentops_self_improve_cli_status_on_off_and_report(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["LIG_SELF_IMPROVEMENT_DIR"] = str(tmp_path)
    env["AGENTOPS_MEMORY_DIR"] = str(tmp_path / "memory")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(WS / "agent_ops" / "agentops.py"), "self-improve", *args],
            cwd=str(WS),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )

    assert run("status").returncode == 0
    off = run("off")
    assert off.returncode == 0
    assert '"enabled": false' in off.stdout.lower()
    on = run("on")
    assert on.returncode == 0
    assert '"enabled": true' in on.stdout.lower()
    report = run("report")
    assert report.returncode == 0
    assert (tmp_path / "report.md").exists()
    assert "Self Improvement Report" in report.stdout
