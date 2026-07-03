# -*- coding: utf-8 -*-
"""Mock-transport tests for the resilient LIG runtime (stdlib only).

Run: py -3.11 tests\\test_lig_runtime.py
All provider/gateway behavior is mocked — real EXAONE/Qwen behavior remains
company validation pending.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_ops.lig_runtime import TransportError, _chat_completions_url, call_llm  # noqa: E402

PASS = 0


def check(label: str, cond: bool, detail: str = "") -> None:
    global PASS
    if cond:
        PASS += 1
        print(f"PASS  {label}")
    else:
        print(f"FAIL  {label}  {detail}")
        sys.exit(1)


ENV = {
    "LIG_GATEWAY_BASE_URL": "http://10.9.9.9/gw",
    "LIG_API_KEY": "FAKE_SECRET_9999",
    "LIG_DEFAULT_PROVIDER": "lig-coding",
}
MSGS = [{"role": "user", "content": "파일을 읽어줘"}]
TOOLS = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]


def resp(content="", tool_calls=None):
    msg = {"content": content}
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


def scripted(*events):
    """Each event: dict response, or TransportError to raise. Records calls."""
    seq = list(events)
    calls = []

    def transport(url, payload, headers, timeout):
        calls.append({"url": url, "model": payload["model"], "msg_count": len(payload["messages"])})
        ev = seq.pop(0) if seq else TransportError("provider_unreachable", "script exhausted")
        if isinstance(ev, TransportError):
            raise ev
        return ev

    transport.calls = calls
    return transport


with tempfile.TemporaryDirectory() as td:
    diag = Path(td)

    check("base /v1 normalized to chat completions",
          _chat_completions_url("http://127.0.0.1:11434/v1") == "http://127.0.0.1:11434/v1/chat/completions")
    check("explicit chat completions url preserved",
          _chat_completions_url("http://127.0.0.1:11434/v1/chat/completions") == "http://127.0.0.1:11434/v1/chat/completions")

    # 1. Clean structured tool call -> ok, no fallback
    t = scripted(resp("", [{"function": {"name": "read_file", "arguments": '{"path": "a.txt"}'}}]))
    r = call_llm(MSGS, tools=TOOLS, env=ENV, transport=t, diag_dir=diag)
    check("clean structured ok", r["ok"] and r["parse_status"] == "ok" and r["provider_final"] == "lig-coding" and r["attempts"] == 0, str(r))

    # 2. Fenced JSON tool call in content -> repaired, still ok
    t = scripted(resp('```json\n{"name": "read_file", "arguments": {"path": "보고서.md"}}\n```'))
    r = call_llm(MSGS, tools=TOOLS, require_tool_call=True, env=ENV, transport=t, diag_dir=diag)
    check("fenced repaired ok", r["ok"] and r["parse_status"] == "repaired" and r["tool_calls"][0]["arguments"]["path"] == "보고서.md", str(r))

    # 3. Timeout -> retry same provider -> success on 2nd try
    t = scripted(TransportError("http_timeout"), resp("답변입니다"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag)
    check("timeout retry ok", r["ok"] and r["attempts"] == 1 and r["provider_final"] == "lig-coding" and len(t.calls) == 2, str(r))

    # 4. Two timeouts -> switch to lig-fallback (Qwen) -> success
    t = scripted(TransportError("http_timeout"), TransportError("http_timeout"), resp("fallback 답변"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag)
    check("timeout x2 -> qwen", r["ok"] and r["provider_final"] == "lig-fallback" and t.calls[-1]["model"] == "Qwen3.6-27B", str(r))
    check("fallback url used", "Qwen3.6-27B-vibe_coding_think_off" in t.calls[-1]["url"], str(t.calls))

    # 5. HTTP 500 -> retry -> 500 again -> fallback provider
    t = scripted(TransportError("http_5xx"), TransportError("http_5xx"), resp("ok"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag)
    check("5xx -> fallback", r["ok"] and r["provider_final"] == "lig-fallback", str(r))

    # 6. HTTP 4xx -> stop immediately (auth/route error, retry useless)
    t = scripted(TransportError("http_4xx", "HTTP 401"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag)
    check("4xx stop", not r["ok"] and r["outcome"] == "stop" and r["fallback_trigger"] == "http_4xx" and len(t.calls) == 1, str(r))

    # 7. Malformed tool call -> simplify retry (extra system msg) -> recovered
    t = scripted(resp('"tool_call": read_file(path='), resp('{"name": "read_file", "arguments": {"path": "a.txt"}}'))
    r = call_llm(MSGS, tools=TOOLS, require_tool_call=True, env=ENV, transport=t, diag_dir=diag)
    check("malformed -> simplify -> ok", r["ok"] and r["repaired"] and t.calls[1]["msg_count"] == len(MSGS) + 1, str(r))

    # 8. Malformed persists -> exhausts simplify retries -> local_fallback
    bad = resp('"tool_call": broken(')
    t = scripted(bad, bad, bad, bad)
    r = call_llm(MSGS, tools=TOOLS, require_tool_call=True, env=ENV, transport=t, diag_dir=diag)
    check("persistent malformed -> local_fallback", not r["ok"] and r["outcome"] == "local_fallback", str(r))

    # 9. Prose when tool call required -> simplify -> still prose -> local_fallback
    prose = resp("죄송하지만 직접 처리하겠습니다.")
    t = scripted(prose, prose, prose, prose)
    r = call_llm(MSGS, tools=TOOLS, require_tool_call=True, env=ENV, transport=t, diag_dir=diag)
    check("text-instead-of-tool -> local_fallback", r["outcome"] == "local_fallback" and r["fallback_trigger"] == "text_instead_of_tool_call", str(r))

    # 10. Unavailable tool requested -> handled, no crash
    t = scripted(resp("", [{"function": {"name": "rm_rf", "arguments": "{}"}}]),
                 resp("", [{"function": {"name": "read_file", "arguments": "{}"}}]))
    r = call_llm(MSGS, tools=TOOLS, env=ENV, transport=t, diag_dir=diag)
    check("unavailable tool -> retry -> ok", r["ok"] and r["tool_calls"][0]["name"] == "read_file", str(r))

    # 11. Unreachable on both providers -> ends without infinite loop
    t = scripted(TransportError("provider_unreachable"), TransportError("provider_unreachable"), TransportError("provider_unreachable"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag)
    check("unreachable both -> terminal", not r["ok"] and r["outcome"] in ("stop", "local_fallback") and r["provider_final"] == "lig-fallback", str(r))

    # 12. Capability route selection: macro/code work -> lig-coding
    t = scripted(resp("macro ok"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag, capability_ids=["macro_generation"])
    check("macro task -> coding route", r["ok"] and r["route_selected"] == "lig-coding" and r["route_reason"] == "macro_generation" and t.calls[-1]["model"] == "EXAONE-4.5-33B", str(r))

    # 13. Capability route selection: document work -> lig-chat
    t = scripted(resp("doc ok"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag, capability_ids=["document_generation"])
    check("document task -> chat route", r["ok"] and r["route_selected"] == "lig-chat" and r["route_reason"] == "document_generation" and "default_think_off" in t.calls[-1]["url"], str(r))

    # 14. Unknown capability -> default lig-coding
    t = scripted(resp("default ok"))
    r = call_llm(MSGS, env=ENV, transport=t, diag_dir=diag, capability_ids=["unknown_cap"])
    check("unknown capability -> default coding", r["ok"] and r["route_selected"] == "lig-coding" and r["route_reason"] == "default", str(r))

    # 15. Diagnostics written, secrets redacted
    data = json.loads((diag / "runtime-last.json").read_text(encoding="utf-8"))
    blob = json.dumps(data) + (diag / "provider-fallback-last.json").read_text(encoding="utf-8")
    check("diag exists w/ fields", {"provider_initial", "provider_final", "fallback_trigger", "trail", "route_selected", "route_reason", "profile"}.issubset(data), str(data.keys()))
    check("diag records route", data["route_selected"] == "lig-coding" and data["route_reason"] == "default" and data["profile"] == "company_gateway", str(data))
    check("no secret in diag", "FAKE_SECRET_9999" not in blob and "10.9.9.9" not in blob, "secret leaked")

print(f"\n{PASS} checks passed")
