# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import base64
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
REPO = WS.parent
HOTFIX = WS / "patches" / "existing_install_hotfix_20260709.py"
FINAL_BAT = REPO / "최종_패치파일.bat"

EMBEDDED_TEXT_SOURCES: dict[str, Path] = {
    "SESSION_AUTOSAVE_PLUGIN": WS / ".opencode" / "plugins" / "session-autosave.ts",
    "HAMSTER_STATUS_PLUGIN": WS / ".opencode" / "plugins" / "hamster-status.ts",
    "MEMORY_INJECT_PLUGIN": WS / ".opencode" / "plugins" / "memory-inject.ts",
    "COMPACTION_HANDOFF_PLUGIN": WS / ".opencode" / "plugins" / "compaction-handoff.ts",
    "AUTOCAD_BATCH_SOURCE": WS / "agent_ops" / "adapters" / "autocad_batch.py",
    "RELEASE_CONTRACTS_SOURCE": WS / "agent_ops" / "release_contracts.py",
    "SELF_IMPROVEMENT_SOURCE": WS / "agent_ops" / "self_improvement.py",
    "QUALITY_GATE_SOURCE": WS / "agent_ops" / "quality_gate.py",
}

PY_MARKER = "__OPENCODELIG_HOTFIX_PY_BASE64__"
WHEEL_NAME_MARKER = "__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__"
WHEEL_MARKER = "__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__"
END_MARKER = "__OPENCODELIG_HOTFIX_END__"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def wrap_base64(data: bytes, width: int = 120) -> list[str]:
    encoded = base64.b64encode(data).decode("ascii")
    return [encoded[i : i + width] for i in range(0, len(encoded), width)]


def replace_raw_constant(doc: str, name: str, body: str) -> str:
    token = f"{name} = r'''"
    start = doc.find(token)
    if start < 0:
        raise RuntimeError(f"constant not found: {name}")
    body_start = start + len(token)
    end = doc.find("\n'''", body_start)
    if end < 0:
        raise RuntimeError(f"constant terminator not found: {name}")
    return doc[:start] + token + body.rstrip("\n") + "\n'''" + doc[end + 4 :]


def upsert_raw_constant(doc: str, name: str, body: str, *, anchor: str) -> str:
    token = f"{name} = r'''"
    if token in doc:
        return replace_raw_constant(doc, name, body)
    idx = doc.find(anchor)
    if idx < 0:
        raise RuntimeError(f"anchor not found for {name}: {anchor}")
    block = f"{name} = r'''{body.rstrip(chr(10))}\n'''\n\n"
    return doc[:idx] + block + doc[idx:]


def ensure_release_contracts_function(doc: str) -> str:
    marker = "def create_release_contracts() -> None:"
    if marker in doc:
        return doc
    anchor = "def create_quality_gate() -> None:"
    idx = doc.find(anchor)
    if idx < 0:
        raise RuntimeError("create_quality_gate anchor not found")
    block = '''
def create_release_contracts() -> None:
    path = WS / "agent_ops" / "release_contracts.py"
    if write_text_if_changed(path, RELEASE_CONTRACTS_SOURCE):
        log(f"[OK] release contracts created/updated: {path}")
    else:
        log(f"[SKIP] release contracts already current: {path}")

'''
    return doc[:idx] + block + doc[idx:]


def ensure_release_contracts_main_call(doc: str) -> str:
    marker = "    create_release_contracts()\n"
    if marker in doc:
        return doc
    needle = "    create_self_improvement()\n"
    idx = doc.find(needle)
    if idx < 0:
        raise RuntimeError("create_self_improvement call not found")
    insert_at = idx + len(needle)
    return doc[:insert_at] + marker + doc[insert_at:]


def ensure_release_contracts_verification(doc: str) -> str:
    marker = '    verify_python(WS / "agent_ops" / "release_contracts.py")\n'
    if marker in doc:
        return doc
    needle = "    verify_python(pending)\n"
    idx = doc.find(needle)
    if idx < 0:
        raise RuntimeError("verify_python(pending) anchor not found")
    return doc[:idx] + marker + doc[idx:]


def sync_hotfix_sources() -> str:
    doc = normalize_text(read_text(HOTFIX))
    for name, path in EMBEDDED_TEXT_SOURCES.items():
        body = normalize_text(read_text(path))
        if name == "RELEASE_CONTRACTS_SOURCE":
            doc = upsert_raw_constant(doc, name, body, anchor="SELF_IMPROVEMENT_SOURCE = r'''")
        else:
            doc = replace_raw_constant(doc, name, body)
    doc = ensure_release_contracts_function(doc)
    doc = ensure_release_contracts_main_call(doc)
    doc = ensure_release_contracts_verification(doc)
    HOTFIX.write_text(doc, encoding="utf-8", newline="\n")
    return doc


def _section(lines: list[str], start: str, end: str) -> str:
    i = lines.index(start)
    j = lines.index(end)
    return "".join(lines[i + 1 : j])


def find_mss_wheel() -> tuple[str, bytes]:
    search_roots = [
        WS / "tools" / "wheelhouse",
        REPO / "tools" / "wheelhouse",
        REPO,
    ]
    for root in search_roots:
        if not root.exists():
            continue
        wheels = sorted(root.rglob("mss-*.whl"))
        if wheels:
            wheel = wheels[0]
            return wheel.name, wheel.read_bytes()
    if FINAL_BAT.exists():
        lines = FINAL_BAT.read_text(encoding="utf-8", errors="replace").splitlines()
        wheel_name = _section(lines, WHEEL_NAME_MARKER, WHEEL_MARKER).strip()
        wheel_data = base64.b64decode(_section(lines, WHEEL_MARKER, END_MARKER))
        if wheel_name:
            return wheel_name, wheel_data
    raise FileNotFoundError("mss wheel not found in wheelhouse or existing final patch BAT")


def build_final_bat() -> None:
    hotfix_bytes = HOTFIX.read_bytes()
    wheel_name, wheel_bytes = find_mss_wheel()
    lines = [
        "@echo off",
        "",
        "chcp 65001 >nul",
        "",
        "setlocal EnableExtensions",
        "",
        'set "PYTHONUTF8=1"',
        'set "PYTHONIOENCODING=utf-8"',
        'set "LITELLM_LOCAL_MODEL_COST_MAP=True"',
        'set "LITELLM_LOCAL_POLICY_TEMPLATES=True"',
        'set "LITELLM_LOCAL_BLOG_POSTS=True"',
        'set "BAT_SELF=%~f0"',
        'set "HOTFIX_PKG=%TEMP%\\opencodelig_hotfix_pkg_%RANDOM%%RANDOM%"',
        'set "HOTFIX_WHEEL_DIR=%HOTFIX_PKG%\\patch_wheels"',
        'set "HOTFIX_PY=%HOTFIX_PKG%\\existing_install_hotfix_20260709.py"',
        'set "LIG_HOTFIX_PACKAGE_DIR=%HOTFIX_PKG%"',
        'mkdir "%HOTFIX_WHEEL_DIR%" >nul 2>&1',
        "",
        "powershell -NoProfile -ExecutionPolicy Bypass -Command \"$self=$env:BAT_SELF; $pkg=$env:HOTFIX_PKG; $py=$env:HOTFIX_PY; $wheelDir=$env:HOTFIX_WHEEL_DIR; $lines=[System.IO.File]::ReadAllLines($self); function Sec($a,$b){$i=[Array]::IndexOf($lines,$a); $j=[Array]::IndexOf($lines,$b); if($i -lt 0 -or $j -lt 0 -or $j -le $i){throw 'payload marker not found: '+$a}; return ($lines[($i+1)..($j-1)] -join '')}; $py64=Sec '__OPENCODELIG_HOTFIX_PY_BASE64__' '__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__'; $wheelName=(Sec '__OPENCODELIG_HOTFIX_MSS_WHEEL_NAME__' '__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__').Trim(); $wheel64=Sec '__OPENCODELIG_HOTFIX_MSS_WHEEL_BASE64__' '__OPENCODELIG_HOTFIX_END__'; [void][System.IO.Directory]::CreateDirectory($pkg); [void][System.IO.Directory]::CreateDirectory($wheelDir); [System.IO.File]::WriteAllBytes($py,[Convert]::FromBase64String($py64)); [System.IO.File]::WriteAllBytes((Join-Path $wheelDir $wheelName),[Convert]::FromBase64String($wheel64))\"",
        "if errorlevel 1 (",
        '  if exist "%HOTFIX_PKG%" rmdir /s /q "%HOTFIX_PKG%" >nul 2>&1',
        "  echo [ERROR] Failed to extract embedded hotfix payload.",
        "  echo [INFO] Temporary files were cleaned. Run the patch again; it is safe to retry.",
        "  pause",
        "  exit /b 1",
        ")",
        "",
        "where py >nul 2>nul",
        "if %ERRORLEVEL%==0 (",
        '  py -3.11 "%HOTFIX_PY%" %*',
        ") else (",
        '  python "%HOTFIX_PY%" %*',
        ")",
        'set "RC=%ERRORLEVEL%"',
        'if exist "%HOTFIX_PKG%" rmdir /s /q "%HOTFIX_PKG%" >nul 2>&1',
        'if not "%RC%"=="0" (',
        "  echo.",
        "  echo [ERROR] Patch failed. Review:",
        "  echo   %USERPROFILE%\\OpenCodeLIG_USERDATA\\diagnostics\\patches",
        "  pause",
        "  exit /b %RC%",
        ")",
        "",
        "echo.",
        "echo [OK] Patch finished.",
        "echo.",
        "pause",
        "exit /b 0",
        "",
        PY_MARKER,
        *wrap_base64(hotfix_bytes),
        WHEEL_NAME_MARKER,
        wheel_name,
        WHEEL_MARKER,
        *wrap_base64(wheel_bytes),
        END_MARKER,
        "",
    ]
    FINAL_BAT.write_bytes("\r\n".join(lines).encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync existing-install hotfix embeds and rebuild final patch BAT.")
    parser.add_argument("--hotfix-only", action="store_true")
    parser.add_argument("--final-bat-only", action="store_true")
    args = parser.parse_args(argv)

    did_hotfix = False
    did_final_bat = False
    if not args.final_bat_only:
        sync_hotfix_sources()
        did_hotfix = True
    if not args.hotfix_only:
        build_final_bat()
        did_final_bat = True
    if did_hotfix:
        print(f"[OK] synced hotfix: {HOTFIX}")
    if did_final_bat:
        print(f"[OK] rebuilt final BAT: {FINAL_BAT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
