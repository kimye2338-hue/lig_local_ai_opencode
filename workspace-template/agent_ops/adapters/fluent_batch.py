# -*- coding: utf-8 -*-
"""ANSYS Fluent batch subprocess adapter."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from ..audit import record as audit_record

STANDARD_PATHS = (
    r"C:\Program Files\ANSYS Inc\v241\fluent\ntbin\win64\fluent.exe",
    r"C:\Program Files\ANSYS Inc\v242\fluent\ntbin\win64\fluent.exe",
)


def find_fluent() -> str:
    override = os.environ.get("FLUENT_EXE", "").strip()
    if override:
        return override
    found = shutil.which("fluent")
    if found:
        return found
    for raw in STANDARD_PATHS:
        path = Path(raw)
        if path.exists():
            return str(path)
    return ""


def _audit(journal_path: Path, result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": "fluent_batch.execute",
        "target": journal_path.name,
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or f"exit {result.get('returncode', '')}",
    })


def execute(journal_path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    path = Path(str(journal_path or "")).expanduser().resolve()
    if not path.exists():
        result = {"ok": False, "error": "Fluent journal 파일 없음"}
        _audit(path, result)
        return result
    exe = find_fluent()
    if not exe:
        result = {"ok": False, "error": "fluent.exe 없음 — FLUENT_EXE 또는 ANSYS Inc 표준 경로 확인"}
        _audit(path, result)
        return result
    timeout_s = int(opts.get("timeout_s") or 1800)
    dimension = str(opts.get("dimension") or "3ddp")
    cores = int(opts.get("cores") or 1)
    cmd = [exe, dimension, "-g", "-i", str(path), f"-t{cores}"]
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
            result["error"] = f"Fluent batch failed exit {r.returncode}"
    except subprocess.TimeoutExpired:
        result = {"ok": False, "error": f"Fluent batch timeout ({timeout_s}s)", "cmd": cmd}
    except Exception as exc:
        result = {"ok": False, "error": f"Fluent batch failed: {exc.__class__.__name__}", "cmd": cmd}
    _audit(path, result)
    return result
