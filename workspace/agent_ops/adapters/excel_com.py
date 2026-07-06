# -*- coding: utf-8 -*-
"""Excel COM adapter with copy-only workbook policy.

The adapter never opens the original workbook directly. `open_copy` first
creates a sibling copy named 사본_<원본파일명>, then all reads/writes/macros target
that copy. pywin32 is optional so the module can load on machines without
Office automation dependencies.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from ..audit import record as audit_record

try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
    _PYWIN32_ERROR = ""
except Exception as exc:  # pragma: no cover - environment dependent
    pythoncom = None  # type: ignore
    win32com = None  # type: ignore
    _PYWIN32_ERROR = exc.__class__.__name__

_SESSION: Dict[str, Any] = {}
ACTIONS = ("open_copy", "read_range", "write_range", "run_macro_file", "save", "close")
MANUAL_IMPORT_GUIDE = "Alt+F11 → 파일 가져오기(.bas) → 매크로 실행으로 수동 진행하세요."


def _missing_pywin32() -> Dict[str, Any]:
    return {"ok": False, "error": "pywin32 미설치 — dependencies.json 'pywin32' 참조"}


def _need_pywin32() -> Optional[Dict[str, Any]]:
    if _PYWIN32_ERROR or pythoncom is None or win32com is None:
        return _missing_pywin32()
    return None


def _copy_path(src: Path) -> Path:
    base = src.with_name("사본_" + src.name)
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    for idx in range(2, 1000):
        candidate = base.with_name(f"{stem}_{idx}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("copy name exhausted")


def _session_required() -> Optional[Dict[str, Any]]:
    if not _SESSION.get("wb"):
        return {"ok": False, "error": "open_copy 먼저"}
    return None


def _sheet(name: str):
    wb = _SESSION["wb"]
    return wb.Worksheets(str(name or "Sheet1"))


def _range_to_matrix(value: Any) -> list:
    if isinstance(value, tuple):
        return [list(row) if isinstance(row, tuple) else [row] for row in value]
    return [[value]]


def _extract_macro_name(source: str) -> str:
    match = re.search(r"(?im)^\s*Sub\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source or "")
    return match.group(1) if match else ""


def _audit(action: str, options: Dict[str, Any], result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": f"excel_com.{action}",
        "target": options.get("path") or options.get("bas_path") or result.get("copy_path") or _SESSION.get("copy_path", ""),
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error") or result.get("fallback") or "",
    })


def _close_session(save_changes: bool = False) -> None:
    wb = _SESSION.get("wb")
    xl = _SESSION.get("xl")
    if wb is not None:
        try:
            wb.Close(SaveChanges=save_changes)
        except Exception:
            pass
    if xl is not None:
        try:
            xl.Quit()
        except Exception:
            pass
    try:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
    except Exception:
        pass
    _SESSION.clear()


def _open_copy(options: Dict[str, Any]) -> Dict[str, Any]:
    if _SESSION.get("wb"):
        return {"ok": False, "error": "이미 열린 사본이 있음 — close 먼저"}
    missing = _need_pywin32()
    if missing:
        return missing
    src = Path(str(options.get("path") or "")).expanduser().resolve()
    if not src.exists():
        return {"ok": False, "error": "원본 파일 없음"}
    copy_path = _copy_path(src)
    shutil.copy2(src, copy_path)
    try:
        pythoncom.CoInitialize()
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = bool(options.get("visible", False))
        xl.DisplayAlerts = False
        # xl 을 세션에 먼저 저장한다 — Workbooks.Open 이 실패해도 _close_session 이
        # 이 EXCEL.EXE 를 Quit 하도록 (저장 전이면 고아 프로세스가 남는다).
        _SESSION["xl"] = xl
        wb = xl.Workbooks.Open(str(copy_path))
    except Exception as exc:
        _close_session()
        return {"ok": False, "error": f"Excel open failed: {exc.__class__.__name__}"}
    _SESSION.update({"xl": xl, "wb": wb, "copy_path": str(copy_path)})
    return {"ok": True, "copy_path": str(copy_path)}


def _read_range(options: Dict[str, Any]) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    needed = _session_required()
    if needed:
        return needed
    try:
        value = _sheet(str(options.get("sheet") or "Sheet1")).Range(str(options.get("range") or "A1")).Value
        return {"ok": True, "values": _range_to_matrix(value)}
    except Exception as exc:
        return {"ok": False, "error": f"read_range failed: {exc.__class__.__name__}"}


def _write_range(options: Dict[str, Any]) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    needed = _session_required()
    if needed:
        return needed
    try:
        _sheet(str(options.get("sheet") or "Sheet1")).Range(str(options.get("range") or "A1")).Value = options.get("values")
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": f"write_range failed: {exc.__class__.__name__}"}


def _run_macro_file(options: Dict[str, Any]) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    needed = _session_required()
    if needed:
        return needed
    bas_path = Path(str(options.get("bas_path") or "")).expanduser().resolve()
    if not bas_path.exists():
        return {"ok": False, "error": "bas 파일 없음"}
    source = bas_path.read_text(encoding="utf-8", errors="replace")
    macro_name = str(options.get("macro_name") or _extract_macro_name(source))
    if not macro_name:
        return {"ok": False, "error": "macro_name 인식 실패"}
    try:
        wb = _SESSION["wb"]
        xl = _SESSION["xl"]
        mod = wb.VBProject.VBComponents.Add(1)
        mod.CodeModule.AddFromString(source)
        xl.Run(macro_name)
        return {"ok": True, "macro": macro_name}
    except Exception as exc:
        return {"ok": False, "error": f"VBProject 접근 실패: {exc.__class__.__name__}",
                "fallback": "manual_import", "guide": MANUAL_IMPORT_GUIDE}


def execute(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one Excel adapter action. Never raises."""
    opts = options if isinstance(options, dict) else {}
    action_name = str(action or "")
    try:
        if action_name not in ACTIONS:
            result = {"ok": False, "error": f"unknown action: {action_name}", "available_actions": list(ACTIONS)}
        elif action_name == "open_copy":
            result = _open_copy(opts)
        elif action_name == "read_range":
            result = _read_range(opts)
        elif action_name == "write_range":
            result = _write_range(opts)
        elif action_name == "run_macro_file":
            result = _run_macro_file(opts)
        elif action_name == "save":
            needed = _need_pywin32() or _session_required()
            if needed:
                result = needed
            else:
                _SESSION["wb"].Save()
                result = {"ok": True, "path": _SESSION.get("copy_path", "")}
        elif action_name == "close":
            # copy_path 를 세션이 비워지기 전에 캡처해 감사 기록의 target 이 빈 값이 되지 않게 한다.
            closed_target = _SESSION.get("copy_path", "")
            _close_session(save_changes=False)
            result = {"ok": True, "copy_path": closed_target}
    except Exception as exc:
        result = {"ok": False, "error": f"{action_name} failed: {exc.__class__.__name__}"}
    _audit(action_name, opts, result)
    return result
