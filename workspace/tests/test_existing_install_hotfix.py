# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import base64
import py_compile
import shutil
import subprocess
import sys
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


def _run_hotfix(root: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["OPENCODELIG_ROOT"] = str(root)
    env["USERPROFILE"] = str(tmp_path)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX"] = "1"
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
    marker = "__OPENCODELIG_HOTFIX_PAYLOAD_BASE64__"
    lines = text.splitlines()
    assert marker in lines
    payload = "".join(lines[lines.index(marker) + 1 :])
    assert len(payload) > 1000
    extracted = tmp_path / "embedded_hotfix.py"
    extracted.write_bytes(base64.b64decode(payload))
    py_compile.compile(str(extracted), doraise=True)


def test_hotfix_preserves_user_working_directory_and_detaches_obsidian(tmp_path: Path) -> None:
    root = _copy_min_install(tmp_path)

    result = _run_hotfix(root, tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    launcher = root / "workspace" / "RUN_OPENCODE_LIG.bat"
    text = launcher.read_text(encoding="utf-8")
    assert 'set "LIG_PROJECT_DIR=%CD%"' in text
    assert 'set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"' in text
    assert 'set "AGENTOPS_MEMORY_DIR=%OPENCODE_USERDATA%\\memory"' in text
    assert 'cd /d "%LIG_PROJECT_DIR%"' in text
    assert "project_agentops_wrapper.py" in text
    assert "obsidian_detached.vbs" in text
    assert 'start "" "%OBSEXE%"' not in text

    assert (root / "workspace" / "launch" / "obsidian_detached.vbs").exists()
    assert (root / "workspace" / "launch" / "project_agentops_wrapper.py").exists()
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
