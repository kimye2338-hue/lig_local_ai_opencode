# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS))


def test_quality_gate_checks_runtime_memory_wiki_and_package_contracts() -> None:
    from agent_ops.quality_gate import run_quality_gate

    result = run_quality_gate(WS, run_commands=False)
    names = {check.name for check in result.checks}

    for name in [
        "launcher_fast_runtime",
        "launcher_direct_hamster",
        "launcher_ocd_project_dir",
        "plugin_runtime_enabled",
        "hamster_subagent_status_bridge",
        "self_improvement_auto_loop",
        "obsidian_wiki_autostart",
        "session_autosave_to_wiki",
        "memory_inject_nonblocking",
        "wiki_manager_smoke",
        "final_patch_self_contained",
        "hotfix_recreates_quality_gate",
    ]:
        assert name in names
    assert all(check.status == "PASS" for check in result.checks), result.to_markdown()


def test_quality_gate_cli_writes_markdown_report(tmp_path: Path) -> None:
    out = tmp_path / "quality-gate.md"
    result = subprocess.run(
        [
            sys.executable,
            str(WS / "agent_ops" / "quality_gate.py"),
            "--workspace",
            str(WS),
            "--no-commands",
            "--out",
            str(out),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists()
    report = out.read_text(encoding="utf-8")
    assert "OpenCodeLIG Quality Gate" in report
    assert "obsidian_wiki_autostart" in report
    assert "PASS" in report


def test_agentops_quality_gate_command_runs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(WS / "agent_ops" / "agentops.py"),
            "quality-gate",
            "--no-commands",
        ],
        cwd=str(WS),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OpenCodeLIG Quality Gate" in result.stdout


def test_hotfix_recreates_quality_gate_for_legacy_install(tmp_path: Path) -> None:
    from test_existing_install_hotfix import _copy_min_install, _run_hotfix

    root = _copy_min_install(tmp_path)
    target = root / "workspace" / "agent_ops" / "quality_gate.py"
    if target.exists():
        target.unlink()
    agentops = root / "workspace" / "agent_ops" / "agentops.py"
    text = agentops.read_text(encoding="utf-8")
    if "def cmd_quality_gate(args):" in text:
        start = text.index("\ndef cmd_quality_gate(args):")
        end = text.index("\ndef cmd_weekly(args):", start)
        text = text[:start] + "\n" + text[end:]
    text = text.replace('    p = sub.add_parser("quality-gate"); p.add_argument("--no-commands", action="store_true"); p.add_argument("--out", default=""); p.set_defaults(func=cmd_quality_gate)\n', "")
    agentops.write_text(text, encoding="utf-8")

    result = _run_hotfix(root, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "run_quality_gate" in text
    assert "obsidian_wiki_autostart" in text
    assert "self_improvement_auto_loop" in text
    patched_agentops = agentops.read_text(encoding="utf-8")
    assert "def cmd_quality_gate(args):" in patched_agentops
    assert 'sub.add_parser("quality-gate")' in patched_agentops


def test_quality_gate_uses_isolated_memory_for_wiki_smoke(monkeypatch) -> None:
    from agent_ops.quality_gate import run_quality_gate

    original = os.environ.get("AGENTOPS_MEMORY_DIR")
    with tempfile.TemporaryDirectory(prefix="quality_gate_memory_") as td:
        monkeypatch.setenv("AGENTOPS_MEMORY_DIR", td)
        result = run_quality_gate(WS, run_commands=False)
    monkeypatch.undo()
    if original is None:
        assert os.environ.get("AGENTOPS_MEMORY_DIR") is None or os.environ.get("AGENTOPS_MEMORY_DIR") == original
    else:
        assert os.environ.get("AGENTOPS_MEMORY_DIR") == original
    assert result.by_name("wiki_manager_smoke").status == "PASS"
