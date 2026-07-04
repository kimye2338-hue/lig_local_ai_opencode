# -*- coding: utf-8 -*-
"""SolidWorks COM adapter with copy-only document policy."""
from __future__ import annotations

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

ACTIONS = ("run_macro",)
MANUAL_IMPORT_GUIDE = "SolidWorks 매크로 편집기에서 .bas 내용을 새 매크로로 import한 뒤 사본 문서에서 실행하세요."


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
    for idx in range(2, 1000):
        candidate = base.with_name(f"{base.stem}_{idx}{base.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("copy name exhausted")


def _audit(action: str, options: Dict[str, Any], result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": f"solidworks_com.{action}",
        "target": result.get("copy_path") or options.get("doc_path") or options.get("path") or "",
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or result.get("fallback", ""),
    })


def _solidworks_app(visible: bool = False) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    try:
        pythoncom.CoInitialize()
        app = win32com.client.GetActiveObject("SldWorks.Application")
    except Exception:
        try:
            app = win32com.client.Dispatch("SldWorks.Application")
        except Exception as exc:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
            return {"ok": False, "error": f"SolidWorks 실행/접속 실패: {exc.__class__.__name__}"}
    try:
        app.Visible = bool(visible)
    except Exception:
        pass
    return {"ok": True, "app": app}


def run_macro(doc_path: str, bas_path: str, options: Dict[str, Any] | None = None) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    doc = Path(str(doc_path or "")).expanduser().resolve()
    macro = Path(str(bas_path or "")).expanduser().resolve()
    if not doc.exists():
        return {"ok": False, "error": "SolidWorks 문서 파일 없음"}
    if not macro.exists():
        return {"ok": False, "error": "매크로 파일 없음"}
    copy_doc = _copy_path(doc)
    shutil.copy2(doc, copy_doc)
    if macro.suffix.lower() == ".bas":
        return {"ok": False, "copy_path": str(copy_doc), "fallback": "manual_import",
                "error": ".bas는 SolidWorks RunMacro2 직접 실행 대상이 아닐 수 있음",
                "guide": MANUAL_IMPORT_GUIDE}
    attached = _solidworks_app(bool(opts.get("visible", False)))
    if not attached.get("ok"):
        attached["copy_path"] = str(copy_doc)
        return attached
    app = attached["app"]
    model = None
    try:
        errors = 0
        warnings = 0
        model = app.OpenDoc6(str(copy_doc), 0, 1, "", errors, warnings)
        if model is None:
            return {"ok": False, "copy_path": str(copy_doc), "error": "SolidWorks 문서 열기 실패"}
        ok = bool(app.RunMacro2(str(macro), "", "", 0, 0))
        result: Dict[str, Any] = {"ok": ok, "copy_path": str(copy_doc), "saved": False}
        if not ok:
            result["error"] = "SolidWorks RunMacro2 failed"
        return result
    except Exception as exc:
        return {"ok": False, "copy_path": str(copy_doc), "error": f"SolidWorks run_macro failed: {exc.__class__.__name__}"}
    finally:
        try:
            if model is not None:
                app.CloseDoc(model.GetTitle())
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def execute(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    action_name = str(action or "")
    try:
        if action_name not in ACTIONS:
            result = {"ok": False, "error": f"unknown action: {action_name}", "available_actions": list(ACTIONS)}
        elif action_name == "run_macro":
            result = run_macro(str(opts.get("doc_path") or opts.get("path") or ""),
                               str(opts.get("bas_path") or opts.get("macro_path") or ""), opts)
    except Exception as exc:
        result = {"ok": False, "error": f"{action_name} failed: {exc.__class__.__name__}"}
    _audit(action_name, opts, result)
    return result
