# -*- coding: utf-8 -*-
"""Tool-call dispatch: normalized tool-calls -> actual local tool execution.

This closes the loop that lig_runtime left open: lig_runtime/toolcall_parser
produce normalized {"name", "arguments"} calls; this module validates them
against a registry, executes the matching local tool (local_tools), records
diagnostics, and cuts off repeated identical failures so a weak model cannot
spin forever on the same broken call.

Diagnostics (workspace-local, secret-free):
  <diag_dir>/tool-dispatch-last.json      last dispatch result
  <diag_dir>/tool-dispatch-history.jsonl  append-only dispatch log

run_agent_loop() is the minimal multi-turn harness:
  prompt -> call_llm -> parse tool-calls -> dispatch -> feed results back
  -> ... -> final text answer.
Transport is injectable, so the whole loop is testable offline with mocks;
real EXAONE/Qwen behavior remains company validation pending.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .lig_providers import DIAG_DIR
from .lig_runtime import call_llm
from .approval import classify_risk
from .audit import record as audit_record
from .local_tools import (
    ToolError,
    tool_append_file,
    tool_list_dir,
    tool_read_file,
    tool_replace_in_file,
    tool_run_diagnostic,
    tool_search_files,
    tool_write_file,
)

ToolFn = Callable[[Path, Dict[str, Any]], Dict[str, Any]]

# name -> (fn, required args, optional args, one-line description).
# Descriptions are deliberately short: weak models pick tools better with a
# hint, but long schemas eat their context and hurt call accuracy.
REGISTRY: Dict[str, Dict[str, Any]] = {
    "read_file":       {"fn": tool_read_file,       "required": ["path"],                 "optional": [],                    "description": "Read a text file"},
    "write_file":      {"fn": tool_write_file,      "required": ["path", "content"],      "optional": [],                    "description": "Create or overwrite a text file"},
    "append_file":     {"fn": tool_append_file,     "required": ["path", "content"],      "optional": [],                    "description": "Append text to an existing file"},
    "replace_in_file": {"fn": tool_replace_in_file, "required": ["path", "old", "new"],   "optional": ["count"],             "description": "Replace exact text inside a file"},
    "list_dir":        {"fn": tool_list_dir,        "required": [],                       "optional": ["path"],              "description": "List files in a directory"},
    "search_files":    {"fn": tool_search_files,    "required": ["query"],                "optional": ["path", "pattern"],   "description": "Search text across files"},
    "run_diagnostic":  {"fn": tool_run_diagnostic,  "required": [],                       "optional": [],                    "description": "Check workspace health"},
}

_PARAM_DESCRIPTIONS = {
    "path": "workspace-relative file or directory path",
    "content": "text content (UTF-8)",
    "old": "exact text to replace",
    "new": "replacement text",
    "count": "max replacements (default: all)",
    "query": "substring to search for",
    "pattern": "glob pattern, e.g. **/*.md",
}


def tool_definitions() -> List[Dict[str, Any]]:
    """OpenAI-style function definitions for the registry, for the LLM payload."""
    defs = []
    for name, spec in REGISTRY.items():
        props = {
            arg: {"type": "integer" if arg == "count" else "string",
                  "description": _PARAM_DESCRIPTIONS.get(arg, "")}
            for arg in spec["required"] + spec["optional"]
        }
        defs.append({
            "type": "function",
            "function": {
                "name": name,
                "description": spec.get("description", ""),
                "parameters": {"type": "object", "properties": props, "required": spec["required"]},
            },
        })
    return defs


def _call_signature(call: Dict[str, Any]) -> str:
    try:
        return call["name"] + ":" + json.dumps(call.get("arguments", {}), sort_keys=True, ensure_ascii=False)
    except Exception:
        return call.get("name", "?") + ":<unserializable>"


class ToolDispatcher:
    """Validates and executes normalized tool calls inside a workspace root."""

    def __init__(self, workspace_root: Path, diag_dir: Optional[Path] = None,
                 max_repeat_failures: int = 2):
        self.root = Path(workspace_root)
        self.diag_dir = Path(diag_dir) if diag_dir else DIAG_DIR
        self.max_repeat_failures = max_repeat_failures
        self._failure_counts: Dict[str, int] = {}

    def dispatch(self, call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one normalized {"name", "arguments"} call; never raises."""
        name = call.get("name", "")
        args = call.get("arguments")
        result = self._execute(name, args)
        result["tool"] = name
        sig = _call_signature(call)
        if not result["ok"]:
            self._failure_counts[sig] = self._failure_counts.get(sig, 0) + 1
        self._record(call, result)
        self._audit(call, result)
        return result

    def repeated_failure(self, call: Dict[str, Any]) -> bool:
        """True when this exact call already failed max_repeat_failures times."""
        return self._failure_counts.get(_call_signature(call), 0) >= self.max_repeat_failures

    def _execute(self, name: str, args: Any) -> Dict[str, Any]:
        spec = REGISTRY.get(name)
        if spec is None:
            return {"ok": False, "error": f"unknown tool: {name}",
                    "root_cause_category": "unknown_tool"}
        # Weak models sometimes emit arguments as a JSON string; normalize.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                return {"ok": False, "error": "arguments is not valid JSON",
                        "root_cause_category": "invalid_argument"}
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "arguments must be a JSON object",
                    "root_cause_category": "invalid_argument"}
        missing = [a for a in spec["required"] if a not in args or args[a] is None]
        if missing:
            return {"ok": False, "error": f"missing required arguments: {', '.join(missing)}",
                    "root_cause_category": "missing_argument"}
        try:
            return spec["fn"](self.root, args)
        except ToolError as exc:
            return {"ok": False, "error": str(exc), "root_cause_category": exc.category}
        except Exception as exc:
            return {"ok": False, "error": repr(exc)[:300], "root_cause_category": "io_error"}

    def _record(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "tool": call.get("name", ""),
            "arguments": call.get("arguments", {}),
            "ok": result.get("ok", False),
            "root_cause_category": result.get("root_cause_category", ""),
            "error": result.get("error", ""),
        }
        try:
            self.diag_dir.mkdir(parents=True, exist_ok=True)
            (self.diag_dir / "tool-dispatch-last.json").write_text(
                json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            with (self.diag_dir / "tool-dispatch-history.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # diagnostics must never break dispatch

    def _audit(self, call: Dict[str, Any], result: Dict[str, Any]) -> None:
        try:
            args = call.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            target = args.get("path") or args.get("target") or ""
            name = call.get("name", "")
            risk = classify_risk(name, str(target), self.root)
            audit_record({
                "kind": "tool",
                "name": name,
                "target": target,
                "risk": risk,
                "verdict": "approved" if result.get("ok") else "denied",
                "detail": result.get("root_cause_category") or ("ok" if result.get("ok") else result.get("error", "")),
            })
        except Exception:
            pass  # audit must never break dispatch


AGENT_SYSTEM_PROMPT = (
    "You are a local file agent operating inside a workspace. "
    "Use the provided tools to complete the task. All paths are relative to "
    "the workspace root. When the task is complete, reply with a plain-text "
    "summary and no tool call."
)


def run_agent_loop(
    prompt: str,
    workspace_root: Path,
    env: Optional[Dict[str, str]] = None,
    transport: Optional[Callable[..., Dict[str, Any]]] = None,
    max_turns: int = 10,
    diag_dir: Optional[Path] = None,
    capability_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Minimal tool-use agent loop over call_llm + ToolDispatcher.

    Returns {ok, outcome, final_content, turns, tool_results, llm_outcome}.
    outcome: completed | tool_loop_cutoff | llm_failed | max_turns_exceeded
    """
    dispatcher = ToolDispatcher(workspace_root, diag_dir=diag_dir)
    tools = tool_definitions()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    tool_results: List[Dict[str, Any]] = []
    outcome = "max_turns_exceeded"
    final_content = ""
    turns = 0

    for _ in range(max_turns):
        turns += 1
        llm = call_llm(messages, tools=tools, env=env, transport=transport,
                       diag_dir=diag_dir, capability_ids=capability_ids)
        if not llm["ok"]:
            outcome = "llm_failed"
            final_content = llm.get("content", "")
            break
        calls = llm.get("tool_calls") or []
        if not calls:
            outcome = "completed"
            final_content = llm.get("content", "")
            break
        call_ids = ["call_%d_%d" % (turns, i + 1) for i in range(len(calls))]
        messages.append({"role": "assistant", "content": llm.get("content", "") or "",
                         "tool_calls": [{"id": call_ids[i], "type": "function", "function": {
                             "name": c["name"],
                             "arguments": json.dumps(c.get("arguments", {}), ensure_ascii=False),
                         }} for i, c in enumerate(calls)]})
        cutoff = False
        for i, call in enumerate(calls):
            if dispatcher.repeated_failure(call):
                outcome = "tool_loop_cutoff"
                final_content = (f"Aborted: tool call {call.get('name')} failed repeatedly "
                                 "with identical arguments.")
                cutoff = True
                break
            result = dispatcher.dispatch(call)
            tool_results.append(result)
            messages.append({"role": "tool", "tool_call_id": call_ids[i],
                             "name": call.get("name", ""),
                             "content": json.dumps(result, ensure_ascii=False)})
        if cutoff:
            break

    result = {
        "ok": outcome == "completed",
        "outcome": outcome,
        "final_content": final_content,
        "turns": turns,
        "tool_results": tool_results,
    }
    try:
        diag = Path(diag_dir) if diag_dir else DIAG_DIR
        diag.mkdir(parents=True, exist_ok=True)
        safe = dict(result)
        safe["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        safe["tool_results"] = [
            {k: v for k, v in r.items() if k != "content"} for r in tool_results
        ]
        (diag / "agent-loop-last.json").write_text(
            json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return result
