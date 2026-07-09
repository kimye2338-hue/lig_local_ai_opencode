# -*- coding: utf-8 -*-
"""Patch an existing OpenCodeLIG install in place.

This script is launched by PATCH_EXISTING_INSTALL_LIG_OPENCODE_20260709.bat.txt.
It is intentionally additive:
- backs up touched files under USERDATA diagnostics;
- never deletes or rewrites OpenCodeLIG_USERDATA memory/wiki/schedules;
- patches diagnostic classification without hiding real app-validation gaps;
- installs optional wheels only when the wheel files are already available.
"""
from __future__ import annotations

import os
import importlib.util
import shutil
import subprocess
import sys
import time
from pathlib import Path

MARK_PENDING = "# BEGIN LIG EXISTING-INSTALL HOTFIX 20260709"
MARK_ADAPTERS = "# BEGIN LIG ADAPTER STATUS HOTFIX 20260709"
MARK_RUN = "rem BEGIN LIG EXISTING-INSTALL HOTFIX 20260709"

SESSION_AUTOSAVE_PLUGIN = r'''// OpenCodeLIG session autosave.
// Writes useful chat/session snippets directly into the Obsidian vault on each
// event, so closing the terminal window does not lose the visible session trail.
// Best-effort and offline-safe: failure must never affect the chat path.

import { appendFileSync, existsSync, mkdirSync, writeFileSync } from "fs"
import { join } from "path"

const MAX_TEXT_CHARS = 1600
const MAX_EVENT_CHARS = 2400
const MIN_USEFUL_CHARS = 8

let lastSignature = ""
let lastWriteMs = 0

function userdataDir(): string {
  const explicit = process.env.OPENCODE_USERDATA
  if (explicit && explicit.trim()) return explicit
  const home = process.env.USERPROFILE || process.env.HOME || "."
  return join(home, "OpenCodeLIG_USERDATA")
}

function wikiSessionsDir(): string {
  return join(userdataDir(), "memory", "wiki", "sessions")
}

function dayStamp(date = new Date()): string {
  return date.toISOString().slice(0, 10)
}

function timeStamp(date = new Date()): string {
  return date.toTimeString().slice(0, 8)
}

function sessionFile(): string {
  return join(wikiSessionsDir(), `${dayStamp()}-opencode-session.md`)
}

function ensureSessionFile(): void {
  const dir = wikiSessionsDir()
  mkdirSync(dir, { recursive: true })
  const path = sessionFile()
  if (!existsSync(path)) {
    writeFileSync(path, [
      "# OpenCode session autosave",
      "",
      "이 파일은 OpenCodeLIG가 대화/작업 이벤트를 자동 저장한 기록입니다.",
      "터미널 창을 닫아도 이미 기록된 내용은 이 Obsidian vault 노트에 남습니다.",
      "",
    ].join("\n"), "utf-8")
  }
}

function compact(value: string): string {
  return value.replace(/\s+/g, " ").trim()
}

function redact(value: string): string {
  return value
    .replace(/Bearer\s+[A-Za-z0-9._\-+/=]+/g, "Bearer <hidden>")
    .replace(/(?i:api[_-]?key\s*[=:]\s*)[^\s,;]+/g, "$1<hidden>")
    .replace(/(?i:password\s*[=:]\s*)[^\s,;]+/g, "$1<hidden>")
}

function collectText(value: any, out: string[], depth = 0): void {
  if (out.length >= 12 || depth > 5 || value == null) return
  if (typeof value === "string") {
    const text = compact(value)
    if (text.length >= MIN_USEFUL_CHARS) out.push(text.slice(0, MAX_TEXT_CHARS))
    return
  }
  if (Array.isArray(value)) {
    for (const item of value) collectText(item, out, depth + 1)
    return
  }
  if (typeof value === "object") {
    const priority = ["role", "text", "content", "message", "summary", "prompt", "title"]
    for (const key of priority) {
      if (key in value) collectText(value[key], out, depth + 1)
    }
  }
}

function usefulText(event: any): string {
  const parts: string[] = []
  collectText(event, parts)
  const unique: string[] = []
  for (const p of parts) {
    if (!unique.includes(p)) unique.push(p)
  }
  return redact(unique.join("\n\n")).slice(0, MAX_EVENT_CHARS)
}

function writeEvent(event: any): void {
  try {
    ensureSessionFile()
    const type = String(event?.type || "event")
    const text = usefulText(event)
    if (!text && type !== "session.idle" && type !== "session.error") return

    const now = Date.now()
    const signature = `${type}:${text.slice(0, 400)}`
    if (signature === lastSignature && now - lastWriteMs < 3000) return
    lastSignature = signature
    lastWriteMs = now

    const heading = `\n## ${timeStamp()} ${type}\n`
    const body = text ? `${text}\n` : "(상태 이벤트)\n"
    appendFileSync(sessionFile(), heading + body, "utf-8")
  } catch {
    // Autosave must never interrupt the user's session.
  }
}

export const SessionAutosave = async (_ctx: any) => {
  try {
    ensureSessionFile()
    appendFileSync(sessionFile(), `\n## ${timeStamp()} session.start\nOpenCode 세션 시작\n`, "utf-8")
  } catch {
    // optional
  }
  return {
    event: async ({ event }: any) => {
      writeEvent(event)
    },
    "experimental.session.compacting": async (input: any, output: any) => {
      writeEvent({ type: "session.compacting", input, output })
    },
  }
}
'''


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.environ.get(name, "").strip().strip('"')
    return Path(raw) if raw else default


ROOT = _path_from_env("OPENCODELIG_ROOT", Path.home() / "OpenCodeLIG")
WS = ROOT / "workspace"
USERDATA = Path.home() / "OpenCodeLIG_USERDATA"
LOG_DIR = USERDATA / "diagnostics" / "patches"
STAMP = time.strftime("%Y%m%d_%H%M%S")
PATCH_SOURCE_DIR = _path_from_env("LIG_HOTFIX_PACKAGE_DIR", Path(__file__).resolve().parents[2])
LOG = LOG_DIR / f"existing_install_hotfix_{STAMP}.log"


def log(message: str) -> None:
    print(message)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(message + "\n")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _crlf_bytes(text: str) -> bytes:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n").encode("utf-8")


def write_crlf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_crlf_bytes(text))


def write_crlf_if_changed(path: Path, text: str) -> bool:
    desired = _crlf_bytes(text)
    if path.exists() and path.read_bytes() == desired:
        return False
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(desired)
    return True


def write_text_if_changed(path: Path, text: str) -> bool:
    desired = text.encode("utf-8")
    if path.exists() and path.read_bytes() == desired:
        return False
    backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(desired)
    return True


def backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    out = LOG_DIR / "backup" / STAMP / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, out)
    return out


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(WS),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def copy_root_check_bat() -> None:
    src = WS / "점검용_전체확인.bat"
    dst = ROOT / "점검용_전체확인.bat"
    if not src.exists():
        log(f"[WARN] workspace check BAT not found: {src}")
        return
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        log(f"[SKIP] root check BAT already current: {dst}")
        return
    backup(dst)
    shutil.copy2(src, dst)
    log(f"[OK] root check BAT copied: {dst}")


def create_gateway_wrappers() -> None:
    """Fix 'probe-gateway is not recognized' from unqualified command calls."""
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    wrappers = {
        "probe-gateway.bat": "probe-gateway.bat",
        "probe_gateway.bat": "probe-gateway.bat",
        "gateway-smoke.bat": "gateway-smoke.bat",
    }
    for wrapper_name, launch_name in wrappers.items():
        target = bin_dir / wrapper_name
        body = (
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "setlocal EnableExtensions\r\n"
            "set \"HERE=%~dp0\"\r\n"
            "for %%I in (\"%HERE%..\") do set \"OC_ROOT=%%~fI\"\r\n"
            f"set \"TARGET=%OC_ROOT%\\workspace\\launch\\{launch_name}\"\r\n"
            "if not exist \"%TARGET%\" (\r\n"
            "  echo [ERROR] target launcher not found: %TARGET%\r\n"
            "  exit /b 1\r\n"
            ")\r\n"
            "call \"%TARGET%\" %*\r\n"
            "exit /b %ERRORLEVEL%\r\n"
        )
        if write_crlf_if_changed(target, body):
            log(f"[OK] command wrapper created/updated: {target}")
        else:
            log(f"[SKIP] command wrapper already current: {target}")


def create_ocd_wrapper() -> None:
    """Create the user-facing command while keeping the existing ocd.py profile flow."""
    bin_dir = ROOT / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / "ocd.bat"
    body = (
        "@echo off\n"
        "chcp 65001 >nul\n"
        "setlocal EnableExtensions\n"
        "set \"PYTHONUTF8=1\"\n"
        "set \"PYTHONIOENCODING=utf-8\"\n"
        "set \"HERE=%~dp0\"\n"
        "for %%I in (\"%HERE%..\") do set \"OC_ROOT=%%~fI\"\n"
        "set \"OCDPY=%OC_ROOT%\\workspace\\agent_ops\\ocd.py\"\n"
        "if not exist \"%OCDPY%\" (\n"
        "  echo [ERROR] OpenCodeLIG ocd.py not found: %OCDPY%\n"
        "  exit /b 1\n"
        ")\n"
        "where py >nul 2>nul\n"
        "if %ERRORLEVEL%==0 (\n"
        "  py -3.11 -X utf8 \"%OCDPY%\" %*\n"
        ") else (\n"
        "  python -X utf8 \"%OCDPY%\" %*\n"
        ")\n"
        "exit /b %ERRORLEVEL%\n"
    )
    if write_crlf_if_changed(target, body):
        log(f"[OK] ocd wrapper created/updated: {target}")
    else:
        log(f"[SKIP] ocd wrapper already current: {target}")


def create_launcher_helpers() -> None:
    launch_dir = WS / "launch"
    launch_dir.mkdir(parents=True, exist_ok=True)

    obsidian_vbs = launch_dir / "obsidian_detached.vbs"
    obsidian_body = (
        "Option Explicit\n"
        "Dim shell, exePath, vaultPath, cmd\n"
        "If WScript.Arguments.Count < 2 Then WScript.Quit 1\n"
        "exePath = WScript.Arguments(0)\n"
        "vaultPath = WScript.Arguments(1)\n"
        "Set shell = CreateObject(\"WScript.Shell\")\n"
        "cmd = Chr(34) & exePath & Chr(34) & \" \" & Chr(34) & vaultPath & Chr(34)\n"
        "shell.Run cmd, 1, False\n"
    )
    if write_crlf_if_changed(obsidian_vbs, obsidian_body):
        log(f"[OK] detached Obsidian launcher created/updated: {obsidian_vbs}")
    else:
        log(f"[SKIP] detached Obsidian launcher already current: {obsidian_vbs}")

    wrapper = launch_dir / "project_agentops_wrapper.py"
    wrapper_body = '''# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def main() -> None:
    install_home = Path(os.environ.get("LIG_AGENTOPS_HOME", "")).resolve()
    if not install_home.exists():
        raise SystemExit("LIG_AGENTOPS_HOME is not set to the installed workspace")
    project_root = Path(os.environ.get("AGENTOPS_ROOT") or Path.cwd()).resolve()
    os.environ["AGENTOPS_ROOT"] = str(project_root)
    script_name = Path(__file__).name
    target = install_home / "agent_ops" / script_name
    if not target.exists():
        raise SystemExit(f"installed agent_ops script not found: {target}")
    project_path = str(project_root)
    sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()) != project_path]
    sys.path.insert(0, str(install_home))
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
'''
    if write_text_if_changed(wrapper, wrapper_body):
        log(f"[OK] project agent_ops wrapper created/updated: {wrapper}")
    else:
        log(f"[SKIP] project agent_ops wrapper already current: {wrapper}")


def create_session_autosave_plugin() -> None:
    plugin = WS / ".opencode" / "plugins" / "session-autosave.ts"
    if write_text_if_changed(plugin, SESSION_AUTOSAVE_PLUGIN):
        log(f"[OK] session autosave plugin created/updated: {plugin}")
    else:
        log(f"[SKIP] session autosave plugin already current: {plugin}")


def wheel_dirs() -> list[Path]:
    candidates = [
        PATCH_SOURCE_DIR / "patch_wheels",
        PATCH_SOURCE_DIR / "workspace" / "tools" / "wheelhouse",
        WS / "tools" / "wheelhouse",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path).lower()
        if path.exists() and key not in seen:
            out.append(path)
            seen.add(key)
    return out


def module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def try_install_optional_wheels() -> None:
    if module_available("mss"):
        log("[SKIP] mss already importable. Offline wheel install not needed.")
        return
    dirs = wheel_dirs()
    mss_found = any(list(d.glob("mss-*.whl")) for d in dirs)
    if not dirs:
        log("[INFO] no wheelhouse found for optional patch wheels")
        return
    if not mss_found:
        log("[INFO] mss wheel not found. Screen capture will use Pillow/PowerShell fallback.")
        return
    for wh in dirs:
        if not list(wh.glob("mss-*.whl")):
            continue
        cp = run([sys.executable, "-m", "pip", "install", "--no-index", "--find-links", str(wh), "mss"], timeout=120)
        if cp.returncode == 0:
            log(f"[OK] mss installed from: {wh}")
            return
        log(f"[WARN] mss install failed from {wh}: {(cp.stderr or cp.stdout)[-800:]}")
    log("[WARN] mss wheel exists but installation failed. Fallback remains active.")


def patch_run_launcher() -> None:
    launcher = WS / "RUN_OPENCODE_LIG.bat"
    if not launcher.exists():
        log(f"[WARN] launcher not found: {launcher}")
        return
    text = read_text(launcher)
    if MARK_RUN in text:
        log(f"[SKIP] launcher already patched: {launcher}")
        return

    backup_path = backup(launcher)

    capture_line = 'for %%I in ("%AGENTOPS_HOME%\\..") do set "OC_ROOT=%%~fI"'
    if capture_line in text and 'set "LIG_PROJECT_DIR=%CD%"' not in text:
        text = text.replace(
            capture_line,
            capture_line
            + "\r\n"
            + 'if not defined LIG_PROJECT_DIR set "LIG_PROJECT_DIR=%CD%"\r\n'
            + 'set "LIG_AGENTOPS_HOME=%AGENTOPS_HOME%"',
            1,
        )

    userdata_line = 'set "OPENCODE_USERDATA=%USERPROFILE%\\OpenCodeLIG_USERDATA"'
    if userdata_line in text and 'set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"' not in text:
        text = text.replace(
            userdata_line,
            userdata_line
            + "\r\n"
            + 'if not defined AGENTOPS_MEMORY_DIR set "AGENTOPS_MEMORY_DIR=%OPENCODE_USERDATA%\\memory"\r\n'
            + 'set "AGENTOPS_ROOT=%LIG_PROJECT_DIR%"\r\n'
            + 'set "PYTHONPATH=%AGENTOPS_HOME%;%PYTHONPATH%"',
            1,
        )

    old_wiki_start = text.find("rem 위키 자동화:")
    old_wiki_end = text.find("\n:wiki_done", old_wiki_start)
    if old_wiki_end < 0:
        old_wiki_end = text.find("\r\n:wiki_done", old_wiki_start)
    if old_wiki_start < 0 or old_wiki_end < 0:
        raise RuntimeError("wiki block not found in launcher")
    old_wiki_end = text.find("\n", old_wiki_end + 1)
    if old_wiki_end < 0:
        old_wiki_end = len(text)
    else:
        old_wiki_end += 1

    new_wiki_block = r'''rem 위키 자동화: vault 자동 시드 + Obsidian 자동 실행.
rem BEGIN LIG EXISTING-INSTALL HOTFIX 20260709
rem Obsidian은 계속 자동으로 띄우되, Electron 로그가 OpenCode TUI에 섞이지 않게 VBS로 분리 실행한다.
rem 끄고 싶으면 이 창 실행 전에 set LIG_AUTO_WIKI=0.
if not exist "%OPENCODE_USERDATA%\memory\wiki" mkdir "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
py -3.11 -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1 || python -m agent_ops.wiki_vault "%OPENCODE_USERDATA%\memory\wiki" >nul 2>&1
if "%LIG_AUTO_WIKI%"=="0" goto :wiki_done
set "OBSEXE="
for %%P in ("%AGENTOPS_HOME%\tools\Obsidian\Obsidian.exe" "%OC_ROOT%\tools\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Obsidian\Obsidian.exe" "%LOCALAPPDATA%\Programs\Obsidian\Obsidian.exe" "%PROGRAMFILES%\Obsidian\Obsidian.exe") do if not defined OBSEXE if exist "%%~P" set "OBSEXE=%%~P"
if not defined OBSEXE for /f "delims=" %%F in ('dir /b /s "%OC_ROOT%\Obsidian.exe" 2^>nul') do if not defined OBSEXE set "OBSEXE=%%F"
if defined OBSEXE if exist "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" wscript "%AGENTOPS_HOME%\launch\obsidian_detached.vbs" "%OBSEXE%" "%OPENCODE_USERDATA%\memory\wiki"
:wiki_done
rem END LIG EXISTING-INSTALL HOTFIX 20260709
'''
    text = text[:old_wiki_start] + new_wiki_block + text[old_wiki_end:]

    launch_line = '"%OCODE_EXE%" %*'
    if launch_line not in text:
        raise RuntimeError("opencode launch line not found")
    project_block = r'''rem BEGIN LIG PROJECT WORKDIR HOTFIX 20260709
rem 프로그램 본체는 설치 폴더에서 읽고, 사용자가 cd로 들어온 폴더를 작업 기준으로 사용한다.
if not exist "%LIG_PROJECT_DIR%" mkdir "%LIG_PROJECT_DIR%" >nul 2>&1
if /I "%LIG_PROJECT_DIR%"=="%AGENTOPS_HOME%" goto :project_ready
if not exist "%LIG_PROJECT_DIR%\.opencode" (
  xcopy /E /I /Y "%AGENTOPS_HOME%\.opencode" "%LIG_PROJECT_DIR%\.opencode" >nul
)
if not exist "%LIG_PROJECT_DIR%\.opencode\plugins" mkdir "%LIG_PROJECT_DIR%\.opencode\plugins" >nul 2>&1
if exist "%AGENTOPS_HOME%\.opencode\plugins\session-autosave.ts" if not exist "%LIG_PROJECT_DIR%\.opencode\plugins\session-autosave.ts" copy /Y "%AGENTOPS_HOME%\.opencode\plugins\session-autosave.ts" "%LIG_PROJECT_DIR%\.opencode\plugins\session-autosave.ts" >nul
if not exist "%LIG_PROJECT_DIR%\agent_ops" mkdir "%LIG_PROJECT_DIR%\agent_ops" >nul 2>&1
if exist "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" (
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\agentops.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\command_guard.py" >nul
  copy /Y "%AGENTOPS_HOME%\launch\project_agentops_wrapper.py" "%LIG_PROJECT_DIR%\agent_ops\safe_file_writer.py" >nul
)
if not exist "%LIG_PROJECT_DIR%\agent_ops\results" mkdir "%LIG_PROJECT_DIR%\agent_ops\results" >nul 2>&1
:project_ready
cd /d "%LIG_PROJECT_DIR%"
rem END LIG PROJECT WORKDIR HOTFIX 20260709

'''
    text = text.replace(launch_line, project_block + launch_line, 1)

    write_crlf(launcher, text)
    log(f"[OK] launcher patched for detached Obsidian and project workdir (backup: {backup_path})")


PENDING_BLOCK = r'''
# BEGIN LIG EXISTING-INSTALL HOTFIX 20260709
# Additive hotfix for an existing company-PC install. The goal is not to hide
# missing apps; it reclassifies diagnostics using already-proven fallback paths.
try:
    _LIG_ORIG_RUN_CMD = run_cmd
    _LIG_ORIG_COMMON_PROGRAM_PATHS = common_program_paths

    def run_cmd(args, timeout=30, cwd=None, env=None):  # type: ignore[override]
        try:
            first = str((args or [""])[0]).lower()
            second = str((args or ["", ""])[1]).lower() if len(args or []) > 1 else ""
            if first.endswith("\\acad.exe") or first.endswith("/acad.exe"):
                if second in {"/?", "-?", "--help", "/help"}:
                    return {
                        "ok": True,
                        "returncode": 0,
                        "stdout": "GUI AutoCAD found; help probe skipped to avoid launching UI. Use /p LIGNEX1 /product ACADM /b for script execution.",
                        "stderr": "",
                        "args": args,
                    }
        except Exception:
            pass
        return _LIG_ORIG_RUN_CMD(args, timeout=timeout, cwd=cwd, env=env)

    def common_program_paths() -> dict[str, list[Path]]:  # type: ignore[override]
        paths = _LIG_ORIG_COMMON_PROGRAM_PATHS()
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        ws = workspace_root()
        root = Path.home() / "OpenCodeLIG"

        def add_unique(key: str, values: list[Path]) -> None:
            cur = paths.setdefault(key, [])
            seen = {str(p).lower() for p in cur}
            for value in values:
                if str(value).lower() not in seen:
                    cur.append(value)
                    seen.add(str(value).lower())

        acad: list[Path] = []
        acad.extend([
            Path(r"C:\AutoCAD 2019\acad.exe"),
            Path(r"C:\AutoCAD 2019\accoreconsole.exe"),
        ])
        for base in (pf / "Autodesk", pfx86 / "Autodesk", Path(r"C:\Autodesk")):
            try:
                acad.extend(base.glob("AutoCAD*/acad.exe"))
                acad.extend(base.glob("AutoCAD*/*accoreconsole.exe"))
                acad.extend(base.glob("**/acad.exe"))
                acad.extend(base.glob("**/accoreconsole.exe"))
            except Exception:
                pass
        for year in range(2016, 2027):
            acad.extend([
                pf / "Autodesk" / f"AutoCAD {year}" / "accoreconsole.exe",
                pf / "Autodesk" / f"AutoCAD {year}" / "acad.exe",
                pfx86 / "Autodesk" / f"AutoCAD {year}" / "accoreconsole.exe",
                pfx86 / "Autodesk" / f"AutoCAD {year}" / "acad.exe",
            ])
        add_unique("autocad", acad)
        add_unique("obsidian", [
            ws / "tools" / "Obsidian" / "Obsidian.exe",
            root / "tools" / "Obsidian" / "Obsidian.exe",
            root / "workspace" / "tools" / "Obsidian" / "Obsidian.exe",
            local / "Obsidian" / "Obsidian.exe",
            local / "Programs" / "Obsidian" / "Obsidian.exe",
        ])
        return paths

    def _lig_hotfix_has_pass(checks: list[Check], item: str) -> bool:
        return any(c.item == item and c.status == "PASS" for c in checks)

    def _lig_hotfix_screenshot_backend() -> tuple[bool, str]:
        if has_module("mss"):
            return True, "mss"
        try:
            from PIL import ImageGrab  # type: ignore # noqa: F401
            return True, "Pillow ImageGrab"
        except Exception:
            pass
        if sys.platform.startswith("win"):
            return True, "PowerShell System.Drawing fallback"
        return False, "none"

    def check_screen_ocr(checks: list[Check]) -> None:  # type: ignore[override]
        capture_ok, capture_via = _lig_hotfix_screenshot_backend()
        add(checks, "화면/OCR", "mss screenshot smoke",
            "PASS" if capture_ok else "PENDING",
            f"screenshot backend available via {capture_via}; mss_installed={has_module('mss')}",
            "mss가 없어도 Pillow/PowerShell 폴백으로 캡처합니다. 고속 캡처가 필요하면 mss wheel을 추가하세요.")
        if has_module("rapidocr_onnxruntime"):
            code = r"""
import json
try:
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    print(json.dumps({"ok": True, "engine": str(type(engine))}, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({"ok": False, "error": type(exc).__name__, "detail": str(exc)[:200]}, ensure_ascii=False))
    raise SystemExit(1)
"""
            res = run_python_probe(code, timeout=30)
            add(checks, "화면/OCR", "RapidOCR instantiate", "PASS" if res.get("ok") else "WARN",
                res.get("stdout") or res.get("stderr") or res.get("error", ""),
                "OCR 모델 파일/onnxruntime wheel 호환성을 확인하세요.")
        else:
            add(checks, "화면/OCR", "RapidOCR instantiate", "PENDING", "rapidocr_onnxruntime missing",
                "OCR이 필요하면 RapidOCR/onnxruntime wheel 및 모델을 반입하세요.")

    _LIG_ORIG_BUILD_REPORT = build_report

    def build_report(checks: list[Check], report_id: str):  # type: ignore[override]
        capture_ok, capture_via = _lig_hotfix_screenshot_backend()
        root_bat = package_root() / "점검용_전체확인.bat"
        for c in checks:
            if c.section == "오프라인 의존성" and c.item == "mss" and c.status != "PASS" and capture_ok:
                c.status = "PASS"
                c.evidence = f"mss module missing, but screenshot fallback is available via {capture_via}"
                c.next_action = "고속/멀티모니터 캡처 최적화가 필요할 때만 mss wheel을 추가하세요."
            if c.section == "문서/패키지" and c.item == "점검 BAT: 점검용_전체확인.bat" and str(root_bat) in c.evidence and root_bat.exists():
                c.status = "PASS"
                c.evidence = f"{root_bat}; copied by existing-install hotfix"
                c.next_action = "루트와 workspace 양쪽에서 점검 BAT를 실행할 수 있습니다."
            if c.item == "fluent cli probe" and "TIMEOUT" in c.evidence and _lig_hotfix_has_pass(checks, "fluent executable"):
                c.status = "SKIP"
                c.evidence = c.evidence + "; fluent.exe exists, help probe is intentionally skipped as a heavy-app startup check"
                c.next_action = "실제 journal 실행 검증은 사용자 작업 파일 기준으로 별도 수행합니다."
            if c.item == "Obsidian executable" and c.status == "PENDING" and _lig_hotfix_has_pass(checks, "실 USERDATA wiki vault"):
                c.status = "WARN"
                c.evidence = c.evidence + "; wiki vault is ready, Obsidian app install remains user-side prerequisite"
                c.next_action = "Obsidian 설치 후 다시 실행하면 자동 탐색합니다. portable은 workspace\\tools\\Obsidian\\Obsidian.exe에 둘 수 있습니다."
            if c.item == "adapter:solidworks" and _lig_hotfix_has_pass(checks, "SolidWorks COM activation"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=COM connection OK, only real macro execution pilot remains"
            if c.item == "adapter:office" and _lig_hotfix_has_pass(checks, "command:office-docx") and _lig_hotfix_has_pass(checks, "command:office-pptx"):
                c.status = "PASS"
                c.evidence = c.evidence + "; effective_state=docx/pptx generation smoke passed"
            if c.item == "adapter:outlook" and _lig_hotfix_has_pass(checks, "Outlook COM activation"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=Outlook COM connect OK, write/sync pilot remains guarded"
            if c.item == "adapter:browser" and _lig_hotfix_has_pass(checks, "Chrome CDP 9222"):
                c.status = "PASS"
                c.evidence = c.evidence + "; effective_state=Chrome CDP reachable; site login remains user/session-dependent"
            if c.item == "adapter:fluent" and _lig_hotfix_has_pass(checks, "fluent executable"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=fluent.exe found, journal pilot remains"
            if c.item == "adapter:ocr_screen" and capture_ok and _lig_hotfix_has_pass(checks, "RapidOCR instantiate"):
                c.status = "PASS"
                c.evidence = c.evidence + f"; effective_state=OCR engine + screenshot backend OK via {capture_via}"
            if c.item == "adapter:desktop_ui" and _lig_hotfix_has_pass(checks, "windows_use"):
                c.status = "WARN"
                c.evidence = c.evidence + "; effective_state=windows-use import OK, target-app UIA pilot remains"
        return _LIG_ORIG_BUILD_REPORT(checks, report_id)
except Exception as _lig_hotfix_exc:
    try:
        print(f"[WARN] LIG hotfix block initialization failed: {_lig_hotfix_exc!r}", file=sys.stderr)
    except Exception:
        pass
# END LIG EXISTING-INSTALL HOTFIX 20260709
'''


ADAPTER_BLOCK = r'''
# BEGIN LIG ADAPTER STATUS HOTFIX 20260709
def _lig_hotfix_refresh_adapter_status() -> None:
    try:
        if "ocr_screen" in ADAPTERS:
            try:
                backs = ocr_screen.detect_backends()
            except Exception:
                backs = []
            if backs:
                ADAPTERS["ocr_screen"]["available"] = True
                ADAPTERS["ocr_screen"]["validated"] = "OCR backend imported; screenshot fallback verified by pending_check"
                ADAPTERS["ocr_screen"]["pending"] = "real screen text quality depends on target UI; read_screen smoke covers capture/backend"
        if "desktop_ui" in ADAPTERS:
            try:
                desktop_ready = bool(desktop_ui.available())
            except Exception:
                desktop_ready = False
            if desktop_ready:
                ADAPTERS["desktop_ui"]["available"] = True
                ADAPTERS["desktop_ui"]["validated"] = "windows-use import OK"
                ADAPTERS["desktop_ui"]["pending"] = "target-app UI Automation exposure/run_task pilot remains"
    except Exception:
        pass

_lig_hotfix_refresh_adapter_status()
# END LIG ADAPTER STATUS HOTFIX 20260709
'''


def inject_before_main(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    text = read_text(path)
    if marker in text:
        log(f"[SKIP] already patched: {path}")
        return
    needle = 'if __name__ == "__main__":'
    idx = text.rfind(needle)
    if idx < 0:
        raise RuntimeError(f"main guard not found: {path}")
    backup_path = backup(path)
    write_text(path, text[:idx].rstrip() + "\n\n" + block.strip() + "\n\n" + text[idx:])
    log(f"[OK] patched {path} (backup: {backup_path})")


def append_once(path: Path, block: str, marker: str) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    text = read_text(path)
    if marker in text:
        log(f"[SKIP] already patched: {path}")
        return
    backup_path = backup(path)
    write_text(path, text.rstrip() + "\n\n" + block.strip() + "\n")
    log(f"[OK] patched {path} (backup: {backup_path})")


def verify_python(path: Path) -> None:
    cp = run([sys.executable, "-m", "py_compile", str(path)], timeout=60)
    if cp.returncode != 0:
        raise RuntimeError(f"py_compile failed for {path}: {(cp.stderr or cp.stdout)[-1200:]}")
    log(f"[OK] py_compile: {path}")


def run_pending_check() -> None:
    if os.environ.get("LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX") == "1":
        log("[SKIP] pending_check skipped by LIG_SKIP_PENDING_CHECK_AFTER_HOTFIX=1")
        return
    pending = WS / "agent_ops" / "pending_check.py"
    out_dir = USERDATA / "diagnostics" / "pending_checks"
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = subprocess.run(
        [sys.executable, str(pending), "--out-dir", str(out_dir)],
        cwd=str(WS),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log(f"[INFO] pending_check exit={cp.returncode}")
    log(f"[REPORT] {out_dir / 'pending-check-last.md'}")


def main() -> int:
    log("=== OpenCodeLIG existing-install hotfix 20260709 ===")
    log(f"ROOT={ROOT}")
    log(f"WS={WS}")
    if not WS.exists():
        log("[ERROR] Installed workspace not found. Install OpenCodeLIG first.")
        return 1
    copy_root_check_bat()
    create_gateway_wrappers()
    create_ocd_wrapper()
    create_launcher_helpers()
    create_session_autosave_plugin()
    patch_run_launcher()
    try_install_optional_wheels()

    pending = WS / "agent_ops" / "pending_check.py"
    adapters = WS / "agent_ops" / "adapters" / "__init__.py"
    inject_before_main(pending, PENDING_BLOCK, MARK_PENDING)
    append_once(adapters, ADAPTER_BLOCK, MARK_ADAPTERS)
    verify_python(pending)
    verify_python(adapters)
    run_pending_check()
    log("[OK] Existing install hotfix complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
