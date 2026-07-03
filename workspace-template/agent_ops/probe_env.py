# -*- coding: utf-8 -*-
"""Environment probe: one run captures the facts workers otherwise guess at.

The user runs launch\\probe-env.bat on a target PC (home or company) and
uploads the generated JSON/MD to the repo's probe/results/. Every worker then
builds against measured facts instead of assumptions.

Collected (all read-only, stdlib only):
  - OS / Python versions, RAM, disk free
  - Installed automation targets via registry ProgIDs and known paths:
    Excel/Word/PowerPoint/Outlook, HWP, SolidWorks, MATLAB, AutoCAD
    (accoreconsole), ANSYS Fluent, Chrome
  - Office version markers + macro security policy (AccessVBOM / VBAWarnings)
    — the single biggest unknown for COM automation on the company PC

Privacy: no hostname, no username, no MAC/IP, no secrets. Paths under the
user profile are recorded with the profile prefix replaced by %USERPROFILE%.
"""
from __future__ import annotations

import ctypes
import glob
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

try:
    import winreg
except ImportError:  # non-Windows: probe still runs, records unsupported
    winreg = None


def _mask_path(p: str) -> str:
    home = str(Path.home())
    return p.replace(home, "%USERPROFILE%") if p else p


def _reg_read(root, key, value=None):
    """Read a registry value; returns (found, data)."""
    if winreg is None:
        return (False, "winreg unavailable")
    try:
        with winreg.OpenKey(root, key) as k:
            if value is None:
                data, _ = winreg.QueryValueEx(k, "")
            else:
                data, _ = winreg.QueryValueEx(k, value)
            return (True, str(data))
    except OSError:
        return (False, "")


def _progid_exists(progid: str):
    found, curver = _reg_read(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CurVer") if winreg else (False, "")
    if not found:
        found = _reg_read(winreg.HKEY_CLASSES_ROOT, progid)[0] if winreg else False
        curver = ""
    return {"installed": bool(found), "curver": curver}


def _first_glob(patterns):
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return _mask_path(hits[-1])  # 최신 버전 우선 (사전순 마지막)
    return ""


def _ram_gb() -> float:
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return round(stat.ullTotalPhys / (1024 ** 3), 1)
    except Exception:
        return -1.0


def _office_security():
    """Macro security policy — decides whether COM macro injection can work.

    AccessVBOM: 1 = 'Trust access to the VBA project object model' enabled.
    VBAWarnings: 1=enable all, 2=disable w/ notification(default), 3=digitally
    signed only, 4=disable all. Missing key = default (2).
    """
    result = {}
    if winreg is None:
        return {"error": "winreg unavailable (not Windows)"}
    for app in ("Excel", "Word", "PowerPoint", "Outlook"):
        for ver in ("16.0", "15.0"):
            base = f"Software\\Microsoft\\Office\\{ver}\\{app}\\Security"
            f1, access_vbom = _reg_read(winreg.HKEY_CURRENT_USER, base, "AccessVBOM")
            f2, vba_warn = _reg_read(winreg.HKEY_CURRENT_USER, base, "VBAWarnings")
            if f1 or f2:
                result[app.lower()] = {
                    "office_ver_key": ver,
                    "AccessVBOM": access_vbom if f1 else "키 없음(기본: 0=차단)",
                    "VBAWarnings": vba_warn if f2 else "키 없음(기본: 2=알림 후 사용 안 함)",
                }
                break
        else:
            result[app.lower()] = {"office_ver_key": "", "AccessVBOM": "키 없음",
                                   "VBAWarnings": "키 없음"}
    # Group policy overrides (HKLM policies) — if present these win over HKCU.
    for app in ("excel", "word", "powerpoint"):
        base = f"Software\\Policies\\Microsoft\\Office\\16.0\\{app}\\Security"
        f, v = _reg_read(winreg.HKEY_CURRENT_USER, base, "VBAWarnings")
        if f:
            result[app]["policy_VBAWarnings"] = v  # 그룹 정책 강제값 존재
    return result


def run_probe() -> dict:
    report = {
        "probe": "env",
        "version": 1,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "os": platform.platform(),
        "python": sys.version.split()[0],
        "py_launcher_311": bool(shutil.which("py")),
        "ram_gb": _ram_gb(),
        "disk_free_gb": round(shutil.disk_usage(Path.home()).free / (1024 ** 3), 1),
        "apps": {},
        "office_macro_security": _office_security(),
    }
    if winreg is not None:
        report["apps"] = {
            "excel": _progid_exists("Excel.Application"),
            "word": _progid_exists("Word.Application"),
            "powerpoint": _progid_exists("PowerPoint.Application"),
            "outlook": _progid_exists("Outlook.Application"),
            "hwp": _progid_exists("HWPFrame.HwpObject"),
            "solidworks": _progid_exists("SldWorks.Application"),
        }
        found, c2r = _reg_read(winreg.HKEY_LOCAL_MACHINE,
                               r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration",
                               "ProductReleaseIds")
        report["office_product_ids"] = c2r if found else "키 없음 (MSI 설치 또는 미설치)"
        found, chrome = _reg_read(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        report["apps"]["chrome"] = {"installed": found, "path": _mask_path(chrome)}
    report["apps"]["matlab_exe"] = _first_glob(
        [r"C:\Program Files\MATLAB\R20*\bin\matlab.exe"])
    # 실측(2026-07-03): 회사 AutoCAD Mechanical 2019는 C:\AutoCAD 2019\ 비표준 경로.
    report["apps"]["accoreconsole_exe"] = _first_glob(
        [r"C:\AutoCAD*\accoreconsole.exe",
         r"C:\Program Files\Autodesk\AutoCAD*\accoreconsole.exe"])
    report["apps"]["acad_exe"] = _first_glob(
        [r"C:\AutoCAD*\acad.exe", r"C:\Program Files\Autodesk\AutoCAD*\acad.exe"])
    report["apps"]["fluent_exe"] = _first_glob(
        [r"C:\Program Files\ANSYS Inc\v*\fluent\ntbin\win64\fluent.exe"])
    try:
        import win32com  # noqa: F401
        report["pywin32"] = True
    except ImportError:
        report["pywin32"] = False
    report["proxy_env"] = {k: bool(os.environ.get(k))
                           for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
                                     "http_proxy", "https_proxy")}
    report["opencode"] = _opencode_probe()
    return report


def _opencode_probe() -> dict:
    """OpenCode 기동 지연 진단: 잔류 프로세스, 구버전 proxy(8765), exe 위치,
    `--version` 소요 시간(cold/warm), autoupdate 설정 존재 여부.

    과거 실측 원인 3종(진단 스크립트 대기 / 잔류 proxy·프로세스 / 업데이트 확인)을
    한 번에 판별하기 위한 데이터 수집 — 판단은 결과를 보고 한다.
    """
    import shutil as _sh
    import socket
    import subprocess
    import time as _t
    info: dict = {}
    exe = _sh.which("opencode") or ""
    if not exe:
        cand = Path.home() / "OpenCodeLIG" / "bin" / "opencode.exe"
        if cand.exists():
            exe = str(cand)
    info["exe"] = _mask_path(exe)
    if exe:
        timings = []
        for label in ("cold", "warm"):
            t0 = _t.time()
            try:
                subprocess.run([exe, "--version"], capture_output=True, timeout=90)
                timings.append({label: round(_t.time() - t0, 1)})
            except subprocess.TimeoutExpired:
                timings.append({label: "timeout(>90s)"})
                break
            except Exception as e:
                timings.append({label: f"error:{type(e).__name__}"})
                break
        info["version_cmd_seconds"] = timings
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq opencode.exe", "/FO", "CSV", "/NH"],
            capture_output=True, timeout=15, text=True).stdout
        info["leftover_opencode_processes"] = out.lower().count("opencode.exe")
    except Exception:
        info["leftover_opencode_processes"] = "확인 실패"
    try:  # 구버전 proxy 잔류 여부 (신버전은 proxy를 쓰지 않음)
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            info["legacy_proxy_8765"] = "리스닝 중 (구버전 proxy 잔류 의심)"
    except Exception:
        info["legacy_proxy_8765"] = "없음"
    configs = {}
    for label, p in [
            ("workspace_opencode_json", Path.home() / "OpenCodeLIG" / "workspace" / "opencode.json"),
            ("home_opencode_json", Path.home() / ".config" / "opencode" / "opencode.json"),
            ("home_opencode_jsonc", Path.home() / ".config" / "opencode" / "opencode.jsonc")]:
        if p.exists():
            head = p.read_text(encoding="utf-8", errors="replace")[:2000]
            configs[label] = {"exists": True, "autoupdate_set": "autoupdate" in head}
        else:
            configs[label] = {"exists": False}
    info["configs"] = configs
    # 구버전 흔적: lig_diag / proxy 스크립트가 워크스페이스에 있는지 (main 아티팩트 판별)
    ws = Path.home() / "OpenCodeLIG" / "workspace"
    info["legacy_files"] = {
        "lig_diag": bool(list(ws.glob("**/lig_diag*.py"))) if ws.exists() else False,
        "capabilities_py(신버전 표식)": (ws / "agent_ops" / "capabilities.py").exists() if ws.exists() else False,
    }
    return info


def _to_markdown(r: dict) -> str:
    lines = [f"# 환경 probe 결과 ({r['timestamp']})", "",
             f"- OS: {r['os']} / Python {r['python']} / RAM {r['ram_gb']}GB / 디스크 여유 {r['disk_free_gb']}GB",
             f"- pywin32: {r.get('pywin32')}", "", "## 자동화 대상 앱", ""]
    for name, info in r["apps"].items():
        lines.append(f"- {name}: {json.dumps(info, ensure_ascii=False)}")
    lines += ["", "## Office 매크로 보안 정책 (COM 자동화 가능 여부의 핵심)", ""]
    for app, sec in r.get("office_macro_security", {}).items():
        lines.append(f"- {app}: {json.dumps(sec, ensure_ascii=False)}")
    lines += ["", "> AccessVBOM=1 이면 매크로 자동 주입 가능. 0/키 없음이면 수동 import 경로 사용.",
              "> policy_* 키가 있으면 그룹 정책 강제 — 개인 설정 변경 불가."]
    lines += ["", "## OpenCode 기동 진단", "",
              f"- proxy env 설정 여부: {json.dumps(r.get('proxy_env', {}), ensure_ascii=False)}"]
    for key, value in r.get("opencode", {}).items():
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines)


def main() -> int:
    out_dir = Path(os.environ.get("PROBE_OUT_DIR") or Path.cwd())
    out_dir.mkdir(parents=True, exist_ok=True)
    report = run_probe()
    stamp = time.strftime("%Y%m%d")
    jpath = out_dir / f"probe_env_{stamp}.json"
    mpath = out_dir / f"probe_env_{stamp}.md"
    jpath.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    mpath.write_text(_to_markdown(report), encoding="utf-8")
    print(_to_markdown(report))
    print(f"\n결과 파일 (repo의 probe/results/ 에 올려주세요):\n  {jpath}\n  {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
