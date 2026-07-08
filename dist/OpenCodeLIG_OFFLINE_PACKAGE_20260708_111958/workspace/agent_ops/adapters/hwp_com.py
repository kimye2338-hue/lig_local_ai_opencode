# -*- coding: utf-8 -*-
"""HWP COM adapter for Markdown -> new HWP document conversion."""
from __future__ import annotations

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

ACTIONS = ("md_to_hwp",)


def _missing_pywin32() -> Dict[str, Any]:
    return {"ok": False, "error": "pywin32 미설치 — dependencies.json 'pywin32' 참조"}


def _need_pywin32() -> Optional[Dict[str, Any]]:
    if _PYWIN32_ERROR or pythoncom is None or win32com is None:
        return _missing_pywin32()
    return None


def _audit(action: str, options: Dict[str, Any], result: Dict[str, Any]) -> None:
    audit_record({
        "kind": "adapter",
        "name": f"hwp_com.{action}",
        "target": options.get("out_path") or options.get("path") or "",
        "risk": "dangerous",
        "verdict": "approved" if result.get("ok") else "failed",
        "detail": result.get("error", "") or result.get("fallback", ""),
    })


def _plain_text_from_md(text: str) -> str:
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        line = line.replace("**", "").replace("__", "")
        lines.append(line)
    return "\r\n".join(lines).strip() + "\r\n"


def md_to_hwp(md_path: str, out_path: str) -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    src = Path(str(md_path or "")).expanduser().resolve()
    dst = Path(str(out_path or "")).expanduser().resolve()
    if not src.exists():
        return {"ok": False, "error": "Markdown 파일 없음"}
    if not dst.name:
        return {"ok": False, "error": "out_path 필요"}
    text = src.read_text(encoding="utf-8", errors="replace")
    hwp = None
    try:
        pythoncom.CoInitialize()
        hwp = win32com.client.Dispatch("HWPFrame.HwpObject")
        try:
            hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
        except Exception:
            pass
        hwp.XHwpDocuments.Add()
        hwp.HAction.GetDefault("InsertText", hwp.HParameterSet.HInsertText.HSet)
        hwp.HParameterSet.HInsertText.Text = _plain_text_from_md(text)
        hwp.HAction.Execute("InsertText", hwp.HParameterSet.HInsertText.HSet)
        dst.parent.mkdir(parents=True, exist_ok=True)
        hwp.SaveAs(str(dst))
        return {"ok": True, "path": str(dst), "source": src.name}
    except Exception as exc:
        return {"ok": False, "error": f"HWP md_to_hwp failed: {exc.__class__.__name__}"}
    finally:
        if hwp is not None:
            try:
                hwp.Quit()
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
        elif action_name == "md_to_hwp":
            result = md_to_hwp(str(opts.get("path") or opts.get("md_path") or ""),
                               str(opts.get("out_path") or ""))
    except Exception as exc:
        result = {"ok": False, "error": f"{action_name} failed: {exc.__class__.__name__}"}
    _audit(action_name, opts, result)
    return result
