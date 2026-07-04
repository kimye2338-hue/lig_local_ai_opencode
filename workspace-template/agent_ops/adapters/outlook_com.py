# -*- coding: utf-8 -*-
"""Outlook COM adapter with active-instance-only read policy.

Company probing showed that starting a new Outlook COM instance can hang while
waiting for profile or security prompts. This adapter never calls DispatchEx.
Read actions run in a short-lived subprocess so a stuck MAPI call cannot hang
the parent process.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import schedule_store
from ..approval import classify_risk
from ..core import ROOT

try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
    _PYWIN32_ERROR = ""
except Exception as exc:  # pragma: no cover - environment dependent
    pythoncom = None  # type: ignore
    win32com = None  # type: ignore
    _PYWIN32_ERROR = exc.__class__.__name__

ACTIONS = ("read_calendar", "sync_calendar", "read_inbox")
INTERNAL_ACTIONS = ("send_mail",)
DEFAULT_TIMEOUT = 30
OUTLOOK_NOT_RUNNING = "Outlook이 실행 중이 아닙니다 — Outlook을 먼저 실행한 뒤 다시 시도하세요"
CODE_ROOT = Path(__file__).resolve().parents[2]


def _missing_pywin32() -> Dict[str, Any]:
    return {"ok": False, "error": "pywin32 미설치 — dependencies.json 'pywin32' 참조"}


def _need_pywin32() -> Optional[Dict[str, Any]]:
    if os.environ.get("LIG_OUTLOOK_COM_DISABLE") == "1":
        return _missing_pywin32()
    if _PYWIN32_ERROR or pythoncom is None or win32com is None:
        return _missing_pywin32()
    return None


def _json_safe(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _active_outlook() -> Dict[str, Any]:
    missing = _need_pywin32()
    if missing:
        return missing
    try:
        pythoncom.CoInitialize()
        app = win32com.client.GetActiveObject("Outlook.Application")
        return {"ok": True, "app": app}
    except Exception:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        return {"ok": False, "error": OUTLOOK_NOT_RUNNING}


def _read_calendar_child(days: int = 7) -> Dict[str, Any]:
    attached = _active_outlook()
    if not attached.get("ok"):
        return attached
    try:
        app = attached["app"]
        namespace = app.GetNamespace("MAPI")
        folder = namespace.GetDefaultFolder(9)
        items = folder.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")
        start = datetime.now()
        end = start + timedelta(days=max(1, int(days or 7)))
        restriction = "[Start] >= '%s' AND [Start] <= '%s'" % (
            start.strftime("%m/%d/%Y %I:%M %p"),
            end.strftime("%m/%d/%Y %I:%M %p"),
        )
        try:
            items = items.Restrict(restriction)
        except Exception:
            pass
        rows: List[Dict[str, str]] = []
        for item in items:
            rows.append({
                "title": _json_safe(getattr(item, "Subject", "")),
                "start": _json_safe(getattr(item, "Start", "")),
                "end": _json_safe(getattr(item, "End", "")),
            })
            if len(rows) >= 200:
                break
        return {"ok": True, "items": rows}
    except Exception as exc:
        return {"ok": False, "error": f"Outlook calendar read failed: {exc.__class__.__name__}"}
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _read_inbox_child(limit: int = 50) -> Dict[str, Any]:
    attached = _active_outlook()
    if not attached.get("ok"):
        return attached
    try:
        app = attached["app"]
        namespace = app.GetNamespace("MAPI")
        folder = namespace.GetDefaultFolder(6)
        items = folder.Items
        items.Sort("[ReceivedTime]", True)
        rows: List[Dict[str, str]] = []
        max_items = max(1, min(int(limit or 50), 200))
        for item in items:
            rows.append({
                "from": _json_safe(getattr(item, "SenderName", "") or getattr(item, "SenderEmailAddress", "")),
                "subject": _json_safe(getattr(item, "Subject", "")),
                "body": _json_safe(getattr(item, "Body", ""))[:200],
            })
            if len(rows) >= max_items:
                break
        return {"ok": True, "items": rows}
    except Exception as exc:
        return {"ok": False, "error": f"Outlook inbox read failed: {exc.__class__.__name__}"}
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _run_child(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    timeout = int(options.get("timeout") or DEFAULT_TIMEOUT)
    cmd = [sys.executable, "-m", "agent_ops.adapters.outlook_com", "--action", action]
    if action == "read_calendar":
        cmd.extend(["--days", str(int(options.get("days") or 7))])
    if action == "read_inbox":
        cmd.extend(["--limit", str(int(options.get("limit") or 50))])
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(CODE_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(cmd, cwd=str(CODE_ROOT), capture_output=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Outlook 응답 없음({timeout}s) — 보안 프롬프트가 떠 있는지 확인"}
    out = (result.stdout or b"").decode("utf-8", errors="replace").strip()
    if not out:
        return {"ok": False, "error": "Outlook adapter returned no JSON"}
    try:
        payload = json.loads(out.splitlines()[-1])
    except Exception:
        return {"ok": False, "error": "Outlook adapter JSON 파싱 실패"}
    return payload


def read_calendar(days: int = 7) -> Dict[str, Any]:
    return _run_child("read_calendar", {"days": days})


def read_inbox(limit: int = 50) -> Dict[str, Any]:
    return _run_child("read_inbox", {"limit": limit})


def _due_from_start(value: str) -> str:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:16] if " " in fmt else text[:10], fmt).strftime(fmt)
        except Exception:
            pass
    return text[:16] if text else ""


def sync_to_schedule(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    existing = {
        (str(item.get("title", "")), str(item.get("due", "")))
        for item in schedule_store.list_items("all")
    }
    added: List[Dict[str, Any]] = []
    skipped = 0
    for item in items:
        title = str(item.get("title") or "").strip()
        due = _due_from_start(str(item.get("start") or ""))
        if not title or not due:
            skipped += 1
            continue
        if (title, due) in existing:
            skipped += 1
            continue
        result = schedule_store.add(title, due, source="outlook")
        if result.get("ok"):
            added.append(result["item"])
            existing.add((title, result["item"]["due"]))
        else:
            skipped += 1
    return {"ok": True, "added": added, "skipped": skipped}


def send_mail(to: str, subject: str, body: str, allow_send: bool = False) -> Dict[str, Any]:
    risk = classify_risk("app.outlook.send_mail", str(to or ""), ROOT)
    if risk != "dangerous":
        return {"ok": False, "risk": risk, "error": "send_mail risk classification failed closed"}
    if not allow_send:
        return {"ok": False, "risk": "dangerous", "error": "send_mail은 기본 비노출입니다 — explicit approval 필요"}
    return {"ok": False, "risk": "dangerous", "error": "send_mail live execution is company validation pending"}


def execute(action: str, options: Dict[str, Any]) -> Dict[str, Any]:
    opts = options if isinstance(options, dict) else {}
    action_name = str(action or "")
    if action_name not in ACTIONS + INTERNAL_ACTIONS:
        return {"ok": False, "error": f"unknown action: {action_name}", "available_actions": list(ACTIONS)}
    if action_name == "read_calendar":
        return read_calendar(int(opts.get("days") or 7))
    if action_name == "sync_calendar":
        result = read_calendar(int(opts.get("days") or 7))
        if not result.get("ok"):
            return result
        return sync_to_schedule(list(result.get("items") or []))
    if action_name == "read_inbox":
        return read_inbox(int(opts.get("limit") or 50))
    if action_name == "send_mail":
        return send_mail(str(opts.get("to") or ""), str(opts.get("subject") or ""),
                         str(opts.get("body") or ""), allow_send=bool(opts.get("allow_send")))
    return {"ok": False, "error": f"unknown action: {action_name}", "available_actions": list(ACTIONS)}


def _main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--action", choices=("read_calendar", "read_inbox"), required=True)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    if args.action == "read_calendar":
        payload = _read_calendar_child(args.days)
    else:
        payload = _read_inbox_child(args.limit)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_main())
