# -*- coding: utf-8 -*-
"""Approval gate helpers for planned work execution.

The gate is conservative by design: anything that writes outside the workspace,
deletes, mutates schedules, or executes an app/adapter is dangerous and needs
explicit current-session approval unless the caller passes assume_yes=True.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

SAFE_ACTIONS = {"read_file", "list_dir", "search_files", "run_diagnostic", "create_file"}
WRITE_ACTIONS = {"write_file", "append_file", "replace_in_file"}
DANGEROUS_ACTIONS = {
    "delete_file",
    "remove_file",
    "delete_dir",
    "adapter_execute",
    "execute_adapter",
    "run_adapter",
    "app_execute",
    "schedule_delete",
    "schedule_remove",
    "schedule_modify",
    "schedule_update",
}


def _resolve_target(target: str, workspace_root: Path) -> Path:
    root = Path(workspace_root).resolve()
    raw = str(target or ".")
    path = Path(raw)
    if path.is_absolute() or (len(raw) >= 2 and raw[1] == ":"):
        return path.resolve()
    return (root / path).resolve()


def _inside_workspace(path: Path, workspace_root: Path) -> bool:
    root = Path(workspace_root).resolve()
    try:
        return path == root or root in path.parents
    except Exception:
        return False


def classify_risk(action_kind: str, target: str, workspace_root: Path) -> str:
    """Classify an intended action as safe, caution, or dangerous."""
    action = (action_kind or "").strip().lower()
    resolved = _resolve_target(target, workspace_root)
    inside = _inside_workspace(resolved, workspace_root)
    if action in DANGEROUS_ACTIONS or action.startswith("adapter.") or action.startswith("app."):
        return "dangerous"
    if action.startswith("schedule.") and action not in {"schedule.add", "schedule.list", "schedule.today", "schedule.week"}:
        return "dangerous"
    if not inside and action not in {"read_file", "list_dir", "search_files"}:
        return "dangerous"
    if action in {"read_file", "list_dir", "search_files", "run_diagnostic"}:
        return "safe" if inside else "dangerous"
    if action in {"write_file", "create_file"}:
        if not inside:
            return "dangerous"
        return "caution" if resolved.exists() else "safe"
    if action in {"append_file", "replace_in_file"} or action in WRITE_ACTIONS:
        if not inside:
            return "dangerous"
        return "caution" if resolved.exists() else "safe"
    return "dangerous"


def _describe_item(item: Dict[str, Any]) -> str:
    kind = item.get("action_kind") or item.get("kind") or item.get("name") or "action"
    target = item.get("target") or item.get("path") or ""
    risk = item.get("risk") or "unknown"
    if target:
        return f"- [{risk}] {kind}: {Path(str(target)).name or target}"
    return f"- [{risk}] {kind}"


def request_approval(
    items: Iterable[Dict[str, Any]],
    assume_yes: bool = False,
    input_fn: Callable[[str], str] = input,
) -> Dict[str, Any]:
    """Ask for approval when dangerous items are present."""
    item_list: List[Dict[str, Any]] = list(items)
    dangerous = [item for item in item_list if item.get("risk") == "dangerous"]
    if not dangerous:
        return {"approved": True, "mode": "auto", "dangerous_count": 0}
    if assume_yes:
        return {"approved": True, "mode": "auto", "dangerous_count": len(dangerous)}
    print("Dangerous actions require approval:")
    for item in dangerous:
        print(_describe_item(item))
    answer = (input_fn("Proceed? [y/N] ") or "").strip().lower()
    if answer in {"y", "yes"}:
        return {"approved": True, "mode": "interactive", "dangerous_count": len(dangerous)}
    return {"approved": False, "mode": "denied", "dangerous_count": len(dangerous)}
