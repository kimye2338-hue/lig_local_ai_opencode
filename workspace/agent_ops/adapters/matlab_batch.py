# -*- coding: utf-8 -*-
"""MATLAB -batch subprocess adapter."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from ..audit import record as audit_record

STANDARD_PATHS = (
    r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe",
)


def find_matlab() -> str:
    override = os.environ.get("MATLAB_EXE", "").strip()
    if override:
        return override
    found = shutil.which("matlab")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.exists():
            return str(path)
    return ""


def _audit(script_path: Path, result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": "matlab_batch.execute",
        "target": script_path.name,
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or f"exit {result.get('returncode', '')}",
    })


def execute(script_path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    path = Path(str(script_path or "")).expanduser().resolve()
    if not path.exists():
        result = {"ok": False, "error": "MATLAB script 파일 없음"}
        _audit(path, result)
        return result
    exe = find_matlab()
    if not exe:
        result = {"ok": False, "error": "MATLAB 실행 파일 없음 — MATLAB_EXE 또는 PATH 확인"}
        _audit(path, result)
        return result
    timeout_s = int(opts.get("timeout_s") or 300)
    cmd = [exe, "-batch", f"run('{path.name}')"]
    try:
        r = subprocess.run(cmd, cwd=str(path.parent), capture_output=True, timeout=timeout_s)
        out = (r.stdout or b"").decode("utf-8", errors="replace")
        err = (r.stderr or b"").decode("utf-8", errors="replace")
        result = {
            "ok": r.returncode == 0,
            "returncode": r.returncode,
            "stdout_tail": out[-800:],
            "stderr_tail": err[-800:],
            "cmd": cmd,
        }
        if r.returncode != 0:
            result["error"] = f"MATLAB -batch failed exit {r.returncode}"
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": f"MATLAB -batch timeout ({timeout_s}s)", "cmd": cmd}
    except Exception as exc:
        result = {"ok": False, "error": f"MATLAB -batch failed: {exc.__class__.__name__}", "cmd": cmd}
    _audit(path, result)
    return result
