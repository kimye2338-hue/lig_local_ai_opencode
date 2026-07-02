# -*- coding: utf-8 -*-
"""Encoding-aware file helpers for Korean Windows environments.

Policy (see FABLE5 handoff §15):
  - New files: UTF-8 without BOM, unless caller opts in.
  - Editing existing files: preserve the file's BOM style and newline style.
    (safe_file_writer.atomic_write always strips BOM/CRLF — use these helpers
    when the original style must survive an edit.)
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

BOM = "﻿"
BOM_BYTES = b"\xef\xbb\xbf"


def detect_style(path: Path) -> Dict[str, Any]:
    """Detect BOM and dominant newline style without decoding errors."""
    raw = path.read_bytes()
    has_bom = raw.startswith(BOM_BYTES)
    crlf = raw.count(b"\r\n")
    lf_only = raw.count(b"\n") - crlf
    newline = "crlf" if crlf >= lf_only and crlf > 0 else "lf"
    return {"bom": has_bom, "newline": newline}


def read_text(path: Path) -> Tuple[str, Dict[str, Any]]:
    """Read UTF-8 text (BOM-tolerant); returns (text, style) for later rewrite."""
    style = detect_style(path)
    text = path.read_bytes().decode("utf-8-sig")
    return text, style


def write_text(path: Path, text: str, style: Dict[str, Any] | None = None) -> None:
    """Atomic write honoring the given style. Default: UTF-8 no BOM, LF."""
    style = style or {"bom": False, "newline": "lf"}
    normalized = text.replace("\r\n", "\n")
    if style.get("newline") == "crlf":
        normalized = normalized.replace("\n", "\r\n")
    data = (BOM_BYTES if style.get("bom") else b"") + normalized.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass


def edit_replace(path: Path, old: str, new: str, count: int = -1) -> Dict[str, Any]:
    """Replace text in a file, preserving its BOM and newline style."""
    text, style = read_text(path)
    if old not in text:
        return {"ok": False, "error": "old text not found", "path": str(path)}
    replaced = text.replace(old, new, count if count > 0 else -1)
    write_text(path, replaced, style)
    return {"ok": True, "path": str(path), "style_preserved": style,
            "replacements": text.count(old) if count <= 0 else min(count, text.count(old))}
