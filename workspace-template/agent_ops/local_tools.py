# -*- coding: utf-8 -*-
"""Local tool implementations that model tool-calls dispatch to.

Every tool is confined to a workspace root: relative paths only, resolved
paths must stay inside the root (path-traversal attempts fail closed).
Encoding policy follows encoding_ops: new files are UTF-8 no BOM / LF,
existing files keep their BOM and newline style across edits.

Each tool returns a structured dict:
  ok=True  -> {"ok": True, ...tool-specific data}
  ok=False -> {"ok": False, "error": str, "root_cause_category": str}

root_cause_category values:
  path_escape / not_found / invalid_argument / already_exists /
  encoding_error / io_error
Never include secrets or gateway URLs in results: tools only touch local
workspace files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .encoding_ops import detect_style, edit_replace, read_text, write_text

MAX_READ_CHARS = 200_000
MAX_SEARCH_RESULTS = 200
MAX_SEARCH_FILES = 2_000


class ToolError(Exception):
    """Tool failure with a machine-readable root cause category."""

    def __init__(self, category: str, detail: str):
        super().__init__(detail)
        self.category = category


def _fail(category: str, detail: str) -> Dict[str, Any]:
    return {"ok": False, "error": detail, "root_cause_category": category}


def resolve_safe(root: Path, rel: Any) -> Path:
    """Resolve a model-supplied path inside the workspace root or raise."""
    if not isinstance(rel, str) or not rel.strip():
        raise ToolError("invalid_argument", "path must be a non-empty string")
    candidate = Path(rel)
    if candidate.is_absolute() or (len(rel) >= 2 and rel[1] == ":"):
        raise ToolError("path_escape", f"absolute path not allowed: {rel}")
    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ToolError("path_escape", f"path escapes workspace root: {rel}")
    return resolved


def tool_read_file(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_safe(root, args.get("path"))
    if not path.is_file():
        raise ToolError("not_found", f"file not found: {args.get('path')}")
    try:
        text, style = read_text(path)
    except UnicodeDecodeError as exc:
        raise ToolError("encoding_error", f"not valid UTF-8: {exc}")
    truncated = len(text) > MAX_READ_CHARS
    return {"ok": True, "path": args["path"], "content": text[:MAX_READ_CHARS],
            "truncated": truncated, "style": style}


def tool_write_file(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_safe(root, args.get("path"))
    content = args.get("content")
    if not isinstance(content, str):
        raise ToolError("invalid_argument", "content must be a string")
    # Existing file keeps its BOM/newline style; new file gets UTF-8 no BOM.
    style = detect_style(path) if path.is_file() else None
    write_text(path, content, style)
    return {"ok": True, "path": args["path"], "chars": len(content),
            "created": style is None, "style_preserved": style}


def tool_append_file(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_safe(root, args.get("path"))
    content = args.get("content")
    if not isinstance(content, str):
        raise ToolError("invalid_argument", "content must be a string")
    if path.is_file():
        text, style = read_text(path)
        write_text(path, text + content, style)
        created = False
    else:
        write_text(path, content)
        style, created = None, True
    return {"ok": True, "path": args["path"], "appended_chars": len(content),
            "created": created, "style_preserved": style}


def tool_replace_in_file(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_safe(root, args.get("path"))
    old, new = args.get("old"), args.get("new")
    if not isinstance(old, str) or not old or not isinstance(new, str):
        raise ToolError("invalid_argument", "old must be a non-empty string and new a string")
    if not path.is_file():
        raise ToolError("not_found", f"file not found: {args.get('path')}")
    result = edit_replace(path, old, new, int(args.get("count") or -1))
    if not result.get("ok"):
        raise ToolError("not_found", f"old text not found in {args.get('path')}")
    result["path"] = args["path"]
    return result


def tool_list_dir(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    path = resolve_safe(root, args.get("path") or ".")
    if not path.is_dir():
        raise ToolError("not_found", f"directory not found: {args.get('path') or '.'}")
    entries = [
        {"name": p.name, "type": "dir" if p.is_dir() else "file"}
        for p in sorted(path.iterdir(), key=lambda p: p.name)
    ]
    return {"ok": True, "path": args.get("path") or ".", "entries": entries}


def tool_search_files(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query:
        raise ToolError("invalid_argument", "query must be a non-empty string")
    base = resolve_safe(root, args.get("path") or ".")
    pattern = args.get("pattern") or "**/*"
    if not base.is_dir():
        raise ToolError("not_found", f"directory not found: {args.get('path') or '.'}")
    root_resolved = root.resolve()
    matches: List[Dict[str, Any]] = []
    scanned = 0
    for path in sorted(base.glob(pattern)):
        if not path.is_file() or scanned >= MAX_SEARCH_FILES:
            continue
        scanned += 1
        try:
            text = path.read_bytes().decode("utf-8-sig")
        except Exception:
            continue  # binary or non-UTF-8: skip silently
        for lineno, line in enumerate(text.splitlines(), 1):
            if query in line:
                matches.append({
                    "path": path.relative_to(root_resolved).as_posix(),
                    "line": lineno,
                    "text": line.strip()[:300],
                })
                if len(matches) >= MAX_SEARCH_RESULTS:
                    return {"ok": True, "query": query, "matches": matches, "truncated": True}
    return {"ok": True, "query": query, "matches": matches, "truncated": False}


def tool_run_diagnostic(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    """Lightweight workspace health check (no secrets, no network)."""
    root_resolved = root.resolve()
    writable = True
    try:
        probe = root_resolved / ".agentops_write_probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception:
        writable = False
    return {"ok": True, "workspace_exists": root_resolved.is_dir(), "writable": writable}
