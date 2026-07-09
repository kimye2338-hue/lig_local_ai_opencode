# -*- coding: utf-8 -*-
"""Release quality gate for OpenCodeLIG.

This gate turns recurring release assumptions into executable checks. It is
deliberately conservative: a release-critical behavior is PASS only when the
installed launcher/package path proves the behavior, not when a file merely
exists.
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class GateCheck:
    name: str
    status: str
    evidence: str
    next_action: str = ""


@dataclass
class GateResult:
    checks: list[GateCheck]
    report_path: Path | None = None

    def by_name(self, name: str) -> GateCheck:
        for check in self.checks:
            if check.name == name:
                return check
        raise KeyError(name)

    @property
    def ok(self) -> bool:
        return all(check.status == "PASS" for check in self.checks)

    def to_markdown(self) -> str:
        counts: dict[str, int] = {}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        lines = [
            "# OpenCodeLIG Quality Gate",
            "",
            f"- timestamp: `{datetime.now().astimezone().isoformat(timespec='seconds')}`",
            f"- verdict: `{'PASS' if self.ok else 'FAIL'}`",
            "- counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
            "",
            "| status | check | evidence | next action |",
            "|---|---|---|---|",
        ]
        for check in self.checks:
            evidence = check.evidence.replace("\n", " ")[:800]
            next_action = check.next_action.replace("\n", " ")[:400]
            lines.append(f"| {check.status} | {check.name} | {evidence} | {next_action} |")
        return "\n".join(lines) + "\n"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _crlf_only(path: Path) -> bool:
    raw = path.read_bytes() if path.exists() else b""
    return bool(raw) and b"\n" not in raw.replace(b"\r\n", b"")


def _add(checks: list[GateCheck], name: str, ok: bool, evidence: str, next_action: str = "") -> None:
    checks.append(GateCheck(name=name, status="PASS" if ok else "FAIL", evidence=evidence, next_action=next_action))


def _markers(text: str, required: list[str]) -> tuple[bool, str]:
    present = {marker: marker in text for marker in required}
    return all(present.values()), "; ".join(f"{k}={v}" for k, v in present.items())


def _check_launcher(workspace: Path, checks: list[GateCheck]) -> None:
    launcher = workspace / "RUN_OPENCODE_LIG.bat"
    text = _read_text(launcher)
    run_idx = text.find("\"%OCODE_EXE%\" %*")

    fast_required = [
        "OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\\opencode_fast_runtime",
        "OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%",
        "XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%",
        "XDG_DATA_HOME=%OPENCODE_FAST_DATA%",
        "XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%",
        "OPENCODE_DISABLE_MODELS_FETCH=1",
        "OPENCODE_DISABLE_AUTOUPDATE=1",
        "OPENCODE_DISABLE_LSP_DOWNLOAD=1",
        "OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json",
        "NPM_CONFIG_REGISTRY=http://127.0.0.1:9/",
        "BUN_CONFIG_REGISTRY=http://127.0.0.1:9/",
        "NO_PROXY=*",
        "set \"OPENCODE_PURE=\"",
    ]
    fast_ok, fast_evidence = _markers(text, fast_required)
    before_run = run_idx >= 0 and all(0 <= text.find(marker) < run_idx for marker in fast_required)
    _add(
        checks,
        "launcher_fast_runtime",
        launcher.exists() and _crlf_only(launcher) and fast_ok and before_run and "OPENCODE_PURE=1" not in text,
        f"path={launcher}; crlf={_crlf_only(launcher)}; before_run={before_run}; {fast_evidence}; pure1={'OPENCODE_PURE=1' in text}",
        "OpenCode 실행 직전 fast runtime/offline 환경변수를 설정하고 OPENCODE_PURE=1을 제거하세요.",
    )

    hamster_required = [
        "LIG_WORKSPACE_HOME=%USERPROFILE%\\OpenCodeLIG\\workspace",
        "agent_ops\\ui\\hamster_overlay.py",
        "hamster_overlay_start.log",
        "start \"OpenCodeLIG Hamster\"",
        "LIG_AGENTOPS_HOME=%LIG_WORKSPACE_HOME%",
    ]
    hamster_ok, hamster_evidence = _markers(text, hamster_required)
    _add(
        checks,
        "launcher_direct_hamster",
        launcher.exists() and hamster_ok and "hamster_hidden.vbs" not in text,
        f"{hamster_evidence}; uses_vbs={'hamster_hidden.vbs' in text}",
        "햄스터는 설치 workspace의 agent_ops\\ui\\hamster_overlay.py를 직접 실행해야 합니다.",
    )

    project_required = [
        "if not defined LIG_PROJECT_DIR (",
        "set \"LIG_PROJECT_DIR=%CD%\"",
        "%WINDIR%\\System32",
        "%WINDIR%\\SysWOW64",
        "cd /d \"%LIG_PROJECT_DIR%\"",
    ]
    project_ok, project_evidence = _markers(text, project_required)
    unconditional_workspace = 'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"' in text.splitlines()
    _add(
        checks,
        "launcher_ocd_project_dir",
        launcher.exists() and project_ok and not unconditional_workspace,
        f"{project_evidence}; unconditional_workspace={unconditional_workspace}",
        "ocd/caller가 넘긴 작업폴더를 보존하고 위험한 시작 위치만 workspace로 fallback해야 합니다.",
    )


def _check_plugins_and_memory(workspace: Path, checks: list[GateCheck]) -> None:
    plugins = workspace / ".opencode" / "plugins"
    required_files = [
        "command-guard.ts",
        "compaction-handoff.ts",
        "hamster-status.ts",
        "memory-inject.ts",
        "session-autosave.ts",
    ]
    missing = [name for name in required_files if not (plugins / name).exists()]
    launcher = _read_text(workspace / "RUN_OPENCODE_LIG.bat")
    sync_all_plugins = ".opencode\\plugins\\*.ts" in launcher
    pure_one = "OPENCODE_PURE=1" in launcher
    _add(
        checks,
        "plugin_runtime_enabled",
        not missing and sync_all_plugins and not pure_one,
        f"missing={missing}; sync_all={sync_all_plugins}; pure1={pure_one}",
        "필수 플러그인을 유지하고 작업폴더로 동기화하며 OPENCODE_PURE=1을 쓰지 마세요.",
    )

    autosave = _read_text(plugins / "session-autosave.ts")
    autosave_required = [
        "memory\", \"wiki\", \"sessions\"",
        "appendFileSync(sessionFile()",
        "Object.entries(value)",
        "log-activity",
        "session.status",
        "session.next.step.ended",
        "session.next.step.failed",
        "bufferEventText",
        "takeBufferedText",
        "session.next.text.delta",
        "token",
        "secret",
        "credential",
    ]
    autosave_ok, autosave_evidence = _markers(autosave, autosave_required)
    _add(
        checks,
        "session_autosave_to_wiki",
        autosave_ok and "(?i:" not in autosave and "execFileSync" not in autosave,
        f"{autosave_evidence}; bad_regex={'(?i:' in autosave}; execFileSync={'execFileSync' in autosave}",
        "세션 이벤트를 wiki\\sessions로 저장하되 delta는 버퍼링 후 ended에서만 flush하고 동기 child 호출은 제거해야 합니다.",
    )

    memory = _read_text(plugins / "memory-inject.ts")
    memory_required = [
        "fallbackStartupBlock",
        "refreshStartupRecallAsync",
        "setTimeout",
        "process.env.LIG_AGENTOPS_HOME",
        "session.status",
        "STARTUP_REFRESH_COOLDOWN_MS",
        "COMPACTION_REFRESH_COOLDOWN_MS",
        "IDLE_REFRESH_COOLDOWN_MS",
        "cachedRecallBlock",
    ]
    memory_ok, memory_evidence = _markers(memory, memory_required)
    _add(
        checks,
        "memory_inject_nonblocking",
        memory_ok and "execFileSync" not in memory and ("execFile(" in memory or "spawn(" in memory),
        f"{memory_evidence}; execFileSync={'execFileSync' in memory}; async_exec={'execFile(' in memory or 'spawn(' in memory}",
        "TUI 시작을 막지 않도록 기억 주입은 fallback 후 백그라운드 refresh 구조여야 하며 동기 child 호출이 남아 있으면 안 됩니다.",
    )

    hamster = _read_text(plugins / "hamster-status.ts")
    hamster_required = [
        "task.start",
        "task.end",
        "subagent",
        "agent_name",
        "OpenCode subagent",
        "opencode-event-types.log",
        "isSubagentOrTaskStart",
        "isSubagentOrTaskEnd",
    ]
    hamster_ok, hamster_evidence = _markers(hamster, hamster_required)
    _add(
        checks,
        "hamster_subagent_status_bridge",
        hamster_ok,
        hamster_evidence,
        "멀티에이전트/subtask 진행 상태가 햄스터 current_status.json으로 자동 반영되어야 합니다.",
    )

    agentops = _read_text(workspace / "agent_ops" / "agentops.py")
    tool_dispatch = _read_text(workspace / "agent_ops" / "tool_dispatch.py")
    self_improvement = _read_text(workspace / "agent_ops" / "self_improvement.py")
    self_required = [
        "DEFAULT_SETTINGS",
        "\"enabled\": True",
        "capture_task_result",
        "format_injection_block",
        "lessons_for_injection",
        "self-improve",
    ]
    self_text = "\n".join([self_improvement, agentops, tool_dispatch])
    self_ok, self_evidence = _markers(self_text, self_required)
    _add(
        checks,
        "self_improvement_auto_loop",
        self_ok,
        self_evidence,
        "자가개선은 기본 ON이며 실패→성공→교훈→다음 세션 주입이 자동 연결되어야 합니다.",
    )


def _check_wiki_obsidian(workspace: Path, checks: list[GateCheck]) -> None:
    launcher = _read_text(workspace / "RUN_OPENCODE_LIG.bat")
    obsidian_required = [
        "agent_ops.wiki_vault",
        "LIG_AUTO_WIKI",
        "obsidian_detached.vbs",
        "%OPENCODE_USERDATA%\\memory\\wiki",
    ]
    obsidian_ok, obsidian_evidence = _markers(launcher, obsidian_required)
    direct_console = 'start "" "%OBSEXE%"' in launcher
    _add(
        checks,
        "obsidian_wiki_autostart",
        obsidian_ok and not direct_console,
        f"{obsidian_evidence}; direct_console={direct_console}",
        "Obsidian은 자동 실행하되 detached VBS로 분리해 TUI에 Electron 로그가 섞이지 않아야 합니다.",
    )

    code = (
        "from agent_ops.memory_manager import add_user_memory\n"
        "from agent_ops.wiki_manager import consolidate, WIKI_DIR\n"
        "item=add_user_memory('quality gate wiki smoke', title='quality gate')\n"
        "stats=consolidate()\n"
        "print(str(WIKI_DIR)); print(stats.get('records', 0))\n"
    )
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="opencodelig_quality_gate_memory_") as td:
        env["AGENTOPS_MEMORY_DIR"] = td
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        cp = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(workspace),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )
    _add(
        checks,
        "wiki_manager_smoke",
        cp.returncode == 0,
        f"rc={cp.returncode}; out={(cp.stdout or '')[-400:]}; err={(cp.stderr or '')[-400:]}",
        "격리 메모리에서 remember→wiki consolidate가 실패하면 memory_manager/wiki_manager 경로를 확인하세요.",
    )


def _section(lines: list[str], start: str, end: str) -> str:
    try:
        i = lines.index(start)
        j = lines.index(end)
    except ValueError:
        return ""
    if j <= i:
        return ""
    return "".join(lines[i + 1:j])


def _check_package(workspace: Path, checks: list[GateCheck]) -> None:
    repo = workspace.parent
    final_bat = repo / "최종_패치파일.bat"
    hotfix = workspace / "patches" / "existing_install_hotfix_20260709.py"
    hotfix_text = _read_text(hotfix)
    _add(
        checks,
        "hotfix_recreates_quality_gate",
        "QUALITY_GATE_SOURCE" in hotfix_text and "create_quality_gate" in hotfix_text and "quality_gate.py" in hotfix_text,
        f"QUALITY_GATE_SOURCE={'QUALITY_GATE_SOURCE' in hotfix_text}; create_quality_gate={'create_quality_gate' in hotfix_text}",
        "기존 설치본에 quality_gate.py가 없어도 최종 패치가 복구해야 합니다.",
    )

    lines = final_bat.read_text(encoding="utf-8", errors="replace").splitlines() if final_bat.exists() else []
    py64 = _section(lines, "__OPENCODELIG_HOTFIX_PY_BASE64__", "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__")
    wheel_name = _section(lines, "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__", "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__").strip()
    wheel64 = _section(lines, "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__", "__OPENCODELIG_HOTFIX_END__")
    payload_ok = False
    wheel_ok = False
    detail = []
    try:
        payload = base64.b64decode(py64)
        payload_ok = b"QUALITY_GATE_SOURCE" in payload and b"create_quality_gate" in payload
        detail.append(f"payload_bytes={len(payload)}")
    except Exception as exc:
        detail.append(f"payload_error={type(exc).__name__}:{exc}")
    try:
        data = base64.b64decode(wheel64)
        with tempfile.TemporaryDirectory(prefix="opencodelig_quality_gate_wheel_") as td:
            wh = Path(td) / wheel_name
            wh.write_bytes(data)
            with zipfile.ZipFile(wh) as zf:
                wheel_ok = any(name.endswith("/METADATA") and name.startswith("mss-") for name in zf.namelist())
        detail.append(f"wheel={wheel_name}")
    except Exception as exc:
        detail.append(f"wheel_error={type(exc).__name__}:{exc}")
    _add(
        checks,
        "final_patch_self_contained",
        final_bat.exists() and _crlf_only(final_bat) and payload_ok and wheel_ok,
        f"path={final_bat}; crlf={_crlf_only(final_bat)}; payload_ok={payload_ok}; wheel_ok={wheel_ok}; {'; '.join(detail)}",
        "최종 BAT는 최신 hotfix payload와 mss wheel을 자체 포함해야 합니다.",
    )


def _run_command_checks(workspace: Path, checks: list[GateCheck]) -> None:
    commands = [
        [sys.executable, "-m", "pytest", str(workspace / "tests" / "test_existing_install_hotfix.py"), str(workspace / "tests" / "test_opencode_lig_plugin_runtime.py"), "-q"],
        [sys.executable, "-m", "py_compile", str(workspace / "agent_ops" / "quality_gate.py"), str(workspace / "patches" / "existing_install_hotfix_20260709.py"), str(workspace / "agent_ops" / "pending_check.py")],
    ]
    for index, cmd in enumerate(commands, start=1):
        cp = subprocess.run(
            cmd,
            cwd=str(workspace.parent),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=180,
        )
        _add(
            checks,
            f"command_regression_{index}",
            cp.returncode == 0,
            f"cmd={' '.join(cmd)}; rc={cp.returncode}; out={(cp.stdout or '')[-500:]}; err={(cp.stderr or '')[-500:]}",
            "회귀 명령 실패 내용을 확인하고 해당 계약을 먼저 복구하세요.",
        )


def run_quality_gate(workspace: Path | str | None = None, run_commands: bool = True, out: Path | str | None = None) -> GateResult:
    ws = Path(workspace) if workspace else Path(__file__).resolve().parents[1]
    ws = ws.resolve()
    checks: list[GateCheck] = []
    _check_launcher(ws, checks)
    _check_plugins_and_memory(ws, checks)
    _check_wiki_obsidian(ws, checks)
    _check_package(ws, checks)
    if run_commands:
        _run_command_checks(ws, checks)

    report_path: Path | None = None
    result = GateResult(checks=checks, report_path=None)
    if out:
        report_path = Path(out)
    else:
        report_path = ws / "agent_ops" / "results" / "quality_gate" / "QUALITY_GATE_LAST.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(result.to_markdown(), encoding="utf-8")
    result.report_path = report_path
    report_path.write_text(result.to_markdown(), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenCodeLIG release quality gate")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--no-commands", action="store_true", help="skip heavier pytest/compile command checks")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    result = run_quality_gate(
        Path(args.workspace),
        run_commands=not args.no_commands,
        out=Path(args.out) if args.out else None,
    )
    print(result.to_markdown())
    if result.report_path:
        print(f"Report: {result.report_path}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
