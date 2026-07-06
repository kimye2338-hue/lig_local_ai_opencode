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
_BROWSER_HINT = (" — 디버그 크롬이 필요합니다: launch\\chrome-debug.bat 로 크롬을 연 뒤 다시 시도"
                 " (이미 떠 있는 일반 크롬 창은 보이지 않습니다)")

_BROWSER_OPTION_KEYS = (
    "url", "tab", "selector", "text", "index", "timeout", "max_length",
    "max_text_length", "max_html_length", "limit", "filename", "wait_seconds",
    "load_timeout", "render_timeout", "output_dir", "max_clicks",
    "include_clickables", "value", "enter",
)


def tool_browse_tabs(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    from .adapters import browser_cdp
    res = browser_cdp.execute("list_tabs", {})
    if not res.get("ok"):
        return {"ok": False, "error": str(res.get("error", "")) + _BROWSER_HINT,
                "root_cause_category": "browser_unavailable"}
    return {"ok": True, "data": res.get("data", {})}


def tool_read_web_page(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    from .adapters import browser_cdp
    url = str(args.get("url") or "")
    tab = args.get("tab")
    if not url and tab in (None, ""):
        return {"ok": False, "error": "url 또는 tab 중 하나는 필요합니다",
                "root_cause_category": "missing_argument"}
    opts: Dict[str, Any] = {}
    if tab not in (None, ""):
        opts["tab"] = tab
    if url:
        opened = browser_cdp.execute("open_url", {"url": url, **opts})
        if not opened.get("ok"):
            return {"ok": False, "error": str(opened.get("error", "")) + _BROWSER_HINT,
                    "root_cause_category": "browser_unavailable"}
    snap = browser_cdp.execute("snapshot", {**opts, "max_text_length": int(args.get("max_length") or 4000),
                                            "include_clickables": False})
    if not snap.get("ok"):
        # Compatibility fallback for older local adapters.
        title = browser_cdp.execute("get_title", dict(opts))
        text = browser_cdp.execute("extract_text", {**opts, "max_length": int(args.get("max_length") or 4000)})
        if not text.get("ok"):
            return {"ok": False, "error": str(text.get("error", snap.get("error", ""))) + _BROWSER_HINT,
                    "root_cause_category": "browser_unavailable"}
        return {"ok": True, "data": {"title": (title.get("data") or {}).get("title", ""),
                                      "url": url,
                                      "text": (text.get("data") or {}).get("text", ""),
                                      "truncated": (text.get("data") or {}).get("truncated", False)}}
    data = snap.get("data") or {}
    return {"ok": True, "data": {"title": data.get("title", ""),
                                  "url": data.get("url") or url,
                                  "text": data.get("text", ""),
                                  "truncated": data.get("text_truncated", False)}}


def tool_browser_action(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    from .adapters import browser_cdp
    action = str(args.get("action") or "")
    if not action:
        return {"ok": False, "error": "action is required", "root_cause_category": "missing_argument"}
    if action not in getattr(browser_cdp, "ACTIONS", ()):  # do not let model invent arbitrary adapter calls
        return {"ok": False,
                "error": "unsupported browser action: %s; available=%s" % (action, ", ".join(browser_cdp.ACTIONS)),
                "root_cause_category": "invalid_argument"}
    opts = {k: v for k, v in args.items() if k in _BROWSER_OPTION_KEYS and v not in (None, "")}
    res = browser_cdp.execute(action, opts)
    if not res.get("ok"):
        return {"ok": False, "error": str(res.get("error", "")) + _BROWSER_HINT,
                "root_cause_category": "browser_unavailable"}
    return {"ok": True, "data": res.get("data", {})}


def _browser_tool(action: str) -> ToolFn:
    def run(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
        return tool_browser_action(root, {"action": action, **args})
    return run


def tool_project_info(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    """현재 폴더 프로필/전역 기억 진단 — 모델이 자기 컨텍스트 출처를 확인."""
    from .project_profile import profile_diagnostics
    return {"ok": True, "data": profile_diagnostics()}


def tool_remember(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    """전역 기억에 교훈/선호를 남긴다 — 다음 작업부터 자동 recall 주입."""
    text = str(args.get("note") or args.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "note is required", "root_cause_category": "missing_argument"}
    title = str(args.get("title") or "").strip() or text[:60]
    from .memory_manager import add_memory_event, extract_keywords
    item = add_memory_event("lesson", title, text, status="active",
                            priority="normal", source="agent",
                            tags=extract_keywords(text)[:8])
    return {"ok": True, "data": {"id": item.get("id"), "title": title}}


REGISTRY: Dict[str, Dict[str, Any]] = {
    "read_file":       {"fn": tool_read_file,       "required": ["path"],                 "optional": [],                    "description": "Read a text file"},
    "write_file":      {"fn": tool_write_file,      "required": ["path", "content"],      "optional": [],                    "description": "Create or overwrite a text file"},
    "append_file":     {"fn": tool_append_file,     "required": ["path", "content"],      "optional": [],                    "description": "Append text to an existing file"},
    "replace_in_file": {"fn": tool_replace_in_file, "required": ["path", "old", "new"],   "optional": ["count"],             "description": "Replace exact text inside a file"},
    "list_dir":        {"fn": tool_list_dir,        "required": [],                       "optional": ["path"],              "description": "List files in a directory"},
    "search_files":    {"fn": tool_search_files,    "required": ["query"],                "optional": ["path", "pattern"],   "description": "Search text across files"},
    "run_diagnostic":  {"fn": tool_run_diagnostic,  "required": [],                       "optional": [],                    "description": "Check workspace health"},
    "browse_tabs":     {"fn": tool_browse_tabs,     "required": [],                       "optional": [],                    "description": "List open Chrome tabs (needs debug Chrome)"},
    "read_web_page":   {"fn": tool_read_web_page,   "required": [],                       "optional": ["url", "tab", "max_length"], "description": "Read rendered page text: url to open, or tab(index/title/url)"},
    "browser_action":  {"fn": tool_browser_action,  "required": ["action"],               "optional": list(_BROWSER_OPTION_KEYS), "description": "Advanced Chrome CDP action: new_tab/select_tab/snapshot/find_clickables/click/fill/screenshot/wait_for_selector/spa_map"},
    "new_tab":         {"fn": _browser_tool("new_tab"),          "required": [], "optional": ["url"], "description": "Open a new debug Chrome tab"},
    "snapshot":        {"fn": _browser_tool("snapshot"),         "required": [], "optional": ["tab", "max_length", "max_text_length", "max_html_length"], "description": "Snapshot rendered SPA page text/html"},
    "find_clickables": {"fn": _browser_tool("find_clickables"),  "required": [], "optional": ["tab", "limit"], "description": "List clickable page elements"},
    "click":           {"fn": _browser_tool("click"),            "required": [], "optional": ["tab", "selector", "text", "index", "wait_seconds"], "description": "Click page element by selector/text/index"},
    "screenshot":      {"fn": _browser_tool("screenshot"),       "required": [], "optional": ["tab", "filename"], "description": "Capture current page screenshot"},
    "wait_for_selector":{"fn": _browser_tool("wait_for_selector"),"required": [], "optional": ["tab", "selector", "text", "timeout"], "description": "Wait until selector/text appears"},
    "select_tab":      {"fn": _browser_tool("select_tab"),       "required": [], "optional": ["tab", "index"], "description": "Activate an open debug Chrome tab"},
    "spa_map":         {"fn": _browser_tool("spa_map"),          "required": [], "optional": ["tab", "output_dir", "max_clicks", "wait_seconds"], "description": "Explore current SPA menu/clickable map"},
    "project_info":    {"fn": tool_project_info,  "required": [],               "optional": [],                    "description": "Show folder profile + global memory paths"},
    "remember":        {"fn": tool_remember,      "required": ["note"],         "optional": ["title"],             "description": "Save a lesson to global memory"},
}

_PARAM_DESCRIPTIONS = {
    "path": "relative path",
    "content": "UTF-8 text",
    "title": "memory title",
    "note": "text to remember",
    "old": "exact text to replace",
    "new": "replacement text",
    "count": "max replacements",
    "query": "search text",
    "pattern": "glob, e.g. **/*.md",
    "action": "browser action name",
    "url": "URL",
    "tab": "tab index or title/url substring",
    "selector": "CSS selector",
    "text": "visible text substring",
    "index": "clickable or tab index",
    "timeout": "seconds",
    "max_length": "max text length",
    "max_text_length": "max text length",
    "max_html_length": "max html length; 0 disables html",
    "limit": "maximum item count",
    "filename": "output filename",
    "wait_seconds": "seconds to wait after click",
    "load_timeout": "page load timeout seconds",
    "output_dir": "output directory",
    "max_clicks": "maximum clicks to explore",
    "include_clickables": "true/false",
}

_INT_PARAMS = {"count", "index", "timeout", "max_length", "max_text_length", "max_html_length", "max_clicks", "limit"}


def tool_definitions() -> List[Dict[str, Any]]:
    """OpenAI-style function definitions for the registry, for the LLM payload."""
    defs = []
    for name, spec in REGISTRY.items():
        props = {
            arg: {"type": "integer" if arg in _INT_PARAMS else "string",
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
            target = args.get("path") or args.get("target") or args.get("url") or args.get("selector") or ""
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
    "You are a local file and browser agent operating inside a workspace. "
    "Use the provided tools to complete the task. All paths are relative to "
    "the workspace root. For browser tasks, use browse_tabs/read_web_page first, "
    "then snapshot/find_clickables/click/wait_for_selector/screenshot/spa_map as needed. "
    "Copy filenames exactly. When the task is complete, reply with a plain-text "
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
    # 복리 기억의 쐐기돌: 축적된 규칙/교훈을 '기계적으로' 주입한다.
    # 페르소나가 recall을 잊어도 같은 실수를 반복하지 않도록 — 선의가 아닌 구조.
    # 주입 순서(제품 문서 §6.3): 전역 기억 → 폴더 프로필(기억/페르소나/규칙) → 작업.
    inserts: List[Dict[str, Any]] = []
    try:
        from .memory_manager import extract_keywords, format_recall_for_prompt, pinned_recall, recall
        keywords = extract_keywords(prompt)
        # 회상 보장: 사용자 규칙 + 최근 실수는 키워드가 안 맞아도 항상 주입,
        # 키워드 매칭분은 그 위에 추가 (id 로 중복 제거).
        pinned = pinned_recall(limit=5)
        matched = recall(keywords=keywords, limit=5)
        seen_ids = {r.get("id") for r in pinned}
        mem = pinned + [r for r in matched if r.get("id") not in seen_ids]
        if mem:
            inserts.append({"role": "system",
                            "content": "이전에 축적된 사용자 규칙/교훈 — 반드시 반영:\n"
                                       + format_recall_for_prompt(mem[:8])})
        # 복리 recall: 개별 사건보다 '주제 페이지'(증류된 지식)가 강하다.
        # 기록이 쌓일수록 같은 주제 발췌가 저절로 풍부해진다 (LLM Wiki 층).
        from .wiki_manager import recall_pages
        pages = recall_pages(keywords, limit=1)
        for page in pages:
            inserts.append({"role": "system",
                            "content": f"축적된 주제 지식(위키 '{page['topic']}') — 참고:\n"
                                       + page["excerpt"]})
    except Exception:  # noqa: BLE001 - 기억 주입 실패가 작업을 막으면 안 된다
        pass
    try:
        from .project_profile import format_context_for_prompt, load_project_context
        project = format_context_for_prompt(load_project_context())
        if project:
            inserts.append({"role": "system", "content": project})
    except Exception:  # noqa: BLE001 - 프로필 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 공식 API 근거 주입: 작업이 특정 소프트웨어(Excel/HWP/CAD 등)를 가리키면
        # 그 소프트웨어의 공식 문서 발췌를 넣어 환각 API 대신 실제 명령으로 코딩하게 한다.
        from .api_reference import context_for_prompt as _api_ctx
        api_ref = _api_ctx(prompt)
        if api_ref:
            inserts.append({"role": "system", "content": api_ref})
    except Exception:  # noqa: BLE001 - API 참조 주입 실패도 작업을 막으면 안 된다
        pass
    for offset, msg in enumerate(inserts):
        messages.insert(1 + offset, msg)
    # 비서펫(오버레이) 라이브 상태 — 실패해도 작업을 막지 않는다.
    try:
        from .status_writer import publish_status
        publish_status("working", message="에이전트 작업 시작", task=prompt[:60])
    except Exception:  # noqa: BLE001
        pass
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
        from .status_writer import publish_event
        status = {"completed": "done", "llm_failed": "error",
                  "tool_loop_cutoff": "needs_user",
                  "max_turns_exceeded": "needs_user"}.get(outcome, "done")
        publish_event("AGENT_" + outcome.upper(), status=status,
                      message=(final_content or outcome)[:120], task=prompt[:60])
    except Exception:  # noqa: BLE001
        pass
    # 시행착오의 기계적 학습: 루프가 비정상 종료하면 그 패턴을 기억에 남긴다.
    # 다음 작업에서 pinned_recall 이 이 교훈을 '반드시' 주입한다.
    if outcome in ("tool_loop_cutoff", "llm_failed", "max_turns_exceeded"):
        try:
            from .memory_manager import record_self_error
            record_self_error(f"에이전트 루프 {outcome}",
                              (final_content or outcome)[:200], task=prompt[:80])
        except Exception:  # noqa: BLE001
            pass
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
