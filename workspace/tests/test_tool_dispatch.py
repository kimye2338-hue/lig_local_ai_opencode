# -*- coding: utf-8 -*-
"""Unit tests for local_tools + ToolDispatcher (stdlib only, no network).

Run: py -3.11 tests\test_tool_dispatch.py
"""
from __future__ import annotations

import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.mock_transport import MOCK_ENV, make_mock_transport  # noqa: E402
from agent_ops.tool_dispatch import AGENT_SYSTEM_PROMPT, ToolDispatcher, run_agent_loop, tool_definitions  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="agentops_dispatch_"))
    ws = tmp / "작업공간"  # Korean workspace root
    ws.mkdir()
    diag = tmp / "diag"
    d = ToolDispatcher(ws, diag_dir=diag)

    # --- registry / definitions ---
    defs = tool_definitions()
    names = {x["function"]["name"] for x in defs}
    browser_names = {"browse_tabs", "read_web_page", "browser_action", "new_tab", "snapshot",
                     "find_clickables", "click", "screenshot", "wait_for_selector", "select_tab", "spa_map"}
    # 앱 어댑터 전체 노출: 대화형 에이전트가 Office/CAD/메일/OCR 앱을 직접 호출.
    adapter_names = {"excel_app", "outlook_app", "hwp_app", "solidworks_app", "ocr_screen",
                     "desktop_ui", "matlab_run", "fluent_run", "autocad_run"}
    check("tool_definitions covers registry",
          {"read_file", "replace_in_file", "project_info", "remember"}.issubset(names)
          and browser_names.issubset(names) and adapter_names.issubset(names) and len(names) == 29)
    prompt_schema_bytes = len(AGENT_SYSTEM_PROMPT.encode("utf-8"))
    prompt_schema_bytes += len(json.dumps(defs, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    # Browser action tools are explicit so weak models stop inventing unsupported tool names.
    # Budget history: 7.5KB at 18 tools; +0.3KB for project_info/remember; +~3KB for the
    # 9 app-adapter tools (Office/CAD/mail/OCR direct control — user-approved full exposure,
    # schemas kept tight: undeclared options still pass through at runtime). Keep tight:
    # every new tool must justify its schema bytes against weak-model call accuracy.
    check("prompt and schema stay under 10.8KB", prompt_schema_bytes <= 11059, str(prompt_schema_bytes))

    r = d.dispatch({"name": "browser_action", "arguments": {"action": "no_such_browser_action"}})
    check("browser_action rejects invented actions without Chrome",
          not r["ok"] and r["root_cause_category"] == "invalid_argument", str(r))

    # --- write then read (Korean path + content) ---
    r = d.dispatch({"name": "write_file", "arguments": {"path": "메모/노트.md", "content": "첫 줄\n둘째 줄\n"}})
    check("write_file creates nested Korean path", r["ok"] and r["created"], str(r))
    r = d.dispatch({"name": "read_file", "arguments": {"path": "메모/노트.md"}})
    check("read_file returns Korean content", r["ok"] and r["content"] == "첫 줄\n둘째 줄\n", str(r))
    check("new file is UTF-8 no BOM", not (ws / "메모" / "노트.md").read_bytes().startswith(b"\xef\xbb\xbf"))

    # --- append preserves BOM+CRLF style ---
    bom_file = ws / "bom.txt"
    bom_file.write_bytes(b"\xef\xbb\xbf" + "한글 원본\r\n".encode("utf-8"))
    r = d.dispatch({"name": "append_file", "arguments": {"path": "bom.txt", "content": "추가 줄\n"}})
    raw = bom_file.read_bytes()
    check("append_file preserves BOM", r["ok"] and raw.startswith(b"\xef\xbb\xbf"), str(r))
    check("append_file preserves CRLF", b"\xec\xb6\x94\xea\xb0\x80 \xec\xa4\x84\r\n" in raw, repr(raw))

    # --- replace_in_file ---
    r = d.dispatch({"name": "replace_in_file", "arguments": {"path": "bom.txt", "old": "원본", "new": "수정본"}})
    check("replace_in_file works and keeps BOM", r["ok"] and bom_file.read_bytes().startswith(b"\xef\xbb\xbf"), str(r))
    r = d.dispatch({"name": "replace_in_file", "arguments": {"path": "bom.txt", "old": "없는텍스트", "new": "x"}})
    check("replace_in_file missing old -> not_found", not r["ok"] and r["root_cause_category"] == "not_found", str(r))

    # --- list_dir / search_files ---
    r = d.dispatch({"name": "list_dir", "arguments": {"path": "메모"}})
    check("list_dir lists Korean dir", r["ok"] and r["entries"][0]["name"] == "노트.md", str(r))
    r = d.dispatch({"name": "search_files", "arguments": {"query": "둘째", "pattern": "**/*.md"}})
    check("search_files finds Korean text", r["ok"] and r["matches"][0]["path"] == "메모/노트.md" and r["matches"][0]["line"] == 2, str(r))

    # --- run_diagnostic ---
    r = d.dispatch({"name": "run_diagnostic", "arguments": {}})
    check("run_diagnostic reports writable workspace", r["ok"] and r["writable"] and r["workspace_exists"], str(r))

    # --- safety: path traversal / absolute paths ---
    r = d.dispatch({"name": "read_file", "arguments": {"path": "../밖의파일.txt"}})
    check("path traversal blocked", not r["ok"] and r["root_cause_category"] == "path_escape", str(r))
    r = d.dispatch({"name": "write_file", "arguments": {"path": "C:/Windows/pwn.txt", "content": "x"}})
    check("absolute path blocked", not r["ok"] and r["root_cause_category"] == "path_escape", str(r))
    check("no file written outside root", not (tmp / "밖의파일.txt").exists())

    # --- validation failures ---
    r = d.dispatch({"name": "no_such_tool", "arguments": {}})
    check("unknown tool -> unknown_tool", not r["ok"] and r["root_cause_category"] == "unknown_tool", str(r))
    r = d.dispatch({"name": "write_file", "arguments": {"path": "a.txt"}})
    check("missing required arg -> missing_argument", not r["ok"] and r["root_cause_category"] == "missing_argument", str(r))
    r = d.dispatch({"name": "read_file", "arguments": '{"path": "메모/노트.md"}'})
    check("string JSON arguments normalized", r["ok"], str(r))
    r = d.dispatch({"name": "read_file", "arguments": "{not json"})
    check("broken string arguments -> invalid_argument", not r["ok"] and r["root_cause_category"] == "invalid_argument", str(r))

    # --- repeated failure cutoff ---
    bad = {"name": "read_file", "arguments": {"path": "없는파일.txt"}}
    check("no cutoff before failures", not d.repeated_failure(bad))
    d.dispatch(bad)
    d.dispatch(bad)
    check("cutoff after repeated identical failures", d.repeated_failure(bad))
    ok_call = {"name": "read_file", "arguments": {"path": "메모/노트.md"}}
    check("different call not cut off", not d.repeated_failure(ok_call))

    # --- diagnostics written ---
    check("dispatch history recorded", (diag / "tool-dispatch-history.jsonl").exists() and (diag / "tool-dispatch-last.json").exists())
    history = (diag / "tool-dispatch-history.jsonl").read_text(encoding="utf-8")
    check("history logs root cause categories", "path_escape" in history and "unknown_tool" in history)

    inner = make_mock_transport()
    seen_payloads = []

    def capturing(url, payload, headers, timeout):
        seen_payloads.append(payload)
        return inner(url, payload, headers, timeout)

    result = run_agent_loop("메모를 작성해줘", ws, env=MOCK_ENV,
                            transport=capturing, diag_dir=diag)
    final_msgs = seen_payloads[-1]["messages"]
    assistant_tcs = [tc for m in final_msgs
                     if m.get("role") == "assistant" and m.get("tool_calls")
                     for tc in m["tool_calls"]]
    tool_ids = [m.get("tool_call_id") for m in final_msgs if m.get("role") == "tool"]
    check("mock agent loop completed", result["ok"], str(result))
    check("assistant tool_calls carry self-issued id",
          assistant_tcs and all(tc.get("id") and tc["id"] != "N/A" for tc in assistant_tcs))
    check("tool msgs tool_call_id matches assistant ids",
          tool_ids == [tc["id"] for tc in assistant_tcs])

    print(f"\nALL {PASS} CHECKS PASSED (tool dispatch)")


if __name__ == "__main__":
    main()
