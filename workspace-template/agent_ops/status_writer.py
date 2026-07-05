# -*- coding: utf-8 -*-
"""Status writer for OpenCodeLIG companion UIs."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def state_dir() -> Path:
    return Path(os.environ.get("LIG_STATE_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "state"))


def _read_current(path: Path) -> Dict[str, Any]:
    try:
        if path.exists() and path.is_file():
            return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except Exception:
        pass
    return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def publish_status(status: str,
                   message: str = "",
                   task: str = "",
                   progress: Optional[int] = None,
                   needs_user: Optional[bool] = None,
                   run_id: str = "",
                   data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Write current_status.json for the hamster overlay. Never raises."""
    path = state_dir() / "current_status.json"
    payload = _read_current(path)
    payload.update({"schema": 1, "app": "OpenCodeLIG", "status": str(status or "idle"), "last_update": now_iso()})
    if message:
        payload["message"] = str(message)
    if task:
        payload["task"] = str(task)
    if progress is not None:
        try:
            payload["progress"] = max(0, min(100, int(progress)))
        except Exception:
            pass
    if needs_user is not None:
        payload["needs_user"] = bool(needs_user)
    if run_id:
        payload["run_id"] = str(run_id)
    if data:
        payload["data"] = data
    try:
        _write_json(path, payload)
    except Exception:
        pass
    return payload


def publish_event(kind: str,
                  message: str = "",
                  status: str = "",
                  task: str = "",
                  run_id: str = "",
                  level: str = "info",
                  data: Optional[Dict[str, Any]] = None,
                  update_status: bool = True) -> Dict[str, Any]:
    """Append one line to events.ndjson and optionally refresh current status."""
    event: Dict[str, Any] = {
        "timestamp": now_iso(),
        "kind": str(kind or "event"),
        "level": str(level or "info"),
        "message": str(message or ""),
        "status": str(status or ""),
        "task": str(task or ""),
    }
    if run_id:
        event["run_id"] = str(run_id)
    if data:
        event["data"] = data
    try:
        path = state_dir() / "events.ndjson"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    if update_status and (status or message or task):
        publish_status(status or "working", message=message, task=task, run_id=run_id, data=data)
    return event
