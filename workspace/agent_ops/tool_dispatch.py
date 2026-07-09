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
import re
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


def _adapter_pending_hint(adapter_id: str) -> str:
    """앱 미검증/미설치 시 붙일 안내 — 어떤 앱/반입이 필요한지 알려준다."""
    try:
        from .adapters import ADAPTERS
        spec = ADAPTERS.get(adapter_id, {})
        note = spec.get("pending") or "; ".join(spec.get("requires", []))
        return (" — " + note) if note else ""
    except Exception:  # noqa: BLE001
        return ""


def _normalize_adapter_result(adapter_id: str, res: Dict[str, Any]) -> Dict[str, Any]:
    if res.get("ok"):
        return {"ok": True, "data": res.get("data", {k: v for k, v in res.items() if k != "ok"})}
    return {"ok": False,
            "error": str(res.get("error", "")) + _adapter_pending_hint(adapter_id),
            "root_cause_category": "app_unavailable"}


def _action_adapter_tool(adapter_id: str, loader: Callable) -> ToolFn:
    """action형 어댑터(execute(action, options))를 도구로 감싼다.

    loader()는 실행 시점에 (execute, actions)를 지연 반환한다 — 모듈 로드 때
    COM/무거운 의존을 끌어오지 않는다. action은 ACTIONS로 검증(임의 호출 금지),
    앱/COM 미설치는 어댑터가 우아하게 ok=False를 돌려주므로 크래시 없이 정규화."""
    def run(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
        action = str(args.get("action") or "")
        try:
            execute, actions = loader()
        except Exception as exc:  # noqa: BLE001 - 어댑터 import 자체 실패도 우아하게
            return {"ok": False, "error": "%s 어댑터 로드 실패: %r%s" % (adapter_id, exc, _adapter_pending_hint(adapter_id)),
                    "root_cause_category": "app_unavailable"}
        valid = tuple(actions)
        if not action:
            return {"ok": False, "error": "action is required; available=%s" % ", ".join(valid),
                    "root_cause_category": "missing_argument"}
        if action not in valid:
            return {"ok": False,
                    "error": "unsupported %s action: %s; available=%s" % (adapter_id, action, ", ".join(valid)),
                    "root_cause_category": "invalid_argument"}
        opts = {k: v for k, v in args.items() if k != "action" and v not in (None, "")}
        try:
            res = execute(action, opts)
        except Exception as exc:  # noqa: BLE001 - 어댑터 예외가 에이전트 루프를 죽이지 않게
            return {"ok": False, "error": ("%s 어댑터 오류: %r" % (adapter_id, exc))[:200],
                    "root_cause_category": "app_unavailable"}
        return _normalize_adapter_result(adapter_id, res)
    return run


def _path_adapter_tool(adapter_id: str, loader: Callable, path_key: str) -> ToolFn:
    """경로형 어댑터(execute(script_path, options))를 도구로 감싼다."""
    def run(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
        sp = str(args.get(path_key) or args.get("path") or "")
        if not sp:
            return {"ok": False, "error": "%s is required" % path_key,
                    "root_cause_category": "missing_argument"}
        try:
            execute = loader()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "%s 어댑터 로드 실패: %r%s" % (adapter_id, exc, _adapter_pending_hint(adapter_id)),
                    "root_cause_category": "app_unavailable"}
        opts = {k: v for k, v in args.items() if k not in (path_key, "path") and v not in (None, "")}
        try:
            res = execute(sp, opts)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": ("%s 어댑터 오류: %r" % (adapter_id, exc))[:200],
                    "root_cause_category": "app_unavailable"}
        return _normalize_adapter_result(adapter_id, res)
    return run


def _load_excel():
    from .adapters import _office_execute, excel_com, office_convert
    return _office_execute, tuple(excel_com.ACTIONS) + tuple(office_convert.ACTIONS)


def _load_outlook():
    from .adapters import outlook_com
    return outlook_com.execute, outlook_com.ACTIONS


def _load_hwp():
    from .adapters import hwp_com
    return hwp_com.execute, hwp_com.ACTIONS


def _load_solidworks():
    from .adapters import solidworks_com
    return solidworks_com.execute, solidworks_com.ACTIONS


def _load_ocr():
    from .adapters import ocr_screen
    return ocr_screen.execute, tuple(ocr_screen.ACTIONS)


def _load_desktop_ui():
    from .adapters import desktop_ui
    return desktop_ui.execute, tuple(desktop_ui.ACTIONS)


def tool_autocad_run(root: Path, args: Dict[str, Any]) -> Dict[str, Any]:
    """AutoCAD accoreconsole 배치: 도면(.dwg) 사본에 스크립트(.scr) 실행."""
    dwg = str(args.get("dwg_path") or "")
    scr = str(args.get("scr_path") or "")
    if not dwg or not scr:
        return {"ok": False, "error": "dwg_path 와 scr_path 가 모두 필요합니다",
                "root_cause_category": "missing_argument"}
    try:
        from .adapters import autocad_batch
        res = autocad_batch.execute(dwg, scr, {})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "autocad 어댑터 오류: %r" % exc,
                "root_cause_category": "app_unavailable"}
    return _normalize_adapter_result("autocad", res)


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
    # --- 앱 어댑터 직접 호출(전체 노출). 앱/COM 미설치 시 우아하게 실패. 스키마는
    # 약한 모델 정확도 위해 타이트하게 — 미선언 옵션도 런타임은 통과시킨다. ---
    "excel_app":       {"fn": _action_adapter_tool("office", _load_excel),       "required": ["action"], "optional": ["path", "range", "bas_path", "sheet", "values", "out_path", "spec", "macro"], "description": "Excel/Word/PPT. read_range:path,range/write_range:path,range,values/run_macro_file:path,bas_path/md_to_docx:path,out_path/spec_to_pptx:path,spec/open_copy:path/save/close"},
    "outlook_app":     {"fn": _action_adapter_tool("outlook", _load_outlook),    "required": ["action"], "optional": ["days", "count", "folder"], "description": "Outlook: read_calendar/sync_calendar/read_inbox"},
    "hwp_app":         {"fn": _action_adapter_tool("hwp", _load_hwp),            "required": ["action"], "optional": ["path", "out_path"], "description": "한글(HWP): md_to_hwp"},
    "solidworks_app":  {"fn": _action_adapter_tool("solidworks", _load_solidworks), "required": ["action"], "optional": ["path"], "description": "SolidWorks: run_macro"},
    "ocr_screen":      {"fn": _action_adapter_tool("ocr_screen", _load_ocr),      "required": ["action"], "optional": ["region", "path"], "description": "화면/이미지 OCR: read_screen/read_image/capabilities"},
    "desktop_ui":      {"fn": _action_adapter_tool("desktop_ui", _load_desktop_ui), "required": ["action"], "optional": ["task"], "description": "COM 없는 앱 조작(UIA): capabilities/run_task"},
    "matlab_run":      {"fn": _path_adapter_tool("matlab", lambda: __import__("agent_ops.adapters.matlab_batch", fromlist=["execute"]).execute, "script_path"), "required": ["script_path"], "optional": [], "description": "MATLAB -batch (.m) 실행"},
    "fluent_run":      {"fn": _path_adapter_tool("fluent", lambda: __import__("agent_ops.adapters.fluent_batch", fromlist=["execute"]).execute, "journal_path"), "required": ["journal_path"], "optional": [], "description": "ANSYS Fluent journal(.jou) 실행"},
    "autocad_run":     {"fn": tool_autocad_run,   "required": ["dwg_path", "scr_path"], "optional": [],           "description": "AutoCAD accoreconsole: .dwg 사본에 .scr 실행"},
}

_PARAM_DESCRIPTIONS = {
    "path": "relative path",
    "content": "UTF-8 text",
    "title": "memory title",
    "note": "text to remember",
    "old": "exact text to replace",
    "new": "replacement text",
    "count": "max replacements or items",
    "query": "search text",
    "pattern": "glob, e.g. **/*.md",
    "action": "action name (browser or adapter)",
    "url": "URL",
    "tab": "tab index or title",
    "selector": "CSS selector",
    "text": "visible text substring",
    "index": "clickable or tab index",
    "timeout": "seconds",
    "max_length": "max text length",
    "max_text_length": "max text length",
    "max_html_length": "max html length",
    "limit": "maximum item count",
    "filename": "output filename",
    "wait_seconds": "seconds to wait",
    "load_timeout": "page load timeout seconds",
    "output_dir": "output directory",
    "max_clicks": "maximum clicks to explore",
    "include_clickables": "true/false",
    "out_path": "output file path",
    "sheet": "worksheet name",
    "range": "cell range, e.g. A1:C10",
    "values": "values to write",
    "bas_path": "macro .bas path",
    "days": "days ahead",
    "folder": "mail folder",
    "spec": "pptx spec",
    "macro": "macro name",
    "region": "screen region [x,y,w,h]",
    "lang": "OCR language, e.g. kor+eng",
    "task": "natural-language app task",
    "script_path": "script file path (.m)",
    "journal_path": "journal file path (.jou)",
    "dwg_path": "AutoCAD drawing .dwg path",
    "scr_path": "AutoCAD script .scr path",
}

_INT_PARAMS = {"count", "index", "timeout", "max_length", "max_text_length", "max_html_length", "max_clicks", "limit"}


# 항상 노출하는 핵심 도구(파일·검색·진단·기억). 나머지는 작업이 가리킬 때만.
_CORE_TOOLS = {"read_file", "write_file", "append_file", "replace_in_file",
               "list_dir", "search_files", "run_diagnostic", "project_info", "remember"}
# 키워드 → 추가로 노출할 도구 그룹. 약한 모델(EXAONE/Qwen 27~33B)은 도구가 많을수록
# 선택 정확도가 급락(연구 근거)하므로, 작업에 맞는 서브셋만 보여준다.
_TOOL_GROUPS = (
    (("web", "브라우저", "browser", "크롬", "chrome", "url", "http", "웹", "페이지", "포털", "사이트", "탭"),
     {"browse_tabs", "read_web_page", "browser_action", "new_tab", "snapshot",
      "find_clickables", "click", "screenshot", "wait_for_selector", "select_tab", "spa_map"}),
    (("excel", "엑셀", "xlsx", "워크북", "워크시트", "매크로", "vba", "office", "워드", "word", "ppt", "파워포인트", "슬라이드"),
     {"excel_app"}),
    (("outlook", "아웃룩", "메일", "이메일", "일정", "받은편지", "캘린더"), {"outlook_app"}),
    (("한글", "hwp", "아래아"), {"hwp_app"}),
    (("solidworks", "솔리드웍스", "파트", "어셈블리", "sldworks"), {"solidworks_app"}),
    (("화면", "ocr", "스크린샷 읽", "글자 읽", "screen"), {"ocr_screen"}),
    (("데스크톱", "gui 앱", "windows-use", "uia"), {"desktop_ui"}),
    (("matlab", "매트랩", "simulink"), {"matlab_run"}),
    (("fluent", "플루언트", "ansys", "cfd", "저널", "journal"), {"fluent_run"}),
    (("autocad", "오토캐드", "dwg", ".scr", "도면", "accoreconsole"), {"autocad_run"}),
)


def _tools_for_capabilities(capability_ids: Optional[List[str]]) -> set:
    if not capability_ids:
        return set()
    try:
        from .capabilities import route_hints_for_capabilities
        hints = route_hints_for_capabilities(capability_ids)
    except Exception:
        return set()
    return {name for name in hints.get("tools", []) if name in REGISTRY}


def _tools_for_prompt(prompt: str, capability_ids: Optional[List[str]] = None) -> List[str]:
    """작업에 관련된 도구 이름 목록(핵심 + capability + 키워드 매칭 그룹)."""
    low = (prompt or "").lower()
    names = set(_CORE_TOOLS) | _tools_for_capabilities(capability_ids)
    for kws, group in _TOOL_GROUPS:
        if any(k in low for k in kws):
            names |= group
    # ".m " 문자열 매칭은 문장 끝 "analysis.m"을 놓친다 — 정규식으로 끝/공백 모두 허용.
    if re.search(r"\.m(\s|$)", low):
        names |= {"matlab_run"}
    return [n for n in REGISTRY if n in names]


def tool_definitions(prompt: Optional[str] = None,
                     capability_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """OpenAI-style function definitions. prompt 주면 작업 관련 서브셋만(약한 모델
    정확도↑). prompt 없으면 전체(하위호환)."""
    names = _tools_for_prompt(prompt or "", capability_ids) if (prompt or capability_ids) else list(REGISTRY)
    return _definitions_for(names)


def _definitions_for(names: List[str]) -> List[Dict[str, Any]]:
    """이름 목록 → function definition 목록 (동적 도구 확장에서도 재사용)."""
    defs = []
    for name in names:
        spec = REGISTRY[name]
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


def _group_for_tool(name: str) -> set:
    """도구 이름 → 함께 노출할 그룹(같은 앱/영역 도구). 그룹 밖이면 그 도구만."""
    expanded = {name}
    for _kws, group in _TOOL_GROUPS:
        if name in group:
            expanded |= group
    return expanded


# tool 결과를 대화 이력에 넣을 때 긴 텍스트 필드 절단 상한(문자).
# read_file/search_files 대형 결과가 이후 턴의 컨텍스트를 다 먹지 않게 한다.
_TOOL_RESULT_TEXT_LIMIT = 6000

# 시스템 주입 블록(기억/위키/프로필/API/KB/디자인/도메인/스킬) 합산 전역 예산(문자).
_INSERT_BUDGET = 6000


def _truncate_for_history(value: Any, limit: int = _TOOL_RESULT_TEXT_LIMIT) -> Any:
    """이력 주입용 사본: 긴 문자열 필드만 절단(원본 tool_results는 그대로 유지)."""
    if isinstance(value, str):
        if len(value) > limit:
            return value[:limit] + f"...(truncated, 원본 {len(value)}자)"
        return value
    if isinstance(value, dict):
        return {k: _truncate_for_history(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate_for_history(v, limit) for v in value]
    return value


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
    # 작업별 도구 서브셋(약한 모델 정확도↑) + "사용 가능 도구 N개" 카운터(도구 누락 방지).
    tools = tool_definitions(prompt, capability_ids=capability_ids)
    sys_prompt = AGENT_SYSTEM_PROMPT + f"\n\n사용 가능한 도구: {len(tools)}개. 이 목록 안의 도구만 호출하라."
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt},
    ]
    # 복리 기억의 쐐기돌: 축적된 규칙/교훈을 '기계적으로' 주입한다.
    # 페르소나가 recall을 잊어도 같은 실수를 반복하지 않도록 — 선의가 아닌 구조.
    # 주입 순서(제품 문서 §6.3): 전역 기억 → 폴더 프로필(기억/페르소나/규칙) → 작업.
    # 각 (priority, message) — priority 낮을수록 중요. 전역 예산 초과 시
    # 낮은 우선순위(큰 숫자)부터 드랍한다: memory(0) > project(1) > api/kb(2)
    # > skill(3) > design(4) > domain(5) > wiki(6).
    inserts: List[Any] = []
    try:
        from .memory_manager import core_memory, extract_keywords, format_recall_for_prompt, recall
        keywords = extract_keywords(prompt)
        # 회상 보장: core memory(사용자 규칙 + 최근 실수, 중요도순)는 키워드가
        # 안 맞아도 항상 주입(약한 모델 검색 실패 안전망), 키워드 매칭분은 그 위에
        # 추가 (id 로 중복 제거). recall은 recency×importance×relevance 랭킹.
        pinned = core_memory(limit=5)
        matched = recall(keywords=keywords, limit=5)
        seen_ids = {r.get("id") for r in pinned}
        mem = pinned + [r for r in matched if r.get("id") not in seen_ids]
        if mem:
            inserts.append((0, {"role": "system",
                                "content": "이전에 축적된 사용자 규칙/교훈 — 반드시 반영:\n"
                                           + format_recall_for_prompt(mem[:8])}))
        # 복리 recall: 개별 사건보다 '주제 페이지'(증류된 지식)가 강하다.
        # 기록이 쌓일수록 같은 주제 발췌가 저절로 풍부해진다 (LLM Wiki 층).
        from .wiki_manager import recall_pages
        # limit=2: WS-4 이후 recall_pages가 사람이 쓴 manual/ 노트를 최소 1개 우선 포함하므로,
        # 1이면 manual이 rich한 auto 주제페이지를 밀어낼 수 있다. 2로 두어 manual+auto를 함께
        # 넣는다(총량은 아래 전역 주입예산 _INSERT_BUDGET로 이미 보호됨).
        pages = recall_pages(keywords, limit=2)
        for page in pages:
            inserts.append((6, {"role": "system",
                                "content": f"축적된 주제 지식(위키 '{page['topic']}') — 참고:\n"
                                           + page["excerpt"]}))
    except Exception:  # noqa: BLE001 - 기억 주입 실패가 작업을 막으면 안 된다
        pass
    try:
        from .project_profile import format_context_for_prompt, load_project_context
        project = format_context_for_prompt(load_project_context())
        if project:
            inserts.append((1, {"role": "system", "content": project}))
    except Exception:  # noqa: BLE001 - 프로필 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 공식 API 근거 주입: 작업이 특정 소프트웨어(Excel/HWP/CAD 등)를 가리키면
        # 그 소프트웨어의 공식 문서 발췌를 넣어 환각 API 대신 실제 명령으로 코딩하게 한다.
        from .api_reference import context_for_prompt as _api_ctx
        api_ref = _api_ctx(prompt)
        if api_ref:
            inserts.append((2, {"role": "system", "content": api_ref}))
    except Exception:  # noqa: BLE001 - API 참조 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 레퍼런스 지식베이스 주입: 작업이 공학 도메인·규격·소프트스킬을 가리키면
        # 팩트체크된 이론·규격·실무 지식을 MOC(지도)+관련 발췌로 넣는다("이거 만들어줘"→근거).
        from .knowledge_base import context_for_prompt as _kb_ctx
        kb_ref = _kb_ctx(prompt)
        if kb_ref:
            inserts.append((2, {"role": "system", "content": kb_ref}))
    except Exception:  # noqa: BLE001 - 지식베이스 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 디자인 가이드 주입: 보고서/문서/PPT 생성 작업이면 디자인·구성 원칙을 넣어
        # 밋밋한 기본 결과 대신 위계·정렬·여백·1슬라이드1메시지를 지킨 결과물을 만들게 한다.
        from .design_guidance import context_for_prompt as _design_ctx
        design_ref = _design_ctx(prompt)
        if design_ref:
            inserts.append((4, {"role": "system", "content": design_ref}))
    except Exception:  # noqa: BLE001 - 디자인 가이드 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 한국 회사 업무 맥락 주입: 메일/회의록/보고서/대외 문서면 관행·톤을 넣는다.
        from .domain_context import context_for_prompt as _domain_ctx
        domain_ref = _domain_ctx(prompt)
        if domain_ref:
            inserts.append((5, {"role": "system", "content": domain_ref}))
    except Exception:  # noqa: BLE001 - 도메인 맥락 주입 실패도 작업을 막으면 안 된다
        pass
    try:
        # 프로세스 스킬 자동 적용: 작업 유형에 맞는 '일하는 절차'를 넣어 방법까지 따르게 한다.
        from .skill_router import context_for_prompt as _skill_ctx
        skill_ref = _skill_ctx(prompt, capability_ids=capability_ids)
        if skill_ref:
            inserts.append((3, {"role": "system", "content": skill_ref}))
    except Exception:  # noqa: BLE001 - 스킬 주입 실패도 작업을 막으면 안 된다
        pass
    # 전역 주입 예산: injector별 개별 예산 합(최악 ~12K자)이 약한 모델 컨텍스트를
    # 다 먹지 않게 총 6000자로 제한. 초과 시 우선순위 낮은(숫자 큰) 블록부터,
    # 같은 우선순위면 뒤 블록부터 드랍. memory(0)는 안전망이므로 드랍하지 않는다.
    total_chars = sum(len(m["content"]) for _p, m in inserts)
    if total_chars > _INSERT_BUDGET:
        drop_order = sorted(range(len(inserts)),
                            key=lambda i: (-inserts[i][0], -i))
        dropped = set()
        for idx in drop_order:
            if total_chars <= _INSERT_BUDGET or inserts[idx][0] == 0:
                continue
            total_chars -= len(inserts[idx][1]["content"])
            dropped.add(idx)
        inserts = [x for i, x in enumerate(inserts) if i not in dropped]
    for offset, (_prio, msg) in enumerate(inserts):
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
    llm_outcome = ""
    fallback_trigger = ""
    exposed = {t["function"]["name"] for t in tools}
    warned_signatures: set = set()  # 반복 실패에 교정 기회(경고 1회)를 준 서명
    last_assistant_content = ""     # max_turns 소진 시 빈 결과 대신 돌려줄 마지막 응답

    for _ in range(max_turns):
        turns += 1
        llm = call_llm(messages, tools=tools, env=env, transport=transport,
                       diag_dir=diag_dir, capability_ids=capability_ids)
        calls = llm.get("tool_calls") or []
        # 동적 도구 확장: 미노출 이름이라도 REGISTRY에 실존하면 해당 그룹을 노출에
        # 추가하고 같은 턴을 재시도한다(디스패치 없이). call_llm은 미노출 도구
        # 호출을 unavailable_tool_repeat로 실패 처리하므로 ok 여부보다 먼저 검사.
        # REGISTRY에도 없으면 기존 폴백 유지(llm_failed 또는 unknown_tool 피드백).
        hidden = [c.get("name") for c in calls
                  if c.get("name") not in exposed and c.get("name") in REGISTRY]
        if hidden:
            add: set = set()
            for n in hidden:
                add |= _group_for_tool(n)
            add -= exposed
            if add:
                exposed |= add
                tools = tools + _definitions_for([n for n in REGISTRY if n in add])
                messages.append({"role": "system",
                                 "content": "도구 %d개가 추가되었다: %s. 이제 이 도구들을 호출할 수 있다."
                                            % (len(add), ", ".join(sorted(add)))})
                continue
        if not llm["ok"]:
            outcome = "llm_failed"
            # call_llm 계층의 세부 outcome(local_fallback/stop)을 보존해
            # 상위(cmd_agent/cmd_work)가 게이트웨이 장애 안내를 띄울 수 있게 한다.
            llm_outcome = llm.get("outcome", "")
            fallback_trigger = llm.get("fallback_trigger", "")
            final_content = llm.get("content", "")
            break
        if llm.get("content"):
            last_assistant_content = llm.get("content", "")
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
                sig = _call_signature(call)
                if sig not in warned_signatures:
                    # 교정 기회 1회: 즉시 중단하지 않고 경고를 주입해 인자/접근을 바꾸게 한다.
                    warned_signatures.add(sig)
                    warn = {"ok": False, "tool": call.get("name", ""),
                            "error": "동일 인자 호출이 2회 실패했다. 인자를 바꾸거나 "
                                     "다른 도구/접근을 써라. 반복하면 중단된다."}
                    messages.append({"role": "tool", "tool_call_id": call_ids[i],
                                     "name": call.get("name", ""),
                                     "content": json.dumps(warn, ensure_ascii=False)})
                    continue
                outcome = "tool_loop_cutoff"
                final_content = (f"Aborted: tool call {call.get('name')} failed repeatedly "
                                 "with identical arguments.")
                cutoff = True
                break
            result = dispatcher.dispatch(call)
            tool_results.append(result)
            # 이력에는 절단본만: 대형 read_file/search_files 결과가 이후 턴을 잠식하지
            # 않게. 전체 원본은 tool_results 에 남는다(진단/반환용).
            messages.append({"role": "tool", "tool_call_id": call_ids[i],
                             "name": call.get("name", ""),
                             "content": json.dumps(_truncate_for_history(result), ensure_ascii=False)})
        if cutoff:
            break

    # max_turns 소진 시 빈 결과 금지: 마지막 assistant 응답 또는 도구 실행 요약을 반환.
    if outcome == "max_turns_exceeded" and not final_content:
        if last_assistant_content:
            final_content = last_assistant_content
        else:
            used = [r.get("tool", "?") for r in tool_results]
            final_content = ("최대 턴 초과 — 실행한 도구 %d개: %s"
                             % (len(used), ", ".join(used) if used else "(없음)"))

    result = {
        "ok": outcome == "completed",
        "outcome": outcome,
        "llm_outcome": llm_outcome,
        "fallback_trigger": fallback_trigger,
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
