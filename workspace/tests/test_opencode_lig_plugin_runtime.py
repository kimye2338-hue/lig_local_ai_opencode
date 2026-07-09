# -*- coding: utf-8 -*-
"""Regression checks for OpenCodeLIG's automatic plugin bridges.

These are static/runtime-contract checks for the parts that make the user-facing
"just use it" behavior work: hamster status, Obsidian autosave, memory injection,
command guard, and pending diagnostics.
"""
from __future__ import annotations

from pathlib import Path

WS = Path(__file__).resolve().parents[1]
REPO = WS.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_launcher_keeps_opencode_lig_plugins_loadable_and_crlf() -> None:
    launcher = WS / "RUN_OPENCODE_LIG.bat"
    raw = launcher.read_bytes()
    text = raw.decode("utf-8", errors="replace")

    assert b"\n" not in raw.replace(b"\r\n", b""), "RUN_OPENCODE_LIG.bat must be CRLF-only"
    assert "OPENCODE_PURE=1" not in text
    assert "set \"OPENCODE_PURE=\"" in text
    assert "--pure" not in text.lower()
    assert "OPENCODE_DISABLE_DEFAULT_PLUGINS=1" in text
    assert "LIG_AGENTOPS_HOME=%AGENTOPS_HOME%" in text


def test_launcher_uses_fast_runtime_and_blocks_external_startup_waits() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")
    run_idx = text.index("\"%OCODE_EXE%\" %*")

    for marker in [
        "set \"OPENCODE_FAST_BASE=%OPENCODE_USERDATA%\\opencode_fast_runtime\"",
        "set \"OPENCODE_FAST_CONFIG=%OPENCODE_FAST_BASE%\\config\"",
        "set \"OPENCODE_FAST_DATA=%OPENCODE_FAST_BASE%\\data\"",
        "set \"OPENCODE_FAST_CACHE=%OPENCODE_FAST_BASE%\\cache\"",
        "set \"OPENCODE_CONFIG_DIR=%OPENCODE_FAST_CONFIG%\"",
        "set \"XDG_CONFIG_HOME=%OPENCODE_FAST_CONFIG%\"",
        "set \"XDG_DATA_HOME=%OPENCODE_FAST_DATA%\"",
        "set \"XDG_CACHE_HOME=%OPENCODE_FAST_CACHE%\"",
        "set \"OPENCODE_CONFIG=%AGENTOPS_HOME%\\opencode.json\"",
        "set \"OPENCODE_PURE=\"",
        "set \"OPENCODE_DISABLE_MODELS_FETCH=1\"",
        "set \"OPENCODE_DISABLE_AUTOUPDATE=1\"",
        "set \"OPENCODE_DISABLE_LSP_DOWNLOAD=1\"",
        "set \"OPENCODE_MODELS_URL=http://127.0.0.1:9/api.json\"",
        "set \"NPM_CONFIG_REGISTRY=http://127.0.0.1:9/\"",
        "set \"NPM_CONFIG_FETCH_TIMEOUT=1000\"",
        "set \"NPM_CONFIG_FETCH_RETRIES=0\"",
        "set \"BUN_CONFIG_REGISTRY=http://127.0.0.1:9/\"",
        "set \"BUN_INSTALL_CACHE_DIR=%OPENCODE_FAST_CACHE%\\bun\"",
        "set \"NO_PROXY=*\"",
        "set \"HTTP_PROXY=\"",
        "set \"HTTPS_PROXY=\"",
        "set \"ALL_PROXY=\"",
    ]:
        assert marker in text
        assert text.index(marker) < run_idx
    assert "set \"OPENCODE_PURE=1\"" not in text


def test_launcher_preserves_project_dir_and_only_falls_back_for_unsafe_starts() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    assert "if not defined LIG_PROJECT_DIR (\n  set \"LIG_PROJECT_DIR=%CD%\"\n)" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%USERPROFILE%\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%WINDIR%\\System32\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert "if /I \"%LIG_PROJECT_DIR%\"==\"%WINDIR%\\SysWOW64\" set \"LIG_PROJECT_DIR=%AGENTOPS_HOME%\"" in text
    assert 'set "LIG_PROJECT_DIR=%AGENTOPS_HOME%"' not in text.splitlines()


def test_launcher_starts_hamster_directly_from_real_ui_path() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    assert "hamster_hidden.vbs" not in text
    assert "set \"LIG_WORKSPACE_HOME=%USERPROFILE%\\OpenCodeLIG\\workspace\"" in text
    assert "agent_ops\\ui\\hamster_overlay.py" in text
    assert "hamster_overlay_start.log" in text
    assert "set \"LIG_AGENTOPS_HOME=%LIG_WORKSPACE_HOME%\"" in text
    assert "set \"PYTHONPATH=%LIG_WORKSPACE_HOME%;%PYTHONPATH%\"" in text
    assert "start \"OpenCodeLIG Hamster\" /MIN /D \"%LIG_WORKSPACE_HOME%\" py -3.11 \"%HAMSTER_PY%\"" in text
    assert "start \"OpenCodeLIG Hamster\" /MIN /D \"%LIG_WORKSPACE_HOME%\" python \"%HAMSTER_PY%\"" in text


def test_ocd_wrapper_passes_current_folder_when_no_argument() -> None:
    bat = read(WS / "launch" / "ocd.bat")
    ocd = read(WS / "agent_ops" / "ocd.py")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    assert "if \"%~1\"==\"\" (" in bat
    assert "if not defined LIG_PROJECT_DIR set \"LIG_PROJECT_DIR=%CD%\"" in bat
    assert "env.setdefault(\"LIG_PROJECT_DIR\", str(cwd))" in ocd
    assert "if not defined LIG_PROJECT_DIR set \\\"LIG_PROJECT_DIR=%CD%\\\"" in hotfix


def test_launcher_refreshes_all_required_project_plugins() -> None:
    text = read(WS / "RUN_OPENCODE_LIG.bat")

    for plugin in [
        "session-autosave.ts",
        "memory-inject.ts",
        "command-guard.ts",
        "hamster-status.ts",
        "compaction-handoff.ts",
    ]:
        assert plugin in text
    assert ".opencode\\plugins\\*.ts" in text
    assert "copy /Y" in text


def test_hamster_status_plugin_tracks_current_opencode_events() -> None:
    text = read(WS / ".opencode" / "plugins" / "hamster-status.ts")

    for marker in [
        "session.status",
        "session.next.text.delta",
        "session.next.step.started",
        "session.next.step.ended",
        "session.next.step.failed",
        "session.next.tool.called",
        "session.next.tool.success",
        "session.next.tool.failed",
        "experimental.session.compacting",
        'properties?.tool === "task"',
    ]:
        assert marker in text
    for marker in [
        "task.start",
        "task.end",
        "session.task.",
        "session.next.task.",
        "agent_name",
        "body.includes(\"subagent\")",
        "body.includes(\"agent_name\")",
    ]:
        assert marker not in text
    assert "properties?.status?.type" in text or "properties.status.type" in text
    assert "writeAtomic" in text
    assert "opencode-event-types.log" in text


def test_session_autosave_extracts_current_event_properties() -> None:
    text = read(WS / ".opencode" / "plugins" / "session-autosave.ts")

    for marker in [
        '"properties"',
        '"delta"',
        '"input"',
        '"output"',
        "session.status",
        "session.next.step.ended",
        "session.next.step.failed",
    ]:
        assert marker in text
    assert "for (const [key, child] of Object.entries(value))" in text
    assert "rememberSessionActivity(base, shouldFlush" in text
    assert "execFileSync" not in text
    assert "session.next.text.delta" in text
    assert "bufferEventText" in text
    assert "token" in text
    assert "secret" in text
    assert "credential" in text


def test_memory_and_handoff_use_installed_agentops_home() -> None:
    memory = read(WS / ".opencode" / "plugins" / "memory-inject.ts")
    handoff = read(WS / ".opencode" / "plugins" / "compaction-handoff.ts")

    assert "process.env.LIG_AGENTOPS_HOME" in memory
    assert "process.env.LIG_AGENTOPS_HOME" in handoff
    assert "session.status" in memory
    assert "execFileSync" not in memory
    assert "execFile(" in memory or "spawn(" in memory
    assert "STARTUP_REFRESH_COOLDOWN_MS" in memory
    assert "COMPACTION_REFRESH_COOLDOWN_MS" in memory
    assert "try {" in handoff
    assert "} catch {" in handoff


def test_pending_check_flags_plugin_runtime_not_just_file_presence() -> None:
    text = read(WS / "agent_ops" / "pending_check.py")

    assert "OpenCode plugin runtime enabled" in text
    assert "OPENCODE_PURE" in text
    assert "OpenCode fast runtime isolation" in text
    assert "direct hamster launcher" in text
    assert "hamster-status.ts" in text
    assert "session-autosave.ts" in text


def test_existing_install_hotfix_contains_same_bridge_repairs() -> None:
    text = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    for marker in [
        "HAMSTER_STATUS_PLUGIN",
        "MEMORY_INJECT_PLUGIN",
        "COMPACTION_HANDOFF_PLUGIN",
        "OPENCODE_PURE",
        ".opencode\\plugins\\*.ts",
        "session.next.text.delta",
        "session.status",
    ]:
        assert marker in text


def test_litellm_remote_cost_map_fetch_is_disabled_offline() -> None:
    launcher = read(WS / "RUN_OPENCODE_LIG.bat")
    agentops = read(WS / "agent_ops" / "agentops.py")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    for text in [launcher, agentops, hotfix]:
        assert "LITELLM_LOCAL_MODEL_COST_MAP" in text
    assert 'set "LITELLM_LOCAL_MODEL_COST_MAP=True"' in launcher
    assert 'os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")' in agentops
    assert "LiteLLM offline" in hotfix


def test_slow_startup_does_not_kill_hamster_or_block_tui() -> None:
    hamster = read(WS / "agent_ops" / "ui" / "hamster_overlay.py")
    launcher = read(WS / "RUN_OPENCODE_LIG.bat")
    memory = read(WS / ".opencode" / "plugins" / "memory-inject.ts")
    hotfix = read(WS / "patches" / "existing_install_hotfix_20260709.py")

    assert "LIG_HAMSTER_START_GRACE_SECONDS" in hamster
    assert "START_GRACE_SECONDS" in hamster
    assert "> START_GRACE_SECONDS" in hamster
    assert 'set "LIG_HAMSTER_START_GRACE_SECONDS=300"' in launcher
    assert "setTimeout" in memory
    assert "refreshStartupRecallAsync" in memory
    assert "patch_hamster_start_grace" in hotfix
    assert "hamster_launcher.log" in hotfix
