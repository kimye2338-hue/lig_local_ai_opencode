# -*- coding: utf-8 -*-
"""Deterministic mock LLM transport for offline pipeline smoke runs.

Mock mode validates the full user-facing chain (BAT/CLI -> run_agent_loop ->
tool dispatch -> real sandboxed file operations -> diagnostics) without any
company gateway. The "LLM" here is a scripted state machine, not model
intelligence: it always performs write -> read-back -> final answer.
Real EXAONE/Qwen behavior remains company validation pending.
"""
from __future__ import annotations

import json
from typing import Any, Dict

# Fake, clearly-labeled values: mock mode must never read the real secret file.
MOCK_ENV = {
    "LIG_GATEWAY_BASE_URL": "http://mock.invalid/gw",
    "LIG_API_KEY": "mock-key-not-a-secret",
    "LIG_DEFAULT_PROVIDER": "lig-coding",
}

MOCK_OUTPUT_FILE = "모의_결과/작업_요약.md"


def _tool_response(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return {"choices": [{"message": {"content": "", "tool_calls": [
        {"type": "function", "function": {"name": name,
                                          "arguments": json.dumps(args, ensure_ascii=False)}}
    ]}}]}


def _text_response(text: str) -> Dict[str, Any]:
    return {"choices": [{"message": {"content": text}}]}


def make_mock_transport():
    """Reactive scripted transport: decides the next step from the number of
    tool-result messages already in the conversation, so it exercises the real
    dispatch/feedback loop instead of ignoring it."""

    def transport(url: str, payload: Dict[str, Any], headers: Dict[str, str],
                  timeout: int) -> Dict[str, Any]:
        messages = payload.get("messages", [])
        user_task = next((m.get("content", "") for m in messages
                          if m.get("role") == "user"), "")
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        step = len(tool_msgs)

        if step == 0:
            content = ("# 모의 실행 요약\n\n"
                       f"- 요청: {user_task}\n"
                       "- 모드: mock (회사 API 미사용, 파이프라인 검증용)\n"
                       "- 이 파일은 mock LLM이 write_file 도구로 생성했습니다.\n")
            return _tool_response("write_file",
                                  {"path": MOCK_OUTPUT_FILE, "content": content})
        if step == 1:
            return _tool_response("read_file", {"path": MOCK_OUTPUT_FILE})

        # Final turn: report based on the actual dispatch results fed back.
        failures = []
        for m in tool_msgs:
            try:
                r = json.loads(m.get("content", "{}"))
                if not r.get("ok"):
                    failures.append(r.get("error", "unknown"))
            except Exception:
                failures.append("unparseable tool result")
        if failures:
            return _text_response("모의 실행 중 도구 오류가 발생했습니다: " + "; ".join(failures))
        return _text_response(
            f"모의 실행이 완료되었습니다. 결과 파일: {MOCK_OUTPUT_FILE} "
            "(mock 모드는 파이프라인 검증용이며 실제 모델 응답이 아닙니다.)")

    return transport
