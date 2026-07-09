# -*- coding: utf-8 -*-
"""AutoCAD subprocess adapter with copy-only DWG policy.

Prefer accoreconsole when present. Some company PCs expose only GUI AutoCAD
Mechanical (`acad.exe /p LIGNEX1 /product ACADM`), so fall back to `acad.exe`
with `/b <script>` while keeping the same copied-DWG safety policy.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from ..audit import record as audit_record

STANDARD_PATHS = (
    r"C:\AutoCAD 2019\accoreconsole.exe",
    r"C:\AutoCAD 2019\acad.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2019\accoreconsole.exe",
    r"C:\Program Files\Autodesk\AutoCAD 2019\acad.exe",
)


def find_accoreconsole() -> str:
    override = os.environ.get("ACCORECONSOLE_EXE", "").strip()
    if override:
        return override
    found = shutil.which("accoreconsole")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.exists():
            return str(path)
    return ""


def find_acad() -> str:
    for name in ("ACAD_EXE", "AUTOCAD_EXE"):
        override = os.environ.get(name, "").strip()
        if override:
            return override
    found = shutil.which("acad")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.name.lower() == "acad.exe" and path.exists():
            return str(path)
    return ""


def find_autocad_executable() -> tuple[str, str]:
    console = find_accoreconsole()
    if console:
        return console, "accoreconsole"
    gui = find_acad()
    if gui:
        return gui, "acad"
    return "", ""


def _copy_path(src: Path) -> Path:
    base = src.with_name("사본_" + src.name)
    if not base.exists():
        return base
    for idx in range(2, 1000):
        candidate = base.with_name(f"{base.stem}_{idx}{base.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("copy name exhausted")


def _decode_autocad(data: bytes) -> str:
    if not data:
        return ""
    return data.decode("utf-16-le", errors="replace")


def _audit(copy_dwg: Path, scr_path: Path, result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": "autocad_batch.execute",
        "target": f"{copy_dwg.name}|{scr_path.name}",
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or f"exit {result.get('returncode', '')}",
    })


def execute(dwg_path: str, scr_path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    dwg = Path(str(dwg_path or "")).expanduser().resolve()
    scr = Path(str(scr_path or "")).expanduser().resolve()
    if not dwg.exists():
        return {"ok": False, "error": "DWG 파일 없음"}
    if not scr.exists():
        return {"ok": False, "error": "AutoCAD script 파일 없음"}
    exe, exe_kind = find_autocad_executable()
    if not exe:
        return {"ok": False, "error": "AutoCAD 실행파일 없음 — ACCORECONSOLE_EXE, ACAD_EXE, AUTOCAD_EXE 또는 AutoCAD 2019 경로 확인"}
    timeout_s = int(opts.get("timeout_s") or 300)
    copy_dwg = _copy_path(dwg)
    shutil.copy2(dwg, copy_dwg)
    if exe_kind == "accoreconsole":
        cmd = [exe, "/i", str(copy_dwg), "/s", str(scr)]
    else:
        profile = str(opts.get("profile") or os.environ.get("AUTOCAD_PROFILE") or "LIGNEX1")
        product = str(opts.get("product") or os.environ.get("AUTOCAD_PRODUCT") or "ACADM")
        cmd = [exe, str(copy_dwg), "/p", profile, "/product", product, "/b", str(scr)]
    try:
        r = subprocess.run(cmd, cwd=str(scr.parent), capture_output=True, timeout=timeout_s)
        out = _decode_autocad(r.stdout or b"")
        err = _decode_autocad(r.stderr or b"")
        if r.returncode == 53:
            result = {
                "ok": False,
                "error": "AutoCAD가 도면을 열지 못함(exit 53) — 사본 dwg 경로 확인",
                "returncode": r.returncode,
                "copy_path": str(copy_dwg),
                "log_tail": (out + err)[-400:],
                "cmd": cmd,
            }
        else:
            result = {
                "ok": r.returncode == 0,
                "returncode": r.returncode,
                "copy_path": str(copy_dwg),
                "stdout_tail": out[-800:],
                "stderr_tail": err[-800:],
                "cmd": cmd,
            }
            if r.returncode != 0:
                result["error"] = f"AutoCAD command failed exit {r.returncode}"
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": f"AutoCAD command timeout ({timeout_s}s)", "copy_path": str(copy_dwg), "cmd": cmd}
    except Exception as exc:
        result = {"ok": False, "error": f"AutoCAD command failed: {exc.__class__.__name__}", "copy_path": str(copy_dwg), "cmd": cmd}
    _audit(copy_dwg, scr, result)
    return result
