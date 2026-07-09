# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import base64
import py_compile
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


WS = Path(__file__).resolve().parents[1]
REPO = WS.parent
HOTFIX = WS / "patches" / "existing_install_hotfix_20260709.py"
PATCH_BAT = REPO / "PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt"
FINAL_BAT = REPO / "최종_패치파일.bat"


def _copy_min_install(tmp_path: Path) -> Path:
    root = tmp_path / "OpenCodeLIG"
    install_ws = root / "workspace"
    shutil.copytree(
        WS,
        install_ws,
        ignore=shutil.ignore_patterns(
            "tests",
            "__pycache__",
            ".pytest_cache",
            "agent_ops/results",
            "docs/archive",
        ),
    )
    (root / "bin").mkdir(parents=True, exist_ok=True)
    return root


def _run_hotfix(root: Path, tmp_path: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["OPENCODELIG_ROOT"] = str(root)
    env["USERPROFILE"] = str(tmp_path)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(HOTFIX)],
        cwd=str(REPO),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )


def test_existing_install_hotfix_compiles() -> None:
    py_compile.compile(str(HOTFIX), doraise=True)


def test_patch_entry_bat_is_utf8_crlf_and_sets_codepage() -> None:
    raw = PATCH_BAT.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8")
    assert "chcp 65001" in text


def test_final_patch_bat_is_self_contained_and_embeds_compilable_payload(tmp_path: Path) -> None:
    raw = FINAL_BAT.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    text = raw.decode("utf-8")
    py_marker = "__OPENCODELIG_HOTFIX_PY_BASE64__"
    wheel_name_marker = "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__"
    wheel_marker = "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__"
    end_marker = "__OPENCODELIG_HOTFIX_END__"
    lines = text.splitlines()
    assert py_marker in lines
    assert wheel_name_marker in lines
    assert wheel_marker in lines
    assert end_marker in lines

    def section(start: str, end: str) -> str:
        return "".join(lines[lines.index(start) + 1 : lines.index(end)])

    payload = section(py_marker, wheel_name_marker)
    extracted = tmp_path / "embedded_hotfix.py"
    extracted.write_bytes(base64.b64decode(payload))
    py_compile.compile(str(extracted), doraise=True)

    wheel_name = section(wheel_name_marker, wheel_marker).strip()
    assert wheel_name.startswith("mss-")
    assert wheel_name.endswith(".whl")
    wheel_path = tmp_path / wheel_name
    wheel_path.write_bytes(base64.b64decode(section(wheel_marker, end_marker)))
    with zipfile.ZipFile(wheel_path) as zf:
        names = zf.namelist()
    assert any(name.endswith("/METADATA") and name.startswith("mss-") for name in names)


def test_final_patch_bat_extracts_and_runs_against_min_install(tmp_path: Path) -> None:
    root = _copy_min_install(tmp_path)
    fake_lib = tmp_path / "fake_lib"
    fake_lib.mkdir()
    (fake_lib / "mss.py").write_text("# fake existing mss for hotfix skip test\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k.upper() != "NODEFAULTCURRENTDIRECTORYINEXEPATH"}
    env["OPENCODELIG_ROOT"] = str(root)
    env["USERPROFILE"] = str(tmp_path)
    env["LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(fake_lib)

    result = subprocess.run(
        f'cmd /c call "{FINAL_BAT}" <nul',
        cwd=str(REPO),
        env=env,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Failed to extract embedded hotfix payload" not in result.stdout + result.stderr
    assert "Existing install hotfix complete" in result.stdout
    assert (root / "bin" / "ocd.bat").exists()


def test_hotfix_preserves_user_working_directory_and_detaches_obsidian(tmp_path: Path) -> None:
    root = _copy_min_install(tmp_path)
    autocad_adapter = root / "workspace" / "agent_ops" / "adapters" / "autocad_batch.py"
    autocad_adapter.write_text(
        "# -*- coding: utf-8 -*-\n"
        "def find_accoreconsole():\n"
        "    return ''\n",
        encoding="utf-8",
    )

    result = _run_hotfix(root, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    launcher = root / "workspace" / "RUN_OPENCODE_LIG.bat"
    text = launcher.read_text(encoding="utf-8")
    assert 'set "LIG_PROJECT_DIR=%CD%"' in text
    assert 'set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"' in text
    assert 'set "AGENTOPS_MEMORY_DIR=%OPENCODE_USERDATA%\\memory"' in text
    assert 'cd /d "%LIG_PROJECT_DIR%"' in text
    assert "project_agentops_wrapper.py" in text
    assert "session-autosave.ts" in text
    assert "obsidian_detached.vbs" in text
    assert 'start "" "%OBSEXE%"' not in text

    assert (root / "workspace" / "launch" / "obsidian_detached.vbs").exists()
    assert (root / "workspace" / "launch" / "project_agentops_wrapper.py").exists()
    assert (root / "workspace" / ".opencode" / "plugins" / "session-autosave.ts").exists()
    patched_autocad = autocad_adapter.read_text(encoding="utf-8")
    assert "def find_acad" in patched_autocad
    assert "LIGNEX1" in patched_autocad
    assert "ACADM" in patched_autocad
    assert (root / "bin" / "ocd.bat").exists()
    assert "agent_ops\\ocd.py" in (root / "bin" / "ocd.bat").read_text(encoding="utf-8")
    assert (root / "bin" / "probe-gateway.bat").exists()
    assert (root / "점검용_전체확인.bat").exists()

    for bat in [
        root / "bin" / "ocd.bat",
        root / "bin" / "probe-gateway.bat",
        root / "점검용_전체확인.bat",
    ]:
        raw = bat.read_bytes()
        assert b"\n" not in raw.replace(b"\r\n", b""), str(bat)


def test_hotfix_replaces_legacy_launcher_without_wiki_block(tmp_path: Path) -> None:
    root = _copy_min_install(tmp_path)
    launcher = root / "workspace" / "RUN_OPENCODE_LIG.bat"
    launcher.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "setlocal EnableExtensions\r\n"
        "for %%I in (\"%~dp0.\") do set \"AGENTOPS_HOME=%%~fI\"\r\n"
        "for %%I in (\"%AGENTOPS_HOME%\\..\") do set \"OC_ROOT=%%~fI\"\r\n"
        "set \"OPENCODE_USERDATA=%OC_ROOT%\\userdata\"\r\n"
        "set \"OPENCODE_PURE=1\"\r\n"
        "cd /d \"%AGENTOPS_HOME%\"\r\n"
        "\"%OC_ROOT%\\bin\\opencode.exe\" %*\r\n",
        encoding="utf-8",
        newline="",
    )

    result = _run_hotfix(root, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    text = launcher.read_text(encoding="utf-8")
    assert "OPENCODE_PURE=1" not in text
    assert "%OC_ROOT%\\userdata" not in text
    assert "%USERPROFILE%\\OpenCodeLIG_USERDATA" in text
    assert "obsidian_detached.vbs" in text
    assert "LIG_HAMSTER_START_GRACE_SECONDS=300" in text
    assert ".opencode\\plugins\\*.ts" in text
    assert "probe_gateway.py" not in text.lower()
    assert "launch\\probe-gateway.bat" not in text.lower()
    raw = launcher.read_bytes()
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_hotfix_skips_current_files_and_existing_mss(tmp_path: Path) -> None:
    root = _copy_min_install(tmp_path)
    fake_lib = tmp_path / "fake_lib"
    fake_lib.mkdir()
    (fake_lib / "mss.py").write_text("# fake existing mss for hotfix skip test\n", encoding="utf-8")
    env = {"PYTHONPATH": str(fake_lib)}

    first = _run_hotfix(root, tmp_path, env)
    assert first.returncode == 0, first.stdout + first.stderr
    second = _run_hotfix(root, tmp_path, env)

    assert second.returncode == 0, second.stdout + second.stderr
    combined = second.stdout + second.stderr
    assert "mss already importable" in combined
    assert "root check BAT already current" in combined
    assert "command wrapper already current" in combined
    assert "ocd wrapper already current" in combined
    assert "AutoCAD adapter already current" in combined


def test_session_autosave_plugin_writes_to_obsidian_sessions(tmp_path: Path) -> None:
    plugin = WS / ".opencode" / "plugins" / "session-autosave.ts"
    text = plugin.read_text(encoding="utf-8")
    assert "memory\", \"wiki\", \"sessions\"" in text
    assert "appendFileSync(sessionFile()" in text
    assert "log-activity" in text
    assert "rememberSessionActivity" in text
    assert "session.start" in text
    assert "(?i:" not in text
