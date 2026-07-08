# -*- coding: utf-8 -*-
"""Append-only, secret-safe audit log."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

AUDIT_DIR = Path(os.environ.get("LIG_AUDIT_DIR") or (Path.home() / "OpenCodeLIG_USERDATA" / "audit"))
AUDIT_FILE = "audit.jsonl"
SECRET_MARKERS = ("sk-", "api_key", "apikey", "authorization", "bearer ", "secret", "token", "password")


def _basename(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    return Path(text.replace("\\", "/")).name[:120]


def _clean_detail(value: Any) -> str:
    text = str(value or "")
    lowered = text.lower()
    if any(marker in lowered for marker in SECRET_MARKERS):
        return "[REDACTED]"
    return text.replace("\r", " ").replace("\n", " ")[:80]


def _clean_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ts": event.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_id": str(event.get("run_id") or ""),
        "task": str(event.get("task") or "")[:80],
        "kind": str(event.get("kind") or ""),
        "name": str(event.get("name") or "")[:80],
        "target": _basename(event.get("target")),
        "risk": str(event.get("risk") or ""),
        "verdict": str(event.get("verdict") or ""),
        "detail": _clean_detail(event.get("detail")),
    }


def _max_bytes() -> int:
    try:
        return int(os.environ.get("LIG_AUDIT_MAX_BYTES", str(10 * 1024 * 1024)))
    except Exception:
        return 10 * 1024 * 1024


def _rotate_if_needed(path: Path) -> None:
    try:
        if not path.exists() or path.stat().st_size < _max_bytes():
            return
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup = path.with_name(f"audit_{stamp}.jsonl.bak")
        if backup.exists():
            backup = path.with_name(f"audit_{stamp}_{os.getpid()}.jsonl.bak")
        path.rename(backup)
    except Exception as exc:
        # Rotation failure must not stop recording; warn and continue appending.
        print(f"[audit] WARNING: failed to rotate audit log: {exc}", file=sys.stderr)


def record(event: Dict[str, Any]) -> bool:
    """Append one audit event.

    Returns True on success, False on failure. Failures warn clearly to stderr
    but never raise — audit failure must never crash the caller.
    """
    try:
        audit_dir = Path(os.environ.get("LIG_AUDIT_DIR") or AUDIT_DIR)
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = audit_dir / AUDIT_FILE
        _rotate_if_needed(audit_path)
        with audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(_clean_event(event), ensure_ascii=False) + "\n")
        return True
    except Exception as exc:
        print(f"[audit] WARNING: failed to write audit record: {exc}", file=sys.stderr)
        return False
