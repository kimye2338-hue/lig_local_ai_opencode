# -*- coding: utf-8 -*-
"""Capability-floor tests: malformed tool-call recovery (stdlib only).

Run: py -3.11 tests\\test_toolcall_parser.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.toolcall_parser import parse_tool_calls  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


# 1. Clean structured OpenAI tool_calls
r = parse_tool_calls({"choices": [{"message": {"content": "", "tool_calls": [
    {"id": "1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "a.txt"}'}}]}}]})
check("structured ok", r["parse_status"] == "ok" and r["tool_calls"] == [{"name": "read_file", "arguments": {"path": "a.txt"}}], str(r))

# 2. Legacy function_call shape
r = parse_tool_calls({"choices": [{"message": {"content": "", "function_call": {"name": "ls", "arguments": "{}"}}}]})
check("legacy function_call", r["parse_status"] == "ok" and r["tool_calls"][0]["name"] == "ls", str(r))

# 3. Tool call as plain JSON in content (no structured field)
r = parse_tool_calls('{"name": "write_file", "arguments": {"path": "메모.txt", "content": "한글"}}')
check("json-in-text", r["parse_status"] == "repaired" and r["tool_calls"][0]["arguments"]["path"] == "메모.txt", str(r))

# 4. Fenced json block mixed with Korean prose
r = parse_tool_calls('파일을 읽겠습니다.\n```json\n{"tool_calls": [{"name": "read_file", "arguments": {"path": "보고서 초안.md"}}]}\n```\n진행합니다.')
check("fenced+prose", r["parse_status"] == "repaired" and r["tool_calls"][0]["name"] == "read_file", str(r))

# 5. Trailing comma repair
r = parse_tool_calls('{"name": "search", "arguments": {"query": "fallback",},}')
check("trailing comma", r["parse_status"] == "repaired" and r["tool_calls"][0]["arguments"] == {"query": "fallback"}, str(r))

# 6. Truncated JSON (missing closing braces)
r = parse_tool_calls('{"name": "append_file", "arguments": {"path": "log.txt", "text": "done"')
check("truncated json", r["parse_status"] == "repaired" and r["tool_calls"][0]["name"] == "append_file", str(r))

# 7. Embedded object in prose without fences
r = parse_tool_calls('결과는 다음과 같습니다: {"tool_name": "list_dir", "args": {"path": "C:\\\\작업 폴더"}} 확인 바랍니다.')
check("embedded in prose", r["parse_status"] == "repaired" and r["tool_calls"][0]["name"] == "list_dir", str(r))

# 8. Plain answer, no tool call at all
r = parse_tool_calls("요약: 이 문서는 세 가지 주제를 다룹니다.")
check("plain text none", r["parse_status"] == "none" and not r["tool_calls"], str(r))

# 9. Broken beyond repair but intent visible -> failed, not crash
r = parse_tool_calls('"tool_call": read_file(path=a.txt')
check("unrecoverable -> failed", r["parse_status"] == "failed" and r["errors"], str(r))

# 10. Unavailable tool detection
r = parse_tool_calls('{"name": "delete_everything", "arguments": {}}', available_tools=["read_file", "write_file"])
check("unavailable tool", r["unavailable_tools"] == ["delete_everything"], str(r))

# 11. Arguments given as stringified JSON inside content JSON
r = parse_tool_calls('{"name": "edit_file", "arguments": "{\\"path\\": \\"a.py\\"}"}')
check("string arguments", r["tool_calls"][0]["arguments"] == {"path": "a.py"}, str(r))

# 12. Structured field present but garbage -> error recorded, no crash
r = parse_tool_calls({"choices": [{"message": {"content": "", "tool_calls": [{"type": "function"}]}}]})
check("garbage structured", r["parse_status"] in ("none", "failed") and r["errors"], str(r))

print(f"\n{PASS} checks passed")
